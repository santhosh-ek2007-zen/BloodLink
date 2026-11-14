"""
services/inventory_service.py — Blood inventory read and management operations.
"""
from db import get_connection

VALID_COMPONENTS = ("whole_blood", "red_cells", "plasma", "platelets")
VALID_BLOOD_GROUPS = (
    "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"
)
VALID_STATUSES = (
    "under_testing", "available", "reserved",
    "issued", "rejected", "discarded", "expired",
)
def _fetch_required(cur, error_message: str):
    """Fetch one database row and raise an error if no row is returned."""
    result = cur.fetchone()
    if result is None:
        raise RuntimeError(error_message)
    return result


# ---------------------------------------------------------------------------
# Blood banks lookup
# ---------------------------------------------------------------------------

def list_blood_banks() -> list[tuple]:
    """Return all blood banks as (bank_id, bank_name, address, phone)."""
    query = """
        SELECT bank_id, bank_name, address, phone
        FROM blood_bank
        ORDER BY bank_name;
    """
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

    if bank_id is not None:
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
            bu.expiry_date - CURRENT_DATE AS days_until_expiry,
            bu.status,
            d.donation_id,
            dn.donor_name
        FROM blood_unit AS bu
        JOIN donation AS d
            ON d.donation_id = bu.donation_id
        JOIN blood_bank AS bb
            ON bb.bank_id = d.bank_id
        JOIN donor AS dn
            ON dn.donor_id = d.donor_id
        {where}
        ORDER BY bu.unit_id DESC;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)

            if cur.description is None:
                return [], []

            columns = [description.name for description in cur.description]
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
        JOIN donation AS d
            ON d.donation_id = bu.donation_id
        JOIN blood_bank AS bb
            ON bb.bank_id = d.bank_id
        JOIN donor AS dn
            ON dn.donor_id = d.donor_id
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

            if cur.description is None:
                return [], []

            columns = [description.name for description in cur.description]
            rows = cur.fetchall()

            return columns, rows


# ---------------------------------------------------------------------------
# Donation registration
# ---------------------------------------------------------------------------

