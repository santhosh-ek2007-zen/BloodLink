"""
services/donor_service.py — CRUD operations and validations for the donor table.

Provides input validation, duplicate prevention, transaction safety,
data privacy protection (contact masking), deactivation, and restricted deletion.
"""

import re
import psycopg
from db import get_connection

VALID_BLOOD_GROUPS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")


# ── Input Validation Helpers ────────────────────────────────────────────────

def validate_name(name: str) -> str:
    """Validate donor name.
    Must be 2-50 characters, letters, spaces, hyphens, or periods only.
    """
    cleaned = name.strip() if name else ""
    if not cleaned:
        raise ValueError("Donor name is required.")
    if len(cleaned) < 2:
        raise ValueError("Donor name must be at least 2 characters long.")
    if len(cleaned) > 50:
        raise ValueError("Donor name must be 50 characters or fewer.")
    if not re.match(r"^[A-Za-z\s\.\-']+$", cleaned):
        raise ValueError("Donor name should only contain letters, spaces, hyphens, or periods.")
    return cleaned


def validate_phone(phone: str) -> str:
    """Validate and clean phone number.
    Ensures the phone number contains exactly 10 digits.
    """
    cleaned = phone.strip() if phone else ""
    if not cleaned:
        raise ValueError("Phone number is required.")
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) != 10:
        raise ValueError(
            f"Invalid phone number '{cleaned}'. Phone number must be exactly 10 digits (found {len(digits)})."
        )
    if not re.match(r"^[0-9\s\-]+$", cleaned):
        raise ValueError(
            f"Invalid phone number format '{cleaned}'. Only digits, spaces, and hyphens are allowed."
        )
    return digits


def validate_blood_group(blood_group: str) -> str:
    """Ensure blood group matches allowed database CHECK constraint values."""
    if not blood_group:
        raise ValueError("Blood group is required.")
    if blood_group not in VALID_BLOOD_GROUPS:
        raise ValueError(
            f"Invalid blood group '{blood_group}'. Must be one of: {', '.join(VALID_BLOOD_GROUPS)}."
        )
    return blood_group


def mask_phone(phone: str) -> str:
    """Mask phone number for privacy protection, e.g. '9000000001' -> '******0001'."""
    if not phone:
        return "—"
    cleaned = phone.strip()
    if len(cleaned) <= 4:
        return "****"
    return "*" * (len(cleaned) - 4) + cleaned[-4:]


# ── Database Operations ─────────────────────────────────────────────────────

def check_duplicate_phone(phone: str) -> tuple[int, str] | None:
    """Check if a donor with the given phone number already exists in PostgreSQL.
    Returns (donor_id, donor_name) if found, else None.
    """
    clean_phone = validate_phone(phone)
    query = "SELECT donor_id, donor_name FROM donor WHERE phone = %s;"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (clean_phone,))
            return cur.fetchone()


def register_donor(
    name: str,
    phone: str,
    blood_group: str,
    location: str = "",
) -> int:
    """Insert a new donor into PostgreSQL with transaction safety.

    Validates all inputs, prevents duplicate phone registration,
    and returns the database-generated donor_id.
    """
    clean_name = validate_name(name)
    clean_phone = validate_phone(phone)
    clean_bg = validate_blood_group(blood_group)
    clean_loc = location.strip() if location else None

    if clean_loc and len(clean_loc) > 100:
        raise ValueError("Location must be 100 characters or fewer.")

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                # 1. Check for existing duplicate phone
                cur.execute(
                    "SELECT donor_id, donor_name FROM donor WHERE phone = %s;",
                    (clean_phone,),
                )
                existing = cur.fetchone()
                if existing:
                    raise ValueError(
                        f"Duplicate Registration: A donor with phone '{clean_phone}' is already registered "
                        f"(Donor ID: {existing[0]}, Name: {existing[1]})."
                    )

                # 2. Parameterized insert letting PostgreSQL generate donor_id
                query = """
                    INSERT INTO donor (donor_name, phone, blood_group, location)
                    VALUES (%s, %s, %s, %s)
                    RETURNING donor_id;
                """
                cur.execute(query, (clean_name, clean_phone, clean_bg, clean_loc))
                row = cur.fetchone()
                if not row:
                    raise RuntimeError("Database failed to return generated donor_id.")
                donor_id = row[0]

            conn.commit()
            return donor_id
        except Exception:
            conn.rollback()
            raise


