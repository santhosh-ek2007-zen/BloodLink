"""
services/request_service.py — Blood request creation and retrieval.
"""

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
            columns = [d.name for d in cur.description]
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


def cancel_request(request_id: int) -> bool:
    """Cancel a pending or partially-fulfilled request.

    Returns True if the request was updated, False if not found or
    already in a terminal state.
    """
    query = """
        UPDATE blood_request
        SET status = 'cancelled'
        WHERE request_id = %s
          AND status IN ('pending', 'partially_fulfilled')
        RETURNING request_id;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (request_id,))
            updated = cur.fetchone()
        conn.commit()

    return updated is not None

