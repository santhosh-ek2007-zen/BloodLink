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
# Blood banks
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
            columns = [d.name for d in cur.description]
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
            columns = [d.name for d in cur.description]
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
        if u["expiry_date"] <= u["collection_date"]:
            raise ValueError("Expiry date must be after collection date.")

    with get_connection() as conn:
        with conn.cursor() as cur:
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

