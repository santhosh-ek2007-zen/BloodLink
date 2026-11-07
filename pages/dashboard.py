"""
pages/dashboard.py — BloodLink dashboard page.
"""

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT), str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.dashboard_service import (
    get_inventory_by_group_and_component,
    get_inventory_by_bank,
    get_inventory_summary,
    get_request_counts,
)

st.title("🩸 BloodLink")
st.subheader("Blood Donor and Inventory Management System")
st.write(
    "Monitor blood inventory, track hospital requests, "
    "and coordinate compatible blood unit allocation."
)
st.divider()

# ── Metrics ────────────────────────────────────────────────────────────────
try:
    inv  = get_inventory_summary()
    reqs = get_request_counts()

    st.header("Inventory Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Units",     inv["total"])
    c2.metric("Available",       inv["available"])
    c3.metric("Reserved",        inv["reserved"])
    c4.metric("Under Testing",   inv["under_testing"])

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Rejected",        inv["rejected"])
    c6.metric("Discarded",       inv["discarded"])
    c7.metric("Expired",         inv["expired"])
    c8.metric("",                "")          # spacer

    st.divider()
    st.header("Request Overview")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Pending",              reqs["pending"])
    r2.metric("Partially Fulfilled",  reqs["partially_fulfilled"])
    r3.metric("Fulfilled",            reqs["fulfilled"])
    r4.metric("Cancelled",            reqs["cancelled"])

except Exception as exc:
    st.error("Unable to load dashboard metrics. Check the database connection.")
    st.exception(exc)

st.divider()

# ── Available inventory by blood group / component ─────────────────────────
st.header("Available Inventory — by Blood Group & Component")
st.caption(
    "Only units that are status=available, not expired, have an approved "
    "screening result, and have no active allocation appear here."
)

try:
    cols, rows = get_inventory_by_group_and_component()
    if rows:
        import pandas as pd
        df = pd.DataFrame(rows, columns=cols)
        df = df.rename(columns={
            "blood_group": "Blood Group",
            "component": "Component",
            "available_units": "Available Units",
        })
        df["Component"] = df["Component"].str.replace("_", " ").str.title()
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No eligible blood units are currently available.")
except Exception as exc:
    st.error("Failed to load inventory summary.")
    st.exception(exc)

st.divider()

# ── Available inventory by bank ────────────────────────────────────────────
st.header("Available Inventory — by Blood Bank")

try:
    cols2, rows2 = get_inventory_by_bank()
    if rows2:
        import pandas as pd
        df2 = pd.DataFrame(rows2, columns=cols2)
        df2 = df2.rename(columns={
            "bank_name": "Blood Bank",
            "component": "Component",
            "blood_group": "Blood Group",
            "available_units": "Available Units",
        })
        df2["Component"] = df2["Component"].str.replace("_", " ").str.title()
        st.dataframe(df2, use_container_width=True, hide_index=True)
    else:
        st.info("No eligible inventory by bank.")
except Exception as exc:
    st.error("Failed to load bank inventory summary.")
    st.exception(exc)

