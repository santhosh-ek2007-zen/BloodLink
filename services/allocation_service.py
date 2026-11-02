"""
services/allocation_service.py — Concurrency-safe blood unit allocation.

Key safety guarantees
---------------------
1. Units are only allocated from the available_blood_inventory view,
   which enforces: status='available', not expired, screening approved,
   no existing active allocation.
2. Each unit is locked with SELECT ... FOR UPDATE SKIP LOCKED inside a
   transaction, preventing two concurrent sessions from allocating the
   same unit.
3. The partial-unique index uq_allocation_active_unit (constraints.sql)
   provides a database-level last line of defence against duplicates.
4. All changes (blood_unit.status, allocation insert, request status,
   status_history insert) occur in a single transaction and roll back
   together on any failure.
"""

import psycopg

from db import get_connection


def find_eligible_units(request_id: int) -> tuple[list, list]:
    """Return candidate units eligible for the given request.

    Uses the blood_compatibility table and available_blood_inventory view.
    Results are read-only candidates — they are NOT allocated by this call.
    """
    query = """
        SELECT
            abi.unit_id,
            abi.bank_name,
            abi.blood_group     AS donor_group,
            abi.component,
            abi.expiry_date,
            abi.expiry_date - CURRENT_DATE AS days_until_expiry
        FROM available_blood_inventory AS abi
        JOIN blood_request AS br
            ON br.request_id = %s
        JOIN blood_compatibility AS bc
            ON bc.component        = br.component
           AND bc.recipient_group  = br.recipient_group
           AND bc.donor_group      = abi.blood_group
        WHERE abi.component = br.component
        ORDER BY abi.expiry_date ASC, abi.unit_id ASC;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (request_id,))
            columns = [d.name for d in cur.description]
            rows = cur.fetchall()

    return columns, rows


def allocate_units(
    request_id: int,
    quantity: int,
    actor: str = "staff",
) -> dict:
    """Allocate up to `quantity` compatible units to a blood request.

    Uses row-level locking (SELECT … FOR UPDATE SKIP LOCKED) to prevent
    concurrent allocations of the same unit.

    Returns
    -------
    dict with keys:
        allocated       : int  — units successfully reserved
        already_issued  : int  — units already issued for this request
        still_needed    : int  — remaining unfulfilled demand
        request_status  : str  — new request status after allocation
        error           : str or None
    """
    if quantity <= 0:
        return {"error": "Quantity must be at least 1.", "allocated": 0,
                "already_issued": 0, "still_needed": quantity,
                "request_status": "unknown"}

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # ── 1. Validate and lock the request ─────────────────────
                cur.execute(
                    """
                    SELECT component, recipient_group, quantity_requested, status
                    FROM blood_request
                    WHERE request_id = %s
                    FOR UPDATE;
                    """,
                    (request_id,),
                )
                req = cur.fetchone()
                if req is None:
                    return {"error": f"Request {request_id} not found.",
                            "allocated": 0, "already_issued": 0,
                            "still_needed": quantity, "request_status": "unknown"}

                component, recipient_group, qty_requested, req_status = req

                if req_status in ("fulfilled", "cancelled"):
                    return {
                        "error": f"Request is already {req_status}.",
                        "allocated": 0, "already_issued": 0,
                        "still_needed": 0, "request_status": req_status,
                    }

                # ── 2. Count already-issued units for this request ───────
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM allocation
                    WHERE request_id = %s AND status = 'issued';
                    """,
                    (request_id,),
                )
                already_issued = cur.fetchone()[0]

                # ── 3. Find and lock eligible units ──────────────────────
                cur.execute(
                    """
                    SELECT abi.unit_id
                    FROM available_blood_inventory AS abi
                    JOIN blood_compatibility AS bc
                        ON bc.component       = %s
                       AND bc.recipient_group = %s
                       AND bc.donor_group     = abi.blood_group
                    WHERE abi.component = %s
                    ORDER BY abi.expiry_date ASC, abi.unit_id ASC
                    LIMIT %s
                    FOR UPDATE OF abi SKIP LOCKED;
                    """,
                    (component, recipient_group, component, quantity),
                )
                # NOTE: available_blood_inventory is a view; FOR UPDATE targets
                # the underlying blood_unit rows via the view rewrite.
                # psycopg/PostgreSQL resolve this correctly.
                candidate_ids = [row[0] for row in cur.fetchall()]

                allocated_count = 0
                for unit_id in candidate_ids:
                    # Reserve the unit
                    cur.execute(
                        "UPDATE blood_unit SET status = 'reserved' WHERE unit_id = %s;",
                        (unit_id,),
                    )
                    cur.execute(
                        """
                        INSERT INTO allocation (request_id, unit_id, status)
                        VALUES (%s, %s, 'reserved');
                        """,
                        (request_id, unit_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO status_history
                            (unit_id, old_status, new_status, actor, remarks)
                        VALUES (%s, 'available', 'reserved', %s,
                                'Reserved for blood request ' || %s::text);
                        """,
                        (unit_id, actor, request_id),
                    )
                    allocated_count += 1

                # ── 4. Update request status ──────────────────────────────
                total_reserved_issued = already_issued + allocated_count
                if total_reserved_issued >= qty_requested:
                    new_req_status = "partially_fulfilled"  # will be fulfilled on issue
                    # If quantity matches requested, mark as partially_fulfilled
                    # (full fulfilment happens when units are 'issued')
                    if total_reserved_issued >= qty_requested:
                        new_req_status = "partially_fulfilled"
                elif allocated_count > 0:
                    new_req_status = "partially_fulfilled"
                else:
                    new_req_status = req_status  # unchanged

                cur.execute(
                    "UPDATE blood_request SET status = %s WHERE request_id = %s;",
                    (new_req_status, request_id),
                )

            conn.commit()

        still_needed = max(0, quantity - allocated_count)
        return {
            "allocated": allocated_count,
            "already_issued": already_issued,
            "still_needed": still_needed,
            "request_status": new_req_status,
            "error": None,
        }

    except psycopg.errors.UniqueViolation:
        # The partial unique index caught a duplicate allocation attempt.
        return {
            "error": "A concurrent allocation claimed one or more units. Please retry.",
            "allocated": 0,
            "already_issued": 0,
            "still_needed": quantity,
            "request_status": "unknown",
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "allocated": 0,
            "already_issued": 0,
            "still_needed": quantity,
            "request_status": "unknown",
        }


def issue_units(request_id: int, actor: str = "staff") -> dict:
    """Mark all reserved units for a request as issued.

    Updates allocation.status → 'issued', blood_unit.status → 'issued',
    and blood_request.status → 'fulfilled' if quantity is met.
    All changes are atomic.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Fetch request details
                cur.execute(
                    """
                    SELECT quantity_requested, status
                    FROM blood_request
                    WHERE request_id = %s FOR UPDATE;
                    """,
                    (request_id,),
                )
                req = cur.fetchone()
                if req is None:
                    return {"error": f"Request {request_id} not found.", "issued": 0}

                qty_requested, req_status = req

                # Find reserved allocations
                cur.execute(
                    """
                    SELECT allocation_id, unit_id
                    FROM allocation
                    WHERE request_id = %s AND status = 'reserved'
                    FOR UPDATE;
                    """,
                    (request_id,),
                )
                reserved = cur.fetchall()

                issued_count = 0
                for alloc_id, unit_id in reserved:
                    cur.execute(
                        """
                        UPDATE allocation
                        SET status = 'issued', issued_at = CURRENT_TIMESTAMP
                        WHERE allocation_id = %s;
                        """,
                        (alloc_id,),
                    )
                    cur.execute(
                        "UPDATE blood_unit SET status = 'issued' WHERE unit_id = %s;",
                        (unit_id,),
                    )
                    cur.execute(
                        """
                        INSERT INTO status_history
                            (unit_id, old_status, new_status, actor, remarks)
                        VALUES (%s, 'reserved', 'issued', %s,
                                'Issued against blood request ' || %s::text);
                        """,
                        (unit_id, actor, request_id),
                    )
                    issued_count += 1

                # Count total issued now
                cur.execute(
                    """
                    SELECT COUNT(*) FROM allocation
                    WHERE request_id = %s AND status = 'issued';
                    """,
                    (request_id,),
                )
                total_issued = cur.fetchone()[0]

                new_status = "fulfilled" if total_issued >= qty_requested else "partially_fulfilled"
                cur.execute(
                    "UPDATE blood_request SET status = %s WHERE request_id = %s;",
                    (new_status, request_id),
                )

            conn.commit()

        return {"issued": issued_count, "request_status": new_status, "error": None}

    except Exception as exc:
        return {"error": str(exc), "issued": 0, "request_status": "unknown"}


def get_allocation_history(request_id: int) -> tuple[list, list]:
    """Return allocation records for a request."""
    query = """
        SELECT
            a.allocation_id,
            a.unit_id,
            bu.blood_group,
            bu.component,
            bb.bank_name,
            a.status            AS allocation_status,
            a.allocated_at,
            a.issued_at,
            a.cancelled_at
        FROM allocation AS a
        JOIN blood_unit  AS bu ON bu.unit_id     = a.unit_id
        JOIN donation    AS d  ON d.donation_id  = bu.donation_id
        JOIN blood_bank  AS bb ON bb.bank_id     = d.bank_id
        WHERE a.request_id = %s
        ORDER BY a.allocated_at DESC;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (request_id,))
            columns = [d.name for d in cur.description]
            rows = cur.fetchall()

    return columns, rows

