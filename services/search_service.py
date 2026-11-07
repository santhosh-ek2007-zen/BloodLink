"""
services/search_service.py — Read-only blood availability search.

This module identifies candidate blood units for a given recipient
blood group, component, and optional location.

IMPORTANT SAFETY NOTE
---------------------
Results returned by this module are database candidates only.
They do not constitute clinical authorisation for transfusion.
Final compatibility verification and release decisions must follow
applicable blood-bank and clinical protocols.
"""

from db import get_connection


# Components present in the schema CHECK constraint.
VALID_COMPONENTS = ("whole_blood", "red_cells", "plasma", "platelets")

# Blood groups present in the schema CHECK constraint.
VALID_BLOOD_GROUPS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")


def get_compatible_donor_groups(
    component: str,
    recipient_group: str,
) -> list[str]:
    """Return donor blood groups compatible with the given recipient group
    and component, according to the blood_compatibility table.

    Returns an empty list when no compatibility rows exist for the
    requested component (e.g. plasma/platelets are not yet seeded).
    """
    query = """
        SELECT donor_group
        FROM blood_compatibility
        WHERE component = %s
          AND recipient_group = %s
        ORDER BY donor_group;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (component, recipient_group))
            rows = cur.fetchall()

    return [row[0] for row in rows]


def search_available_blood(
    recipient_group: str,
    component: str,
    city: str = "",
    quantity_needed: int = 1,
) -> dict:
    """Search the available_blood_inventory view for matching units.

    Parameters
    ----------
    recipient_group : str
        The recipient's blood group (e.g. 'A+').
    component : str
        The required blood component (e.g. 'red_cells').
    city : str, optional
        Case-insensitive city filter applied to bank_address.
        Empty string means no location filter.
    quantity_needed : int
        The number of units required. Used to calculate fulfilment status.

    Returns
    -------
    dict with keys:
        compatible_groups : list[str]   — donor groups found in compatibility table
        results           : list[tuple] — matching rows
        columns           : list[str]   — column names for results
        quantity_available: int         — total units found
        quantity_needed   : int         — as supplied
        is_sufficient     : bool        — quantity_available >= quantity_needed
        compatibility_gap : bool        — True when no compatibility rows exist
    """
    compatible_groups = get_compatible_donor_groups(component, recipient_group)

    if not compatible_groups:
        # No compatibility rows for this component — report the gap.
        return {
            "compatible_groups": [],
            "results": [],
            "columns": [],
            "quantity_available": 0,
            "quantity_needed": quantity_needed,
            "is_sufficient": False,
            "compatibility_gap": True,
        }

    # Build parameterized query against the available_blood_inventory view.
    # The view already enforces:
    #   status = 'available', expiry_date >= CURRENT_DATE,
    #   latest screening approved, no active allocation.
    base_query = """
        SELECT
            abi.unit_id,
            abi.bank_name,
            abi.bank_address        AS location,
            abi.blood_group         AS donor_group,
            abi.component,
            abi.expiry_date,
            abi.expiry_date - CURRENT_DATE AS days_until_expiry,
            abi.status
        FROM available_blood_inventory AS abi
        WHERE abi.component = %s
          AND abi.blood_group = ANY(%s)
    """

    params: list = [component, compatible_groups]

    if city.strip():
        base_query += "\n  AND abi.bank_address ILIKE %s"
        params.append(f"%{city.strip()}%")

    base_query += "\nORDER BY abi.expiry_date ASC, abi.unit_id ASC;"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(base_query, params)
            columns = ([d.name for d in cur.description] if cur.description else [])
            rows = cur.fetchall()

    return {
        "compatible_groups": compatible_groups,
        "results": rows,
        "columns": columns,
        "quantity_available": len(rows),
        "quantity_needed": quantity_needed,
        "is_sufficient": len(rows) >= quantity_needed,
        "compatibility_gap": False,
    }

