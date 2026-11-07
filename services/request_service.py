"""
services/request_service.py — Blood request creation, retrieval, updates, and cancellation.
"""
import psycopg
from db import get_connection

VALID_COMPONENTS  = ("whole_blood", "red_cells", "plasma", "platelets")
VALID_GROUPS      = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")
VALID_URGENCIES   = ("normal", "urgent", "emergency")
VALID_STATUSES    = ("pending", "partially_fulfilled", "fulfilled", "cancelled")


def list_hospitals() -> list[tuple]:
    """Return all hospitals as (hospital_id, hospital_name, address)."""
    query = "SELECT hospital_id, hospital_name, address FROM hospital ORDER BY hospital_name;"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()


def list_requests(
    status: str = "",
    hospital_id: int | None = None,
    component: str = "",
) -> tuple[list, list]:
    """Return blood requests with optional filters."""
    conditions = []
    params: list = []

    if status:
        conditions.append("br.status = %s")
        params.append(status)

    if hospital_id:
        conditions.append("br.hospital_id = %s")
        params.append(hospital_id)

    if component:
        conditions.append("br.component = %s")
        params.append(component)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    query = f"""
        SELECT
            br.request_id,
            h.hospital_name,
            br.component,
            br.recipient_group,
            br.quantity_requested,
            br.urgency,
            br.request_date,
            br.status,

            COUNT(a.allocation_id) FILTER (WHERE a.status = 'issued')   AS issued_units,
            COUNT(a.allocation_id) FILTER (WHERE a.status = 'reserved') AS reserved_units,

            GREATEST(
                br.quantity_requested
                - COUNT(a.allocation_id) FILTER (WHERE a.status IN ('reserved', 'issued')),
                0
            ) AS still_needed

        FROM blood_request AS br
        JOIN hospital AS h ON h.hospital_id = br.hospital_id
        LEFT JOIN allocation AS a ON a.request_id = br.request_id
        {where}
        GROUP BY
            br.request_id, h.hospital_name, br.component,
            br.recipient_group, br.quantity_requested,
            br.urgency, br.request_date, br.status
        ORDER BY br.request_date DESC, br.request_id DESC;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = ([d.name for d in cur.description] if cur.description else [])
            rows = cur.fetchall()

    return columns, rows


def get_request_detail(request_id: int) -> tuple | None:
    """Return a single blood request row or None."""
    query = """
        SELECT
            br.request_id,
            h.hospital_name,
            h.address AS hospital_address,
            h.phone   AS hospital_phone,
            br.component,
            br.recipient_group,
            br.quantity_requested,
            br.urgency,
            br.request_date,
            br.status
        FROM blood_request AS br
        JOIN hospital AS h ON h.hospital_id = br.hospital_id
        WHERE br.request_id = %s;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (request_id,))
            return cur.fetchone()


