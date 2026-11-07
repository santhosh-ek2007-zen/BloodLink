"""
services/reports_service.py — SQL-based reports for the Reports page.

Demonstrates core DBMS concepts from the syllabus:
- Views
- Aggregates (COUNT, SUM, AVG) & Grouping (GROUP BY, HAVING)
- Multi-table Joins (INNER JOIN, LEFT JOIN)
- Set Operations (UNION, EXCEPT)
- Nested Subqueries
- Three-Valued Logic & Conditional Expressions (CASE, FILTER)
"""

from db import get_connection


def report_inventory_by_bank() -> tuple[list, list]:
    """Available inventory grouped by bank, component, and blood group."""
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
            return ([d.name for d in cur.description] if cur.description else []), cur.fetchall()


def report_inventory_by_status() -> tuple[list, list]:
    """All blood units grouped by status."""
    query = """
        SELECT
            status,
            COUNT(*) AS unit_count
        FROM blood_unit
        GROUP BY status
        ORDER BY status;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return ([d.name for d in cur.description] if cur.description else []), cur.fetchall()


def report_expiry() -> tuple[list, list]:
    """Units expiring within 7 days or already expired."""
    query = """
        SELECT
            unit_id,
            bank_name,
            component,
            blood_group,
            expiry_date,
            days_until_expiry,
            expiry_category,
            status
        FROM blood_expiry_report
        WHERE days_until_expiry <= 7
        ORDER BY days_until_expiry ASC, bank_name;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return ([d.name for d in cur.description] if cur.description else []), cur.fetchall()


def report_demand() -> tuple[list, list]:
    """Outstanding demand by component and blood group (pending/partial requests)."""
    query = """
        SELECT
            component,
            recipient_group,
            COUNT(*)                    AS total_requests,
            SUM(quantity_requested)     AS total_units_requested
        FROM blood_request
        WHERE status IN ('pending', 'partially_fulfilled')
        GROUP BY component, recipient_group
        ORDER BY total_units_requested DESC, component, recipient_group;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return ([d.name for d in cur.description] if cur.description else []), cur.fetchall()


def report_request_fulfillment() -> tuple[list, list]:
    """Hospital request fulfillment status (all requests)."""
    query = """
        SELECT
            br.request_id,
            h.hospital_name,
            br.component,
            br.recipient_group,
            br.quantity_requested,
            COUNT(a.allocation_id) FILTER (WHERE a.status = 'reserved') AS reserved_units,
            COUNT(a.allocation_id) FILTER (WHERE a.status = 'issued')   AS issued_units,
            GREATEST(
                br.quantity_requested
                - COUNT(a.allocation_id) FILTER (WHERE a.status IN ('reserved','issued')),
                0
            ) AS units_not_yet_allocated,
            br.status AS request_status
        FROM blood_request AS br
        JOIN hospital AS h ON h.hospital_id = br.hospital_id
        LEFT JOIN allocation AS a ON a.request_id = br.request_id
        GROUP BY
            br.request_id, h.hospital_name, br.component,
            br.recipient_group, br.quantity_requested, br.status
        ORDER BY br.request_date DESC, br.request_id;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return ([d.name for d in cur.description] if cur.description else []), cur.fetchall()


def report_allocation_history() -> tuple[list, list]:
    """Full allocation history across all requests."""
    query = """
        SELECT
            a.allocation_id,
            a.request_id,
            h.hospital_name,
            a.unit_id,
            bu.blood_group,
            bu.component,
            bb.bank_name,
            a.status            AS allocation_status,
            a.allocated_at,
            a.issued_at
        FROM allocation AS a
        JOIN blood_request AS br ON br.request_id = a.request_id
        JOIN hospital      AS h  ON h.hospital_id = br.hospital_id
        JOIN blood_unit    AS bu ON bu.unit_id     = a.unit_id
        JOIN donation      AS d  ON d.donation_id  = bu.donation_id
        JOIN blood_bank    AS bb ON bb.bank_id     = d.bank_id
        ORDER BY a.allocated_at DESC;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return ([d.name for d in cur.description] if cur.description else []), cur.fetchall()


def report_set_union_facilities() -> tuple[list, list]:
    """Demonstrates SQL Set Operation: UNION.
    Combines blood banks and hospitals into a unified healthcare facility directory.
    """
    query = """
        SELECT
            bank_name AS facility_name,
            address,
            phone,
            'Blood Bank' AS facility_type
        FROM blood_bank
        UNION
        SELECT
            hospital_name AS facility_name,
            address,
            phone,
            'Hospital' AS facility_type
        FROM hospital
        ORDER BY facility_type, facility_name;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return ([d.name for d in cur.description] if cur.description else []), cur.fetchall()


def report_set_except_inactive_donors() -> tuple[list, list]:
    """Demonstrates SQL Set Operation: EXCEPT (Set Difference).
    Finds registered donors who have not yet participated in any donation event.
    """
    query = """
        SELECT
            d.donor_id,
            d.donor_name,
            d.phone,
            d.blood_group,
            d.location
        FROM donor AS d
        WHERE d.donor_id IN (
            SELECT donor_id FROM donor
            EXCEPT
            SELECT donor_id FROM donation
        )
        ORDER BY d.donor_id;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return ([d.name for d in cur.description] if cur.description else []), cur.fetchall()


def report_nested_having_above_average_banks() -> tuple[list, list]:
    """Demonstrates Nested Subquery, Derived Table, and HAVING with Aggregate comparison.
    Finds blood banks holding available inventory at or above the system-wide average.
    """
    query = """
        SELECT
            bb.bank_name,
            COUNT(bu.unit_id) AS total_units_stored
        FROM blood_bank AS bb
        JOIN donation AS d
            ON d.bank_id = bb.bank_id
        JOIN blood_unit AS bu
            ON bu.donation_id = d.donation_id
        GROUP BY
            bb.bank_id,
            bb.bank_name
        HAVING COUNT(bu.unit_id) >= (
            SELECT AVG(bank_count)
            FROM (
                SELECT COUNT(bu2.unit_id) AS bank_count
                FROM blood_bank AS bb2
                JOIN donation AS d2 ON d2.bank_id = bb2.bank_id
                JOIN blood_unit AS bu2 ON bu2.donation_id = d2.donation_id
                GROUP BY bb2.bank_id
            ) AS avg_subquery
        )
        ORDER BY total_units_stored DESC;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return ([d.name for d in cur.description] if cur.description else []), cur.fetchall()
