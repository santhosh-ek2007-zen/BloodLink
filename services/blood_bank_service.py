"""
services/blood_bank_service.py — CRUD operations for the blood_bank table.

Implements:
- Blood bank registration (INSERT)
- Blood bank listing & lookup (SELECT)
- Blood bank updates (UPDATE)
- Restricted blood bank deletion (DELETE with referential integrity protection)
"""

import re
from db import get_connection


def validate_blood_bank_input(name: str, address: str, phone: str):
    """Validate required fields and exact 10-digit length for blood bank records."""
    name = name.strip() if name else ""
    address = address.strip() if address else ""
    phone = phone.strip() if phone else ""

    if not name:
        raise ValueError("Blood bank name is required.")
    if len(name) > 50:
        raise ValueError("Blood bank name must be 50 characters or fewer.")
    if not address:
        raise ValueError("Blood bank address is required.")
    if len(address) > 200:
        raise ValueError("Blood bank address must be 200 characters or fewer.")
    if not phone:
        raise ValueError("Blood bank phone number is required.")

    digits = re.sub(r"\D", "", phone)
    if len(digits) != 10:
        raise ValueError(
            f"Blood bank phone number must be exactly 10 digits (found {len(digits)})."
        )
    if not re.match(r"^[0-9\s\-]+$", phone):
        raise ValueError(
            f"Invalid phone number format '{phone}'. Only digits, spaces, and hyphens are allowed."
        )

    return name, address, digits


def create_blood_bank(name: str, address: str, phone: str) -> int:
    """Register a new blood bank in PostgreSQL."""
    clean_name, clean_address, clean_phone = validate_blood_bank_input(name, address, phone)

    query = """
        INSERT INTO blood_bank (bank_name, address, phone)
        VALUES (%s, %s, %s)
        RETURNING bank_id;
    """
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(query, (clean_name, clean_address, clean_phone))
                result = cur.fetchone()

                if result is None:
                    raise RuntimeError("Blood bank registration failed.")

                bank_id = result[0]
            conn.commit()
            return bank_id
        except Exception:
            conn.rollback()
            raise


def list_blood_banks(search_name: str = "") -> tuple[list, list]:
    """Return all blood banks with optional name filtering."""
    params = []
    where = ""
    if search_name.strip():
        where = "WHERE bank_name ILIKE %s"
        params.append(f"%{search_name.strip()}%")

    query = f"""
        SELECT bank_id, bank_name, address, phone
        FROM blood_bank
        {where}
        ORDER BY bank_name;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = ([d.name for d in cur.description] if cur.description else [])
            rows = cur.fetchall()
            return columns, rows


def get_blood_bank_by_id(bank_id: int) -> tuple | None:
    """Return a single blood bank by ID."""
    query = """
        SELECT bank_id, bank_name, address, phone
        FROM blood_bank
        WHERE bank_id = %s;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (bank_id,))
            return cur.fetchone()


def update_blood_bank(bank_id: int, name: str, address: str, phone: str) -> bool:
    """Update an existing blood bank record."""
    clean_name, clean_address, clean_phone = validate_blood_bank_input(name, address, phone)

    query = """
        UPDATE blood_bank
        SET bank_name = %s,
            address   = %s,
            phone     = %s
        WHERE bank_id = %s;
    """
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(query, (clean_name, clean_address, clean_phone, bank_id))
                updated = cur.rowcount > 0
            conn.commit()
            return updated
        except Exception:
            conn.rollback()
            raise


def delete_blood_bank(bank_id: int) -> bool:
    """Delete a blood bank only if no donation records are associated with it.

    Enforces relational referential integrity:
    Foreign key fk_donation_bank prevents deletion if donations were received.
    """
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                # 1. Check if bank exists
                cur.execute("SELECT bank_name FROM blood_bank WHERE bank_id = %s;", (bank_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Blood bank #{bank_id} not found.")
                bank_name = row[0]

                # 2. Check for dependent donation records
                cur.execute("SELECT COUNT(*) FROM donation WHERE bank_id = %s;", (bank_id,))
                result = cur.fetchone()

                if result is None:
                    raise RuntimeError("Could not retrieve donation count.")

                don_count = result[0]
                if don_count > 0:
                    raise ValueError(
                        f"Cannot delete blood bank '{bank_name}' (ID: #{bank_id}) because {don_count} "
                        "donation record(s) are linked to it. Foreign-key referential integrity prevents deletion. "
                        "Historical donation records must be preserved."
                    )

                # 3. Perform delete
                cur.execute("DELETE FROM blood_bank WHERE bank_id = %s;", (bank_id,))
                deleted = cur.rowcount > 0

            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise

