"""
pages/emergency_search.py — Emergency blood search page (read-only).

IMPORTANT: Search results are database candidates only.
They do not constitute clinical authorisation for transfusion.
"""

import sys
from pathlib import Path

import streamlit as st

# Ensure app/ and services/ are importable from project root launch.
_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT), str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.search_service import (
    VALID_BLOOD_GROUPS,
    VALID_COMPONENTS,
    search_available_blood,
)

st.title("🚨 Find Blood Now")
st.caption(
    "Search results are database candidates only and do not constitute "
    "clinical authorisation for transfusion. Always verify with qualified "
    "blood-bank personnel before use."
)

st.divider()

# ── Search form ────────────────────────────────────────────────────────────
with st.form("emergency_search_form"):
    st.subheader("Search Criteria")

    col1, col2 = st.columns(2)

    with col1:
        recipient_group = st.selectbox(
            "Recipient Blood Group *",
            options=[""] + list(VALID_BLOOD_GROUPS),
            index=0,
        )
        component = st.selectbox(
            "Required Component *",
            options=[""] + list(VALID_COMPONENTS),
            index=0,
            format_func=lambda x: x.replace("_", " ").title() if x else "— select —",
        )

    with col2:
        city = st.text_input(
            "City / Location (optional)",
            placeholder="e.g. Chennai",
            max_chars=100,
        )
        quantity_needed = st.number_input(
            "Units Required *",
            min_value=1,
            max_value=100,
            value=1,
            step=1,
        )

    submitted = st.form_submit_button("🔍 Search", use_container_width=True)

# ── Results ────────────────────────────────────────────────────────────────
if submitted:
    errors = []
    if not recipient_group:
        errors.append("Please select a recipient blood group.")
    if not component:
        errors.append("Please select a blood component.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        try:
            result = search_available_blood(
                recipient_group=recipient_group,
                component=component,
                city=city,
                quantity_needed=quantity_needed,
            )

            st.divider()
            st.subheader("Search Results")

            # Compatibility gap
            if result["compatibility_gap"]:
                st.warning(
                    f"No compatibility rules are defined for **{component.replace('_', ' ').title()}** "
                    f"in the database. Compatible donor groups cannot be determined. "
                    f"Please consult blood-bank personnel directly."
                )
            else:
                # Compatible groups banner
                st.info(
                    f"Compatible donor groups for **{recipient_group}** "
                    f"({component.replace('_', ' ').title()}): "
                    + ", ".join(f"**{g}**" for g in result["compatible_groups"])
                )

                qty_available = result["quantity_available"]
                qty_needed    = result["quantity_needed"]

                # Fulfilment status
                col_a, col_b = st.columns(2)
                col_a.metric("Units Available", qty_available)
                col_b.metric("Units Requested", qty_needed)

                if qty_available == 0:
                    st.error(
                        f"No eligible {component.replace('_', ' ').title()} units "
                        f"are currently available for blood group **{recipient_group}**"
                        + (f" in **{city}**" if city.strip() else "")
                        + ". Please contact blood banks directly."
                    )
                elif result["is_sufficient"]:
                    st.success(
                        f"✅ Sufficient inventory found — "
                        f"{qty_available} unit(s) available, {qty_needed} requested."
                    )
                else:
                    st.warning(
                        f"⚠️ Insufficient inventory — only {qty_available} unit(s) "
                        f"available, {qty_needed} requested. "
                        "Consider contacting additional blood banks."
                    )

                # Results table
                if result["results"]:
                    import pandas as pd

                    df = pd.DataFrame(result["results"], columns=result["columns"])

                    # Rename columns for readability
                    df = df.rename(columns={
                        "unit_id":           "Unit ID",
                        "bank_name":         "Blood Bank",
                        "location":          "Location",
                        "donor_group":       "Donor Group",
                        "component":         "Component",
                        "expiry_date":       "Expiry Date",
                        "days_until_expiry": "Days Until Expiry",
                        "status":            "Status",
                    })
                    df["Component"] = df["Component"].str.replace("_", " ").str.title()

                    st.dataframe(df, use_container_width=True, hide_index=True)

        except Exception as exc:
            st.error("An error occurred while searching the database.")
            st.exception(exc)

