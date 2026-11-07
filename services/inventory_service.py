"""
services/inventory_service.py — Blood inventory read and management operations.
"""

from db import get_connection

VALID_COMPONENTS = ("whole_blood", "red_cells", "plasma", "platelets")
VALID_BLOOD_GROUPS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")
VALID_STATUSES = (
    "under_testing", "available", "reserved",
    "issued", "rejected", "discarded", "expired",
)


# ---------------------------------------------------------------------------
# Blood banks lookup
# ---------------------------------------------------------------------------

def list_blood_banks() -> list[tuple]:
    """Return all blood banks as (bank_id, bank_name, address, phone)."""
    query = "SELECT bank_id, bank_name, address, phone FROM blood_bank ORDER BY bank_name;"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()


# ---------------------------------------------------------------------------
# Inventory views
# ---------------------------------------------------------------------------

def list_inventory(
    blood_group: str = "",
    component: str = "",
    bank_id: int | None = None,
    status: str = "",
) -> tuple[list, list]:
    """Return blood units with optional filters."""
    conditions = []
    params: list = []

    if blood_group:
        conditions.append("bu.blood_group = %s")
        params.append(blood_group)

    if component:
        conditions.append("bu.component = %s")
        params.append(component)

    if bank_id:
        conditions.append("d.bank_id = %s")
        params.append(bank_id)

    if status:
        conditions.append("bu.status = %s")
        params.append(status)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    query = f"""
        SELECT
            bu.unit_id,
            bb.bank_name,
            bu.component,
            bu.blood_group,
            bu.collection_date,
            bu.expiry_date,
            bu.expiry_date - CURRENT_DATE   AS days_until_expiry,
            bu.status,
            d.donation_id,
            dn.donor_name
        FROM blood_unit AS bu
        JOIN donation   AS d   ON d.donation_id  = bu.donation_id
        JOIN blood_bank AS bb  ON bb.bank_id      = d.bank_id
        JOIN donor      AS dn  ON dn.donor_id     = d.donor_id
        {where}
        ORDER BY bu.unit_id DESC;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = ([d.name for d in cur.description] if cur.description else [])
            rows = cur.fetchall()

    return columns, rows


def get_unit_detail(unit_id: int) -> tuple | None:
    """Return full details for a single blood unit."""
    query = """
        SELECT
            bu.unit_id,
            bb.bank_name,
            dn.donor_name,
            d.donation_date,
            bu.component,
            bu.blood_group,
            bu.collection_date,
            bu.expiry_date,
            bu.expiry_date - CURRENT_DATE AS days_until_expiry,
            bu.status
        FROM blood_unit AS bu
        JOIN donation   AS d   ON d.donation_id  = bu.donation_id
        JOIN blood_bank AS bb  ON bb.bank_id      = d.bank_id
        JOIN donor      AS dn  ON dn.donor_id     = d.donor_id
        WHERE bu.unit_id = %s;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (unit_id,))
            return cur.fetchone()