def register_donation_and_units(
    donor_id: int,
    bank_id: int,
    donation_date: str,
    quantity_ml: int = 450,
    units: list[dict] | None = None,
    num_units: int | None = None,
) -> int:
    """
    Register a donation and create blood unit records atomically.

    Parameters
    ----------
    donor_id      : ID of the active donor.
    bank_id       : ID of the blood bank.
    donation_date : Date string (YYYY-MM-DD).
    quantity_ml   : Total volume collected in millilitres.
    units         : List of unit dicts. Each dict must contain:
                      component, blood_group, collection_date, expiry_date.
                    If a single dict is provided and num_units > 1, the same
                    component/blood_group/dates are replicated num_units times.
    num_units     : Optional explicit count of units to produce.
                    When provided and units contains exactly one template dict,
                    that template is replicated num_units times.
                    When units already has the correct number of entries,
                    num_units is ignored.

    Returns the new donation_id.
    """

    if quantity_ml <= 0:
        raise ValueError("Volume collected (ml) must be a positive number.")

    if not units:
        raise ValueError("At least one blood unit must be specified.")

    # If a num_units count is provided and only one template is given, replicate it.
    if num_units is not None and num_units >= 1 and len(units) == 1:
        template = units[0]
        units = [dict(template) for _ in range(num_units)]

    if not units:
        raise ValueError("Number of units produced must be at least 1.")

    for unit in units:
        if unit["component"] not in VALID_COMPONENTS:
            raise ValueError(f"Invalid component: {unit['component']!r}")

        if unit["blood_group"] not in VALID_BLOOD_GROUPS:
            raise ValueError(f"Invalid blood group: {unit['blood_group']!r}")

        if str(unit["expiry_date"]) <= str(unit["collection_date"]):
            raise ValueError(
                "Expiry date must be strictly after collection date."
            )

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:

                # Check whether the donor table has an is_active column
                cur.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'donor'
                      AND column_name = 'is_active';
                    """
                )

                has_active_column = cur.fetchone() is not None

                if has_active_column:
                    cur.execute(
                        """
                        SELECT is_active, donor_name
                        FROM donor
                        WHERE donor_id = %s;
                        """,
                        (donor_id,)
                    )

                    donor_row = cur.fetchone()

                    if donor_row is None:
                        raise ValueError(f"Donor #{donor_id} not found.")

                    if not donor_row[0]:
                        raise ValueError(
                            f"Donor #{donor_id} ('{donor_row[1]}') "
                            "is deactivated. Reactivate the donor "
                            "before registering a donation."
                        )

                # Insert donation
                cur.execute(
                    """
                    INSERT INTO donation
                        (donor_id, bank_id, donation_date, quantity_ml)
                    VALUES (%s, %s, %s, %s)
                    RETURNING donation_id;
                    """,
                    (donor_id, bank_id, donation_date, quantity_ml),
                )

                result = _fetch_required(
                    cur,
                    "Donation registration failed."
                )

                donation_id = result[0]

                # Insert blood units
                for unit in units:
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
                            unit["component"],
                            unit["blood_group"],
                            unit["collection_date"],
                            unit["expiry_date"],
                        ),
                    )

                    result = _fetch_required(
                        cur,
                        "Blood unit registration failed."
                    )

                    unit_id = result[0]

                    # Record initial status in history
                    cur.execute(
                        """
                        INSERT INTO status_history
                            (unit_id, old_status, new_status, actor, remarks)
                        VALUES (
                            %s, NULL, 'under_testing',
                            'system',
                            'Unit created on donation registration'
                        );
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
    """
    Update a blood unit's status and record it in status_history.

    Returns True if the unit was updated.
    Raises ValueError for invalid statuses or unknown units.
    """

    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status!r}")

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:

                # Fetch current status
                cur.execute(
                    """
                    SELECT status
                    FROM blood_unit
                    WHERE unit_id = %s
                    FOR UPDATE;
                    """,
                    (unit_id,)
                )

                row = cur.fetchone()

                if row is None:
                    raise ValueError(
                        f"No blood unit with unit_id={unit_id}."
                    )

                old_status = row[0]

                # Check whether the status actually changes
                if old_status == new_status:
                    updated = False
                else:
                    # Update unit
                    cur.execute(
                        """
                        UPDATE blood_unit
                        SET status = %s
                        WHERE unit_id = %s;
                        """,
                        (new_status, unit_id),
                    )

                    # Record history
                    cur.execute(
                        """
                        INSERT INTO status_history
                            (unit_id, old_status, new_status, actor, remarks)
                        VALUES (%s, %s, %s, %s, %s);
                        """,
                        (
                            unit_id,
                            old_status,
                            new_status,
                            actor,
                            remarks or None,
                        ),
                    )

                    updated = True

            conn.commit()
            return updated

        except Exception:
            conn.rollback()
            raise


# ---------------------------------------------------------------------------
# Unit Expiry Update
# ---------------------------------------------------------------------------

def update_unit_expiry(
    unit_id: int,
    new_expiry_date,
    actor: str = "staff",
    remarks: str = "",
) -> bool:
    """
    Update a blood unit's expiry date if safe.

    Restricts modifications on units that are already reserved or issued.
    Records the modification in status_history.
    """

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT collection_date, expiry_date, status
                    FROM blood_unit
                    WHERE unit_id = %s
                    FOR UPDATE;
                    """,
                    (unit_id,)
                )

                row = cur.fetchone()

                if row is None:
                    raise ValueError(
                        f"Blood unit #{unit_id} not found."
                    )

                coll_date, old_exp, current_status = row

                # Restrict modifications on reserved or issued units
                if current_status in ("reserved", "issued"):
                    raise ValueError(
                        f"Cannot modify blood unit #{unit_id} because "
                        f"its current status is '{current_status}'. "
                        "Modifications to reserved or issued units "
                        "are prohibited."
                    )

                # Validate date constraint
                if str(new_expiry_date) <= str(coll_date):
                    raise ValueError(
                        f"New expiry date ({new_expiry_date}) must be "
                        f"strictly after collection date ({coll_date})."
                    )

                # Update expiry date
                cur.execute(
                    """
                    UPDATE blood_unit
                    SET expiry_date = %s
                    WHERE unit_id = %s;
                    """,
                    (str(new_expiry_date), unit_id),
                )

                # Record modification in status history
                cur.execute(
                    """
                    INSERT INTO status_history
                        (unit_id, old_status, new_status, actor, remarks)
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (
                        unit_id,
                        current_status,
                        current_status,
                        actor,
                        remarks or (
                            f"Expiry date changed from {old_exp} "
                            f"to {new_expiry_date}"
                        ),
                    ),
                )

            conn.commit()
            return True

        except Exception:
            conn.rollback()
            raise


