import streamlit as st

from db import get_connection


# --------------------------------------------------
# Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="BloodLink",
    page_icon="🩸",
    layout="wide"
)


# --------------------------------------------------
# Database functions
# --------------------------------------------------

def get_dashboard_data():
    """Retrieve summary statistics from PostgreSQL."""

    query = """
        SELECT
            COUNT(*) AS total_units,

            COUNT(*) FILTER (
                WHERE status = 'available'
            ) AS available_units,

            COUNT(*) FILTER (
                WHERE status = 'reserved'
            ) AS reserved_units,

            COUNT(*) FILTER (
                WHERE status = 'under_testing'
            ) AS testing_units,

            COUNT(*) FILTER (
                WHERE status = 'expired'
            ) AS expired_units

        FROM blood_unit;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchone()


def get_pending_requests():
    """Count requests that are pending or partially fulfilled."""

    query = """
        SELECT COUNT(*)
        FROM blood_request
        WHERE status IN ('pending', 'partially_fulfilled');
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchone()[0]


def get_available_inventory():
    """Retrieve eligible blood inventory from the existing view."""

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

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)

            columns = [
                description.name
                for description in cursor.description
            ]

            rows = cursor.fetchall()

    return columns, rows


# --------------------------------------------------
# Dashboard interface
# --------------------------------------------------

st.title("🩸 BloodLink")
st.subheader("Blood Donor and Inventory Management System")

st.write(
    "Monitor blood inventory, track hospital requests, "
    "and identify available blood components."
)

st.divider()


try:
    (
        total_units,
        available_units,
        reserved_units,
        testing_units,
        expired_units
    ) = get_dashboard_data()

    pending_requests = get_pending_requests()

    # Summary metrics
    st.header("Dashboard Overview")

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Blood Units", total_units)
    col2.metric("Available Units", available_units)
    col3.metric("Pending Requests", pending_requests)

    col4, col5, col6 = st.columns(3)

    col4.metric("Reserved Units", reserved_units)
    col5.metric("Under Testing", testing_units)
    col6.metric("Expired Units", expired_units)

    st.divider()

    # Available inventory
    st.header("Available Blood Inventory")

    inventory_columns, inventory_rows = get_available_inventory()

    if inventory_rows:
        st.dataframe(
        inventory_rows,
        column_config={
            index: st.column_config.TextColumn(label=column)
            for index, column in enumerate(inventory_columns)
        },
        hide_index=True,
        width="stretch"
        )
    else:
        st.info("No eligible blood inventory is currently available.")

    st.caption(
        "Inventory counts are retrieved from the database. "
        "Only units included in the available_blood_inventory "
        "view appear in the inventory table."
    )

except Exception as error:
    st.error("Unable to load the BloodLink dashboard.")
    st.exception(error)