def get_unit_screening_history(unit_id: int) -> tuple[list, list]:
    """Return all screening records for a unit."""
    query = """
        SELECT screening_id, screening_date, result, remarks
        FROM screening
        WHERE unit_id = %s
        ORDER BY screening_date DESC, screening_id DESC;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (unit_id,))
            columns = ([d.name for d in cur.description] if cur.description else [])
            rows = cur.fetchall()

    return columns, rows


# ---------------------------------------------------------------------------
# Donation registration
# ---------------------------------------------------------------------------

def register_donation_and_units(
    donor_id: int,
    bank_id: int,
    donation_date: str,
    quantity_ml: int,
    units: list[dict],
) -> int:
    """Register a donation and create blood unit records atomically.

    Parameters
    ----------
    units : list of dict, each with keys:
        component, blood_group, collection_date, expiry_date

    Returns the new donation_id.
    """
    if quantity_ml <= 0:
        raise ValueError("Quantity must be a positive number of ml.")
    if not units:
        raise ValueError("At least one blood unit must be specified.")

    for u in units:
        if u["component"] not in VALID_COMPONENTS:
            raise ValueError(f"Invalid component: {u['component']!r}")
        if u["blood_group"] not in VALID_BLOOD_GROUPS:
            raise ValueError(f"Invalid blood group: {u['blood_group']!r}")
        if str(u["expiry_date"]) <= str(u["collection_date"]):
            raise ValueError("Expiry date must be strictly after collection date.")

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                # Check if donor is active (if is_active column exists)
                cur.execute(
                    "SELECT 1 FROM information_schema.columns WHERE table_name = 'donor' AND column_name = 'is_active';"
                )
                if cur.fetchone():
                    cur.execute("SELECT is_active, donor_name FROM donor WHERE donor_id = %s;", (donor_id,))
                    d_row = cur.fetchone()
                    if d_row and not d_row[0]:
                        raise ValueError(f"Donor #{donor_id} ('{d_row[1]}') is deactivated. Reactivate the donor before registering a donation.")

                # Insert donation
                cur.execute(
                    """
                    INSERT INTO donation (donor_id, bank_id, donation_date, quantity_ml)
                    VALUES (%s, %s, %s, %s)
                    RETURNING donation_id;
                    """,
                    (donor_id, bank_id, donation_date, quantity_ml),
                )
                donation_id = cur.fetchone()[0]

                # Insert blood units
                for u in units:
                    cur.execute(
                        """
                        INSERT INTO blood_unit
                            (donation_id, component, blood_group,
                             collection_date, expiry_date, status)
                        VALUES (%s, %s, %s, %s, %s, 'under_testing')
                        RETURNING unit_id;
                        """,
                        (
                            donation_id,
                            u["component"],
                            u["blood_group"],
                            u["collection_date"],
                            u["expiry_date"],
                        ),
                    )
                    unit_id = cur.fetchone()[0]

                    # Record initial status in history
                    cur.execute(
                        """
                        INSERT INTO status_history
                            (unit_id, old_status, new_status, actor, remarks)
                        VALUES (%s, NULL, 'under_testing', 'system', 'Unit created on donation registration');
                        """,
                        (unit_id,),
                    )

            conn.commit()
            return donation_id
        except Exception:
            conn.rollback()
            raise


# ---------------------------------------------------------------------------
# Status update
# ---------------------------------------------------------------------------

def update_unit_status(
    unit_id: int,
    new_status: str,
    actor: str = "staff",
    remarks: str = "",
) -> bool:
    """Update a blood unit's status and record it in status_history.

    Returns True if the unit was updated.
    Raises ValueError for invalid transitions or unknown unit.
    """
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status!r}")

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                # Fetch current status
                cur.execute(
                    "SELECT status FROM blood_unit WHERE unit_id = %s FOR UPDATE;",
                    (unit_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(f"No blood unit with unit_id={unit_id}.")

                old_status = row[0]

                if old_status == new_status:
                    return False  # No change needed

                # Update unit
                cur.execute(
                    "UPDATE blood_unit SET status = %s WHERE unit_id = %s;",
                    (new_status, unit_id),
                )

                # Record history
                cur.execute(
                    """
                    INSERT INTO status_history
                        (unit_id, old_status, new_status, actor, remarks)
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (unit_id, old_status, new_status, actor, remarks or None),
                )

            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise


# ---------------------------------------------------------------------------
# Unit Expiry Update & Restricted Delete
# ---------------------------------------------------------------------------