def create_request(
    hospital_id: int,
    component: str,
    recipient_group: str,
    quantity_requested: int,
    urgency: str,
) -> int:
    """Insert a new blood request and return its request_id.

    Raises ValueError for invalid input.
    """
    if component not in VALID_COMPONENTS:
        raise ValueError(f"Invalid component: {component!r}")
    if recipient_group not in VALID_GROUPS:
        raise ValueError(f"Invalid blood group: {recipient_group!r}")
    if quantity_requested <= 0:
        raise ValueError("Quantity must be at least 1.")
    if urgency not in VALID_URGENCIES:
        raise ValueError(f"Invalid urgency: {urgency!r}")

    query = """
        INSERT INTO blood_request
            (hospital_id, component, recipient_group,
             quantity_requested, urgency, status)
        VALUES (%s, %s, %s, %s, %s, 'pending')
        RETURNING request_id;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (hospital_id, component, recipient_group,
                 quantity_requested, urgency),
            )
            request_id = cur.fetchone()[0]
        conn.commit()

    return request_id


def update_request(
    request_id: int,
    quantity_requested: int,
    urgency: str,
) -> bool:
    """Update quantity and urgency for an unallocated pending request.

    Restricts modifications once units have been allocated or if request is closed.
    """
    if quantity_requested <= 0:
        raise ValueError("Quantity requested must be at least 1.")
    if urgency not in VALID_URGENCIES:
        raise ValueError(f"Invalid urgency: {urgency!r}")

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                # 1. Check request status
                cur.execute(
                    "SELECT status FROM blood_request WHERE request_id = %s FOR UPDATE;",
                    (request_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Blood request #{request_id} not found.")

                status = row[0]
                if status != "pending":
                    raise ValueError(
                        f"Cannot modify blood request #{request_id} because its status is '{status}'. "
                        "Modifications are only permitted on 'pending' requests."
                    )

                # 2. Check for active allocations
                cur.execute(
                    "SELECT COUNT(*) FROM allocation WHERE request_id = %s AND status IN ('reserved', 'issued');",
                    (request_id,),
                )
                alloc_count = cur.fetchone()[0]
                if alloc_count > 0:
                    raise ValueError(
                        f"Cannot modify blood request #{request_id} because {alloc_count} unit(s) are already allocated to it. "
                        "Cancel the request or allocate additional units instead."
                    )

                # 3. Perform update
                cur.execute(
                    """
                    UPDATE blood_request
                    SET quantity_requested = %s,
                        urgency            = %s
                    WHERE request_id = %s;
                    """,
                    (quantity_requested, urgency, request_id),
                )
                updated = cur.rowcount > 0

            conn.commit()
            return updated
        except Exception:
            conn.rollback()
            raise


def cancel_request(request_id: int) -> bool:
    """Cancel a pending or partially-fulfilled request.

    In a single transaction:
    1. Finds all 'reserved' allocations for this request.
    2. Cancels those allocations (status='cancelled', cancelled_at=CURRENT_TIMESTAMP).
    3. Reverts the corresponding units in blood_unit back to status='available'.
    4. Audits the unit status reversion in status_history.
    5. Sets blood_request.status to 'cancelled'.
    """
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                # 1. Verify request is cancellable
                cur.execute(
                    """
                    SELECT status FROM blood_request
                    WHERE request_id = %s
                    FOR UPDATE;
                    """,
                    (request_id,),
                )
                req = cur.fetchone()
                if not req or req[0] not in ('pending', 'partially_fulfilled'):
                    return False

                # 2. Find and cancel all reserved allocations
                cur.execute(
                    """
                    UPDATE allocation
                    SET status = 'cancelled',
                        cancelled_at = CURRENT_TIMESTAMP
                    WHERE request_id = %s AND status = 'reserved'
                    RETURNING unit_id;
                    """,
                    (request_id,),
                )
                cancelled_units = [row[0] for row in cur.fetchall()]

                # 3. Revert each reserved unit back to 'available' and record status_history
                for unit_id in cancelled_units:
                    cur.execute(
                        """
                        UPDATE blood_unit
                        SET status = 'available'
                        WHERE unit_id = %s;
                        """,
                        (unit_id,),
                    )
                    cur.execute(
                        """
                        INSERT INTO status_history (unit_id, old_status, new_status, reason)
                        VALUES (%s, 'reserved', 'available', %s);
                        """,
                        (unit_id, f"Released back to available: Request #{request_id} was cancelled."),
                    )

                # 4. Mark request as cancelled
                cur.execute(
                    """
                    UPDATE blood_request
                    SET status = 'cancelled'
                    WHERE request_id = %s;
                    """,
                    (request_id,),
                )

            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise


def delete_request(request_id: int) -> bool:
    """Delete a blood request only if no allocation records exist.

    Preserves allocation and issue history for medical audit integrity.
    """
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                # 1. Check if request exists
                cur.execute("SELECT status FROM blood_request WHERE request_id = %s;", (request_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Blood request #{request_id} not found.")

                # 2. Check for dependent allocation records
                cur.execute(
                    "SELECT COUNT(*) FROM allocation WHERE request_id = %s;",
                    (request_id,),
                )
                alloc_count = cur.fetchone()[0]
                if alloc_count > 0:
                    raise ValueError(
                        f"Cannot delete blood request #{request_id} because {alloc_count} allocation record(s) exist. "
                        "Foreign-key referential integrity and audit requirements require this history to be preserved. "
                        "You may cancel the request instead."
                    )

                # 3. Safe deletion
                cur.execute("DELETE FROM blood_request WHERE request_id = %s;", (request_id,))
                deleted = cur.rowcount > 0

            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
