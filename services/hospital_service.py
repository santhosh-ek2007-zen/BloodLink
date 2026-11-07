
"""
services/hospital_service.py — CRUD operations for the hospital table.

Implements:
- Hospital registration (INSERT)
- Hospital listing and detail lookup (SELECT)
- Hospital updates (UPDATE)
- Restricted hospital deletion (DELETE with referential integrity protection)
"""

import re
from db import get_connection


def validate_hospital_input(name: str, address: str, phone: str):
    """Validate required fields and exact 10-digit length for hospital records."""

    name = name.strip() if name else ""
    address = address.strip() if address else ""
    phone = phone.strip() if phone else ""

    if not name:
        raise ValueError("Hospital name is required.")

    if len(name) > 50:
        raise ValueError("Hospital name must be 50 characters or fewer.")

    if not address:
        raise ValueError("Hospital address is required.")

    if len(address) > 200:
        raise ValueError("Hospital address must be 200 characters or fewer.")

    if not phone:
        raise ValueError("Hospital phone number is required.")

    digits = re.sub(r"\D", "", phone)

    if len(digits) != 10:
        raise ValueError(
            f"Hospital phone number must be exactly 10 digits "
            f"(found {len(digits)})."
        )

    if not re.match(r"^[0-9\s-]+$", phone):
        raise ValueError(
            f"Invalid phone number format '{phone}'. "
            "Only digits, spaces, and hyphens are allowed."
        )

    return name, address, digits


def create_hospital(name: str, address: str, phone: str) -> int:
    """Register a new hospital in PostgreSQL."""

    clean_name, clean_address, clean_phone = validate_hospital_input(
        name, address, phone
    )

    query = """
        INSERT INTO hospital (hospital_name, address, phone)
        VALUES (%s, %s, %s)
        RETURNING hospital_id;
    """

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (clean_name, clean_address, clean_phone)
                )

                result = cur.fetchone()

                if result is None:
                    raise RuntimeError("Hospital registration failed.")

                hospital_id = result[0]

            conn.commit()
            return hospital_id

        except Exception:
            conn.rollback()
            raise


def list_hospitals(search_name: str = "") -> tuple[list, list]:
    """Return all hospitals with optional name filtering."""

    params = []
    where = ""

    if search_name.strip():
        where = "WHERE hospital_name ILIKE %s"
        params.append(f"%{search_name.strip()}%")

    query = f"""
        SELECT hospital_id, hospital_name, address, phone
        FROM hospital
        {where}
        ORDER BY hospital_name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)

            if cur.description is None:
                return [], []

            columns = [description.name for description in cur.description]
            rows = cur.fetchall()

            return columns, rows


def get_hospital_by_id(hospital_id: int) -> tuple | None:
    """Return a single hospital row by ID."""

    query = """
        SELECT hospital_id, hospital_name, address, phone
        FROM hospital
        WHERE hospital_id = %s;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (hospital_id,))
            return cur.fetchone()


def update_hospital(
    hospital_id: int,
    name: str,
    address: str,
    phone: str
) -> bool:
    """Update details of an existing hospital."""

    clean_name, clean_address, clean_phone = validate_hospital_input(
        name, address, phone
    )

    query = """
        UPDATE hospital
        SET hospital_name = %s,
            address = %s,
            phone = %s
        WHERE hospital_id = %s;
    """

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (clean_name, clean_address, clean_phone, hospital_id)
                )

                updated = cur.rowcount > 0

            conn.commit()
            return updated

        except Exception:
            conn.rollback()
            raise


def delete_hospital(hospital_id: int) -> bool:
    """
    Delete a hospital only if no blood requests reference it.

    The foreign key in blood_request protects referential integrity.
    """

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:

                # 1. Check whether the hospital exists
                cur.execute(
                    """
                    SELECT hospital_name
                    FROM hospital
                    WHERE hospital_id = %s;
                    """,
                    (hospital_id,)
                )

                row = cur.fetchone()

                if row is None:
                    raise ValueError(
                        f"Hospital #{hospital_id} not found."
                    )

                hosp_name = row[0]

                # 2. Check for dependent blood requests
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM blood_request
                    WHERE hospital_id = %s;
                    """,
                    (hospital_id,)
                )

                result = cur.fetchone()

                if result is None:
                    raise RuntimeError(
                        "Could not retrieve blood request count."
                    )

                req_count = result[0]

                if req_count > 0:
                    raise ValueError(
                        f"Cannot delete hospital '{hosp_name}' "
                        f"(ID: #{hospital_id}) because {req_count} "
                        "blood request(s) are linked to it. "
                        "Historical request records must be preserved."
                    )

                # 3. Delete the hospital
                cur.execute(
                    """
                    DELETE FROM hospital
                    WHERE hospital_id = %s;
                    """,
                    (hospital_id,)
                )

                deleted = cur.rowcount > 0

            conn.commit()
            return deleted

        except Exception:
            conn.rollback()
            raise