def update_unit_expiry(
    unit_id: int,
    new_expiry_date,
    actor: str = "staff",
    remarks: str = "",
) -> bool:
    """Update a blood unit's expiry date if safe.

    Restricts modifications on units that are already reserved or issued.
    Enforces check constraint chk_blood_unit_dates (expiry_date > collection_date).
    Records the modification in status_history.
    """
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT collection_date, expiry_date, status FROM blood_unit WHERE unit_id = %s FOR UPDATE;",
                    (unit_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Blood unit #{unit_id} not found.")

                coll_date, old_exp, current_status = row

                # Restrict modifications on reserved or issued units
                if current_status in ("reserved", "issued"):
                    raise ValueError(
                        f"Cannot modify blood unit #{unit_id} because its current status is '{current_status}'. "
                        "Modifications to units that are already reserved or issued are prohibited to maintain allocation integrity."
                    )

                # Validate date constraint
                if str(new_expiry_date) <= str(coll_date):
                    raise ValueError(f"New expiry date ({new_expiry_date}) must be strictly after collection date ({coll_date}).")

                # Perform update
                cur.execute(
                    "UPDATE blood_unit SET expiry_date = %s WHERE unit_id = %s;",
                    (str(new_expiry_date), unit_id),
                )

                # Log modification in status_history
                cur.execute(
                    """
                    INSERT INTO status_history (unit_id, old_status, new_status, actor, remarks)
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (
                        unit_id,
                        current_status,
                        current_status,
                        actor,
                        remarks or f"Expiry date changed from {old_exp} to {new_expiry_date}",
                    ),
                )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise


def record_screening(
    unit_id: int,
    result: str,
    remarks: str = "",
    actor: str = "lab_tech",
) -> int:
    """Record a screening test result for a blood unit.

    If result == 'approved', updates blood_unit.status to 'available' if currently 'under_testing'.
    If result == 'rejected', updates blood_unit.status to 'discarded'.
    Also logs the audit entry in status_history.
    """
    valid_results = ("pending", "approved", "rejected")
    if result not in valid_results:
        raise ValueError(f"Invalid screening result '{result}'. Must be one of: {', '.join(valid_results)}")

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                # 1. Verify unit exists
                cur.execute("SELECT status FROM blood_unit WHERE unit_id = %s FOR UPDATE;", (unit_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Blood unit #{unit_id} not found.")
                old_status = row[0]

                # 2. Insert screening record
                cur.execute(
                    """
                    INSERT INTO screening (unit_id, result, remarks)
                    VALUES (%s, %s, %s)
                    RETURNING screening_id;
                    """,
                    (unit_id, result, remarks or None),
                )
                screening_id = cur.fetchone()[0]

                # 3. Synchronize unit status
                new_status = old_status
                if result == "approved" and old_status == "under_testing":
                    new_status = "available"
                elif result == "rejected" and old_status in ("under_testing", "available"):
                    new_status = "discarded"

                if new_status != old_status:
                    cur.execute(
                        "UPDATE blood_unit SET status = %s WHERE unit_id = %s;",
                        (new_status, unit_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO status_history (unit_id, old_status, new_status, actor, remarks)
                        VALUES (%s, %s, %s, %s, %s);
                        """,
                        (unit_id, old_status, new_status, actor, f"Screening result: {result}. {remarks}".strip()),
                    )

            conn.commit()
            return screening_id
        except Exception:
            conn.rollback()
            raise


def record_screening(
    unit_id: int,
    result: str,
    remarks: str = "",
    actor: str = "lab_tech",
) -> int:
    """Record a screening test result for a blood unit.

    If result == 'approved', updates blood_unit.status to 'available' if currently 'under_testing'.
    If result == 'rejected', updates blood_unit.status to 'discarded'.
    Also logs the audit entry in status_history.
    """
    valid_results = ("pending", "approved", "rejected")
    if result not in valid_results:
        raise ValueError(f"Invalid screening result '{result}'. Must be one of: {', '.join(valid_results)}")

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                # 1. Verify unit exists
                cur.execute("SELECT status FROM blood_unit WHERE unit_id = %s FOR UPDATE;", (unit_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Blood unit #{unit_id} not found.")
                old_status = row[0]

                # 2. Insert screening record
                cur.execute(
                    """
                    INSERT INTO screening (unit_id, result, remarks)
                    VALUES (%s, %s, %s)
                    RETURNING screening_id;
                    """,
                    (unit_id, result, remarks or None),
                )
                screening_id = cur.fetchone()[0]

                # 3. Synchronize unit status
                new_status = old_status
                if result == "approved" and old_status == "under_testing":
                    new_status = "available"
                elif result == "rejected" and old_status in ("under_testing", "available"):
                    new_status = "discarded"

                if new_status != old_status:
                    cur.execute(
                        "UPDATE blood_unit SET status = %s WHERE unit_id = %s;",
                        (new_status, unit_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO status_history (unit_id, old_status, new_status, actor, remarks)
                        VALUES (%s, %s, %s, %s, %s);
                        """,
                        (unit_id, old_status, new_status, actor, f"Screening result: {result}. {remarks}".strip()),
                    )

            conn.commit()
            return screening_id
        except Exception:
            conn.rollback()
            raise


def delete_blood_unit(unit_id: int) -> bool:
    """Delete a blood unit only if no screening or allocation records exist.

    If allocation or screening records exist, physical deletion is prohibited
    to preserve historical data. The user should update the unit status to
    'discarded' or 'expired' instead.
    """
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                # 1. Check if unit exists
                cur.execute("SELECT status FROM blood_unit WHERE unit_id = %s;", (unit_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Blood unit #{unit_id} not found.")

                # 2. Check for dependent allocation records
                cur.execute("SELECT COUNT(*) FROM allocation WHERE unit_id = %s;", (unit_id,))
                alloc_count = cur.fetchone()[0]

                # 3. Check for dependent screening records
                cur.execute("SELECT COUNT(*) FROM screening WHERE unit_id = %s;", (unit_id,))
                screen_count = cur.fetchone()[0]

                if alloc_count > 0 or screen_count > 0:
                    raise ValueError(
                        f"Cannot physically delete blood unit #{unit_id} because {screen_count} screening record(s) "
                        f"and {alloc_count} allocation record(s) exist. Medical audit integrity requires this history "
                        "to be preserved. You may update the unit status to 'discarded' or 'expired' instead."
                    )

                # 4. Clean up status history for this unit and delete
                cur.execute("DELETE FROM status_history WHERE unit_id = %s;", (unit_id,))
                cur.execute("DELETE FROM blood_unit WHERE unit_id = %s;", (unit_id,))
                deleted = cur.rowcount > 0

            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