# ---------------------------------------------------------------------------
# Screening
# ---------------------------------------------------------------------------

def record_screening(
    unit_id: int,
    result: str,
    remarks: str = "",
    actor: str = "lab_tech",
) -> int:
    """
    Record a screening test result for a blood unit.

    Approved:
        Changes under_testing status to available.

    Rejected:
        Changes under_testing or available status to discarded.

    Also records status changes in status_history.
    """

    valid_results = ("pending", "approved", "rejected")

    if result not in valid_results:
        raise ValueError(
            f"Invalid screening result '{result}'. "
            f"Must be one of: {', '.join(valid_results)}"
        )

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:

                # 1. Verify unit exists
                cur.execute(
                    """
                    SELECT status
                    FROM blood_unit
                    WHERE unit_id = %s
                    FOR UPDATE;
                    """,
                    (unit_id,)
                )

                row = cur.fetchone()

                if row is None:
                    raise ValueError(
                        f"Blood unit #{unit_id} not found."
                    )

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

                screening_row = _fetch_required(
                    cur,
                    "Screening record creation failed."
                )

                screening_id = screening_row[0]

                # 3. Determine the new status
                new_status = old_status

                if result == "approved" and old_status == "under_testing":
                    new_status = "available"

                elif result == "rejected" and old_status in (
                    "under_testing", "available"
                ):
                    new_status = "discarded"

                # 4. Update status and record history if required
                if new_status != old_status:
                    cur.execute(
                        """
                        UPDATE blood_unit
                        SET status = %s
                        WHERE unit_id = %s;
                        """,
                        (new_status, unit_id),
                    )

                    cur.execute(
                        """
                        INSERT INTO status_history
                            (unit_id, old_status, new_status, actor, remarks)
                        VALUES (%s, %s, %s, %s, %s);
                        """,
                        (
                            unit_id,
                            old_status,
                            new_status,
                            actor,
                            f"Screening result: {result}. {remarks}".strip(),
                        ),
                    )

            conn.commit()
            return screening_id

        except Exception:
            conn.rollback()
            raise


# ---------------------------------------------------------------------------
# Restricted Delete
# ---------------------------------------------------------------------------

def delete_blood_unit(unit_id: int) -> bool:
    """
    Delete a blood unit only if no screening or allocation records exist.

    If allocation or screening records exist, physical deletion is prohibited.
    The user should update the unit status to 'discarded' or 'expired' instead.
    """

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:

                # 1. Check whether the unit exists
                cur.execute(
                    """
                    SELECT status
                    FROM blood_unit
                    WHERE unit_id = %s;
                    """,
                    (unit_id,)
                )

                row = cur.fetchone()

                if row is None:
                    raise ValueError(
                        f"Blood unit #{unit_id} not found."
                    )

                # 2. Count dependent allocation records
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM allocation
                    WHERE unit_id = %s;
                    """,
                    (unit_id,)
                )

                result = _fetch_required(
                    cur,
                    "Could not retrieve allocation count."
                )

                alloc_count = result[0]

                # 3. Count dependent screening records
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM screening
                    WHERE unit_id = %s;
                    """,
                    (unit_id,)
                )

                result = _fetch_required(
                    cur,
                    "Could not retrieve screening count."
                )

                screen_count = result[0]

                # 4. Prevent deletion if dependent records exist
                if alloc_count > 0 or screen_count > 0:
                    raise ValueError(
                        f"Cannot physically delete blood unit #{unit_id} "
                        f"because {screen_count} screening record(s) "
                        f"and {alloc_count} allocation record(s) exist. "
                        "Historical records must be preserved. "
                        "You may update the unit status to "
                        "'discarded' or 'expired' instead."
                    )

                # 5. Delete status history and blood unit
                cur.execute(
                    """
                    DELETE FROM status_history
                    WHERE unit_id = %s;
                    """,
                    (unit_id,)
                )

                cur.execute(
                    """
                    DELETE FROM blood_unit
                    WHERE unit_id = %s;
                    """,
                    (unit_id,)
                )

                deleted = cur.rowcount > 0

            conn.commit()
            return deleted

        except Exception:
            conn.rollback()
            raise
