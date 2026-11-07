"""
pages/reports.py — SQL-based reports and DBMS syllabus analytics.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT), str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.reports_service import (
    report_allocation_history,
    report_demand,
    report_expiry,
    report_inventory_by_bank,
    report_inventory_by_status,
    report_nested_having_above_average_banks,
    report_request_fulfillment,
    report_set_except_inactive_donors,
    report_set_union_facilities,
)

st.title("📊 Reports & DBMS Syllabus Analytics")
st.caption(
    "All queries are executed directly on PostgreSQL. "
    "Demonstrates Views, Joins, Grouping & Aggregates, Nested Queries, "
    "Set Operations (UNION, EXCEPT), and Three-Valued Logic."
)

tab_operational, tab_syllabus = st.tabs(
    ["📈 Operational Reports", "🎓 DBMS Coursework Concepts Showcase"]
)


def show_report(title: str, fn, rename_map: dict | None = None, concept_badge: str = ""):
    """Helper: run a report function, display results as a dataframe."""
    st.subheader(title)
    if concept_badge:
        st.info(f"**DBMS Concept Demonstrated:** {concept_badge}")
    try:
        cols, rows = fn()
        if rows:
            df = pd.DataFrame(rows, columns=cols)
            if rename_map:
                df = df.rename(columns=rename_map)
            if "component" in df.columns:
                df["component"] = df["component"].str.replace("_", " ").str.title()
            if "Component" in df.columns:
                df["Component"] = df["Component"].str.replace("_", " ").str.title()
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"{len(rows)} row(s) returned.")
        else:
            st.info("No data returned for this query.")
    except Exception as exc:
        st.error(f"Failed to execute query: {title}")
        st.exception(exc)
    st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# Tab 1: Operational Reports
# ══════════════════════════════════════════════════════════════════════════════
with tab_operational:
    show_report(
        "1. Available Inventory by Blood Bank, Component & Group",
        report_inventory_by_bank,
        {"bank_name": "Blood Bank", "component": "Component",
         "blood_group": "Blood Group", "available_units": "Available Units"},
        "View Querying (available_blood_inventory) + GROUP BY + Aggregation (COUNT)",
    )

    show_report(
        "2. Inventory Distribution by Status",
        report_inventory_by_status,
        {"status": "Status", "unit_count": "Total Units"},
        "Aggregate Functions (COUNT) + GROUP BY across discrete status domains",
    )

    show_report(
        "3. Expiring or Expired Units (Within 7 Days)",
        report_expiry,
        {
            "unit_id": "Unit ID", "bank_name": "Blood Bank",
            "component": "Component", "blood_group": "Blood Group",
            "expiry_date": "Expiry Date", "days_until_expiry": "Days Left",
            "expiry_category": "Category", "status": "Status",
        },
        "Date Arithmetic + CASE Expressions + Three-Valued Logic in Views",
    )

    show_report(
        "4. Outstanding Demand by Component & Recipient Group",
        report_demand,
        {
            "component": "Component", "recipient_group": "Recipient Group",
            "total_requests": "Open Requests", "total_units_requested": "Units Requested",
        },
        "Multiple Aggregates (COUNT, SUM) + WHERE status IN ('pending', 'partially_fulfilled')",
    )

    show_report(
        "5. Hospital Request Fulfillment Tracking",
        report_request_fulfillment,
        {
            "request_id": "Request ID", "hospital_name": "Hospital",
            "component": "Component", "recipient_group": "Recipient Group",
            "quantity_requested": "Qty Requested",
            "reserved_units": "Reserved", "issued_units": "Issued",
            "units_not_yet_allocated": "Still Needed",
            "request_status": "Status",
        },
        "Multi-table Joins (INNER + LEFT JOIN) + Aggregation with FILTER + Mathematical GREATEST",
    )

    show_report(
        "6. Complete Allocation History Log",
        report_allocation_history,
        {
            "allocation_id": "Alloc ID", "request_id": "Request ID",
            "hospital_name": "Hospital", "unit_id": "Unit ID",
            "blood_group": "Blood Group", "component": "Component",
            "bank_name": "Blood Bank", "allocation_status": "Status",
            "allocated_at": "Allocated At", "issued_at": "Issued At",
        },
        "5-Table Relational Join (allocation, blood_request, hospital, blood_unit, donation, blood_bank)",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2: DBMS Coursework Concepts Showcase
# ══════════════════════════════════════════════════════════════════════════════
with tab_syllabus:
    st.subheader("🎓 Relational Algebra & Advanced SQL Demonstration")
    st.write(
        "This section directly executes queries demonstrating theoretical DBMS syllabus concepts: "
        "Set Operations, Nested Queries with Subqueries in FROM, and HAVING clauses."
    )
    st.divider()

    show_report(
        "A. Set Operation: UNION (Blood Banks ∪ Hospitals)",
        report_set_union_facilities,
        {
            "facility_name": "Healthcare Facility Name",
            "address": "Address",
            "phone": "Phone",
            "facility_type": "Facility Type",
        },
        "Relational Set Union (UNION): Combines compatible tuples from disjoint relations into a single relation.",
    )

    show_report(
        "B. Set Operation: EXCEPT / Set Difference (Donors − Donated Donors)",
        report_set_except_inactive_donors,
        {
            "donor_id": "Donor ID",
            "donor_name": "Donor Name",
            "phone": "Contact Number",
            "blood_group": "Blood Group",
            "location": "Location",
        },
        "Relational Set Difference (EXCEPT): Evaluates {Donor IDs in donor} − {Donor IDs in donation} to find registered donors with 0 donation events.",
    )

    show_report(
        "C. Nested Subquery with HAVING & Derived Table (Above-Average Stock Blood Banks)",
        report_nested_having_above_average_banks,
        {
            "bank_name": "Blood Bank",
            "total_units_stored": "Units in Stock",
        },
        "Nested Query: Computes system-wide average in an inner subquery (derived table) and filters aggregated groups using HAVING COUNT >= (SELECT AVG(...)).",
    )
