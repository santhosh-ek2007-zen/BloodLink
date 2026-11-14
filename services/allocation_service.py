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
            columns = ([d.name for d in cur.description] if cur.description else [])
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

    The function caps the number of units to reserve at the outstanding
    demand: (quantity_requested - already_reserved - already_issued).
    This prevents over-allocation even if the same function is called
    multiple times or with a quantity larger than the remaining need.

    Returns
    -------
    dict with keys:
        allocated       : int        — units successfully reserved this call
        already_reserved: int        — units already reserved before this call
        already_issued  : int        — units already issued for this request
        still_needed    : int        — remaining unfulfilled demand after this call
        request_status  : str        — new request status after allocation
        donor_summary   : list[str]  — human-readable per-donor breakdown
        error           : str or None
    """
    if quantity <= 0:
        return {
            "error": "Quantity must be at least 1.",
            "allocated": 0,
            "already_reserved": 0,
            "already_issued": 0,
            "still_needed": quantity,
            "request_status": "unknown",
            "donor_summary": [],
        }

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
                    return {
                        "error": f"Request {request_id} not found.",
                        "allocated": 0,
                        "already_reserved": 0,
                        "already_issued": 0,
                        "still_needed": quantity,
                        "request_status": "unknown",
                        "donor_summary": [],
                    }

                component, recipient_group, qty_requested, req_status = req

                if req_status in ("fulfilled", "cancelled"):
                    return {
                        "error": f"Request is already {req_status}.",
                        "allocated": 0,
                        "already_reserved": 0,
                        "already_issued": 0,
                        "still_needed": 0,
                        "request_status": req_status,
                        "donor_summary": [],
                    }

                # ── 2. Count already-reserved and already-issued units ────
                cur.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'reserved') AS already_reserved,
                        COUNT(*) FILTER (WHERE status = 'issued')   AS already_issued
                    FROM allocation
                    WHERE request_id = %s;
                    """,
                    (request_id,),
                )
                counts = cur.fetchone()
                already_reserved = counts[0] if counts else 0
                already_issued   = counts[1] if counts else 0

                # ── 3. Calculate remaining demand ─────────────────────────
                remaining_demand = qty_requested - already_reserved - already_issued
                if remaining_demand <= 0:
                    return {
                        "error": (
                            f"Request {request_id} already has all "
                            f"{qty_requested} unit(s) reserved or issued. "
                            "No further allocation is needed."
                        ),
                        "allocated": 0,
                        "already_reserved": already_reserved,
                        "already_issued": already_issued,
                        "still_needed": 0,
                        "request_status": req_status,
                        "donor_summary": [],
                    }

                # Cap the user-requested quantity at the actual remaining demand
                to_reserve = min(quantity, remaining_demand)

                # ── 4. Find and lock eligible units (FIFO by expiry) ──────
                cur.execute(
                    """
                    SELECT
                        bu.unit_id,
                        dn.donor_id,
                        dn.donor_name
                    FROM blood_unit AS bu
                    JOIN donation AS d
                        ON d.donation_id = bu.donation_id
                    JOIN donor AS dn
                        ON dn.donor_id = d.donor_id
                    JOIN blood_compatibility AS bc
                        ON bc.component       = %s
                       AND bc.recipient_group = %s
                       AND bc.donor_group     = bu.blood_group
                    WHERE bu.component = %s
                      AND bu.unit_id IN (
                          SELECT abi.unit_id
                          FROM available_blood_inventory AS abi
                      )
                    ORDER BY bu.expiry_date ASC, bu.unit_id ASC
                    LIMIT %s
                    FOR UPDATE OF bu SKIP LOCKED;
                    """,
                    (component, recipient_group, component, to_reserve),
                )
                candidate_rows = cur.fetchall()

                allocated_count = 0
                # Track units per donor for the success message
                donor_unit_map: dict[int, tuple[str, int]] = {}  # donor_id -> (name, count)

                for unit_id, did, dname in candidate_rows:
                    # Reserve the blood unit
                    cur.execute(
                        "UPDATE blood_unit SET status = 'reserved' WHERE unit_id = %s;",
                        (unit_id,),
                    )
                    # Insert allocation record
                    cur.execute(
                        """
                        INSERT INTO allocation (request_id, unit_id, status)
                        VALUES (%s, %s, 'reserved');
                        """,
                        (request_id, unit_id),
                    )
                    # Record status transition
                    cur.execute(
                        """
                        INSERT INTO status_history
                            (unit_id, old_status, new_status, actor, remarks)
                        VALUES (%s, 'available', 'reserved', %s,
                                'Reserved for blood request ' || %s::text);
                        """,
                        (unit_id, actor, request_id),
                    )

                    if did in donor_unit_map:
                        donor_unit_map[did] = (dname, donor_unit_map[did][1] + 1)
                    else:
                        donor_unit_map[did] = (dname, 1)

                    allocated_count += 1

                # ── 5. Update request status ──────────────────────────────
                total_active = already_reserved + already_issued + allocated_count
                if allocated_count > 0 or total_active > 0:
                    new_req_status = "partially_fulfilled"
                else:
                    new_req_status = req_status  # unchanged (still pending)

                cur.execute(
                    "UPDATE blood_request SET status = %s WHERE request_id = %s;",
                    (new_req_status, request_id),
                )

            conn.commit()

        still_needed = max(0, qty_requested - already_reserved - already_issued - allocated_count)
        donor_summary = [
            f"{name} ({cnt} unit{'s' if cnt > 1 else ''})"
            for _, (name, cnt) in donor_unit_map.items()
        ]
        return {
            "allocated": allocated_count,
            "already_reserved": already_reserved,
            "already_issued": already_issued,
            "still_needed": still_needed,
            "request_status": new_req_status,
            "donor_summary": donor_summary,
            "error": None,
        }

    except psycopg.errors.UniqueViolation:
        # The partial unique index caught a duplicate allocation attempt.
        return {
            "error": "A concurrent allocation claimed one or more units. Please retry.",
            "allocated": 0,
            "already_reserved": 0,
            "already_issued": 0,
            "still_needed": quantity,
            "request_status": "unknown",
            "donor_summary": [],
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "allocated": 0,
            "already_reserved": 0,
            "already_issued": 0,
            "still_needed": quantity,
            "request_status": "unknown",
            "donor_summary": [],
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

                if req_status == "cancelled":
                    return {
                        "error": "Cannot issue units for a cancelled request.",
                        "issued": 0,
                        "request_status": req_status,
                    }

                if req_status == "fulfilled":
                    return {
                        "error": "This request is already fulfilled.",
                        "issued": 0,
                        "request_status": req_status,
                    }

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

                if not reserved:
                    return {
                        "error": "No reserved units are available for issuing.",
                        "issued": 0,
                        "request_status": req_status,
                    }

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
                        """
                        UPDATE blood_unit
                        SET status = 'issued'
                        WHERE unit_id = %s
                          AND status = 'reserved'
                        RETURNING unit_id;
                        """,
                        (unit_id,),
                    )

                    if cur.fetchone() is None:
                        raise ValueError(
                            f"Blood unit {unit_id} is not in reserved status."
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
                result = cur.fetchone()

                if result is None:
                    total_issued = 0
                else:
                    total_issued = result[0]

                new_status = "fulfilled" if total_issued >= qty_requested else "partially_fulfilled"
                cur.execute(
                    "UPDATE blood_request SET status = %s WHERE request_id = %s;",
                    (new_status, request_id),
                )

            conn.commit()

        return {"issued": issued_count, "request_status": new_status, "error": None}

    except Exception as exc:
        return {"error": str(exc), "issued": 0, "request_status": "unknown"}


def get_request_allocation_demand(request_id: int) -> dict | None:
    """Return demand summary for a request (qty, reserved, issued, remaining).

    Returns None if the request does not exist.
    """
    query = """
        SELECT
            br.quantity_requested,
            br.status AS request_status,
            h.hospital_name,
            br.component,
            br.recipient_group,
            COUNT(a.allocation_id) FILTER (WHERE a.status = 'reserved') AS reserved,
            COUNT(a.allocation_id) FILTER (WHERE a.status = 'issued')   AS issued
        FROM blood_request AS br
        JOIN hospital AS h ON h.hospital_id = br.hospital_id
        LEFT JOIN allocation AS a ON a.request_id = br.request_id
        WHERE br.request_id = %s
        GROUP BY br.request_id, br.quantity_requested, br.status,
                 h.hospital_name, br.component, br.recipient_group;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (request_id,))
            row = cur.fetchone()

    if row is None:
        return None

    qty, req_status, hospital, component, group, reserved, issued = row
    return {
        "quantity_requested": qty,
        "request_status": req_status,
        "hospital_name": hospital,
        "component": component,
        "recipient_group": group,
        "already_reserved": reserved,
        "already_issued": issued,
        "remaining_demand": max(0, qty - reserved - issued),
    }


def get_allocation_history(request_id: int) -> tuple[list, list]:
    """Return allocation records for a request, including donor traceability."""
    query = """
        SELECT
            a.allocation_id,
            a.request_id,
            h.hospital_name,
            a.unit_id,
            dn.donor_id,
            dn.donor_name,
            d.donation_id,
            bu.blood_group,
            bu.component,
            bb.bank_name,
            a.status            AS allocation_status,
            a.allocated_at,
            a.issued_at,
            a.cancelled_at
        FROM allocation AS a
        JOIN blood_request AS br ON br.request_id  = a.request_id
        JOIN hospital      AS h  ON h.hospital_id  = br.hospital_id
        JOIN blood_unit    AS bu ON bu.unit_id      = a.unit_id
        JOIN donation      AS d  ON d.donation_id   = bu.donation_id
        JOIN blood_bank    AS bb ON bb.bank_id      = d.bank_id
        JOIN donor         AS dn ON dn.donor_id     = d.donor_id
        WHERE a.request_id = %s
        ORDER BY a.allocated_at DESC;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (request_id,))
            columns = ([d.name for d in cur.description] if cur.description else [])
            rows = cur.fetchall()

    return columns, rows

