"""
services/dashboard_service.py — Database queries for the dashboard page.
"""

from db import get_connection


def get_inventory_summary() -> dict:
    """Return aggregate blood-unit counts grouped by status.

    Returns a dict with keys:
        total, available, reserved, under_testing,
        rejected, discarded, expired
    All values are integers (0 when no rows exist).
    """
    query = """
        SELECT
            COUNT(*)                                    AS total,
            COUNT(*) FILTER (WHERE status = 'available')      AS available,
            COUNT(*) FILTER (WHERE status = 'reserved')       AS reserved,
            COUNT(*) FILTER (WHERE status = 'under_testing')  AS under_testing,
            COUNT(*) FILTER (WHERE status = 'rejected')       AS rejected,
            COUNT(*) FILTER (WHERE status = 'discarded')      AS discarded,
            COUNT(*) FILTER (WHERE status = 'expired')        AS expired
        FROM blood_unit;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()

    # row is a tuple or None
    if row is None:
        return dict(total=0, available=0, reserved=0, under_testing=0,
                    rejected=0, discarded=0, expired=0)

    keys = ["total", "available", "reserved", "under_testing",
            "rejected", "discarded", "expired"]
    return dict(zip(keys, (v or 0 for v in row)))


def get_request_counts() -> dict:
    """Return blood-request counts grouped by status."""
    query = """
        SELECT
            COUNT(*) FILTER (WHERE status = 'pending')              AS pending,
            COUNT(*) FILTER (WHERE status = 'partially_fulfilled')  AS partially_fulfilled,
            COUNT(*) FILTER (WHERE status = 'fulfilled')            AS fulfilled,
            COUNT(*) FILTER (WHERE status = 'cancelled')            AS cancelled
        FROM blood_request;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()

    if row is None:
        return dict(pending=0, partially_fulfilled=0, fulfilled=0, cancelled=0)

    keys = ["pending", "partially_fulfilled", "fulfilled", "cancelled"]
    return dict(zip(keys, (v or 0 for v in row)))


def get_inventory_by_group_and_component() -> tuple[list, list]:
    """Return available inventory grouped by blood group and component.

    Uses the available_blood_inventory view which already enforces
    screening approval, expiry, and allocation exclusion.

    Returns
    -------
    columns : list[str]
    rows    : list[tuple]
    """
    query = """
        SELECT
            blood_group,
            component,
            COUNT(*) AS available_units
        FROM available_blood_inventory
        GROUP BY blood_group, component
        ORDER BY blood_group, component;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            columns = ([d.name for d in cur.description] if cur.description else [])
            rows = cur.fetchall()

    return columns, rows


def get_inventory_by_bank() -> tuple[list, list]:
    """Return available inventory grouped by blood bank."""
    query = """
        SELECT
            bank_name,
            component,
            blood_group,
            COUNT(*) AS available_units
        FROM available_blood_inventory
        GROUP BY bank_name, component, blood_group
        ORDER BY bank_name, component, blood_group;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            columns = ([d.name for d in cur.description] if cur.description else [])
            rows = cur.fetchall()

    return columns, rows