def list_donors(
    search_name: str = "",
    blood_group: str = "",
    location: str = "",
    mask_contacts: bool = True,
    active_only: bool = False,
) -> tuple[list, list]:
    """Return registered donors from PostgreSQL with optional filtering and privacy masking."""
    conditions = []
    params: list = []

    if search_name.strip():
        conditions.append("donor_name ILIKE %s")
        params.append(f"%{search_name.strip()}%")

    if blood_group and blood_group in VALID_BLOOD_GROUPS:
        conditions.append("blood_group = %s")
        params.append(blood_group)

    if location.strip():
        conditions.append("location ILIKE %s")
        params.append(f"%{location.strip()}%")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    query = f"""
        SELECT
            donor_id,
            donor_name,
            blood_group,
            location,
            phone,
            COALESCE(is_active, TRUE) AS is_active
        FROM donor
        {where}
        ORDER BY donor_id DESC;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            # First check if is_active column exists
            cur.execute(
                """
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'donor' AND column_name = 'is_active';
                """
            )
            has_is_active = cur.fetchone() is not None

            if not has_is_active:
                # Fallback query if column hasn't been migrated yet
                fallback_query = f"""
                    SELECT
                        donor_id,
                        donor_name,
                        blood_group,
                        location,
                        phone,
                        TRUE AS is_active
                    FROM donor
                    {where}
                    ORDER BY donor_id DESC;
                """
                cur.execute(fallback_query, params)
            else:
                if active_only:
                    active_cond = "is_active = TRUE"
                    where_clause = f"{where} AND {active_cond}" if where else f"WHERE {active_cond}"
                    active_query = f"""
                        SELECT
                            donor_id,
                            donor_name,
                            blood_group,
                            location,
                            phone,
                            is_active
                        FROM donor
                        {where_clause}
                        ORDER BY donor_id DESC;
                    """
                    cur.execute(active_query, params)
                else:
                    cur.execute(query, params)

            columns = ([d.name for d in cur.description] if cur.description else [])
            raw_rows = cur.fetchall()

    if mask_contacts:
        processed_rows = []
        for r in raw_rows:
            # (donor_id, donor_name, blood_group, location, phone, is_active)
            masked_r = (r[0], r[1], r[2], r[3], mask_phone(r[4]), r[5])
            processed_rows.append(masked_r)
        return columns, processed_rows

    return columns, raw_rows


def get_donor_by_id(donor_id: int) -> tuple | None:
    """Return a single donor row by primary key or None."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'donor' AND column_name = 'is_active';
                """
            )
            has_is_active = cur.fetchone() is not None

            if has_is_active:
                cur.execute(
                    """
                    SELECT donor_id, donor_name, phone, blood_group, location, is_active
                    FROM donor
                    WHERE donor_id = %s;
                    """,
                    (donor_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT donor_id, donor_name, phone, blood_group, location, TRUE AS is_active
                    FROM donor
                    WHERE donor_id = %s;
                    """,
                    (donor_id,),
                )
            return cur.fetchone()


def get_donation_history(donor_id: int) -> tuple[list, list]:
    """Return all donations and blood units for a donor."""
    query = """
        SELECT
            dn.donation_id,
            bb.bank_name,
            dn.donation_date,
            dn.quantity_ml,
            bu.unit_id,
            bu.component,
            bu.blood_group,
            bu.status,
            bu.expiry_date
        FROM donation AS dn
        JOIN blood_bank AS bb ON bb.bank_id = dn.bank_id
        LEFT JOIN blood_unit AS bu ON bu.donation_id = dn.donation_id
        WHERE dn.donor_id = %s
        ORDER BY dn.donation_date DESC, bu.unit_id;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (donor_id,))
            columns = ([d.name for d in cur.description] if cur.description else [])
            rows = cur.fetchall()

    return columns, rows


def update_donor(
    donor_id: int,
    name: str,
    phone: str,
    blood_group: str,
    location: str = "",
) -> bool:
    """Update an existing donor in PostgreSQL with validation."""
    clean_name = validate_name(name)
    clean_phone = validate_phone(phone)
    clean_bg = validate_blood_group(blood_group)
    clean_loc = location.strip() if location else None

    if clean_loc and len(clean_loc) > 100:
        raise ValueError("Location must be 100 characters or fewer.")

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                # Ensure phone is not taken by another donor
                cur.execute(
                    "SELECT donor_id FROM donor WHERE phone = %s AND donor_id <> %s;",
                    (clean_phone, donor_id),
                )
                if cur.fetchone():
                    raise ValueError(f"Phone number '{clean_phone}' is already registered to another donor.")

                query = """
                    UPDATE donor
                    SET donor_name  = %s,
                        phone       = %s,
                        blood_group = %s,
                        location    = %s
                    WHERE donor_id = %s;
                """
                cur.execute(query, (clean_name, clean_phone, clean_bg, clean_loc, donor_id))
                updated = cur.rowcount
            conn.commit()
            return updated > 0
        except Exception:
            conn.rollback()
            raise


def deactivate_donor(donor_id: int) -> bool:
    """Set donor status to inactive (logical deactivation)."""
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE donor SET is_active = FALSE WHERE donor_id = %s;", (donor_id,))
                updated = cur.rowcount > 0
            conn.commit()
            return updated
        except Exception:
            conn.rollback()
            raise


def reactivate_donor(donor_id: int) -> bool:
    """Set donor status to active (logical reactivation)."""
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE donor SET is_active = TRUE WHERE donor_id = %s;", (donor_id,))
                updated = cur.rowcount > 0
            conn.commit()
            return updated
        except Exception:
            conn.rollback()
            raise


def delete_donor(donor_id: int) -> bool:
    """Physically delete a donor ONLY if no donation records exist.
    Preserves medical and transaction history.
    """
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                # 1. Check if donor exists
                cur.execute("SELECT donor_name FROM donor WHERE donor_id = %s;", (donor_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Donor #{donor_id} not found.")
                donor_name = row[0]

                # 2. Check for dependent donation records
                cur.execute("SELECT COUNT(*) FROM donation WHERE donor_id = %s;", (donor_id,))
                result = cur.fetchone()

                if result is None:
                    raise RuntimeError("Could not retrieve donation count.")

                don_count = result[0]
                if don_count > 0:
                    raise ValueError(
                        f"Cannot delete donor #{donor_id} ('{donor_name}') because {don_count} donation "
                        "record(s) exist. Medical donation history must be preserved. "
                        "You may deactivate the donor instead to prevent future donations."
                    )

                # 3. Safe physical deletion
                cur.execute("DELETE FROM donor WHERE donor_id = %s;", (donor_id,))
                deleted = cur.rowcount > 0

            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
