"""
pages/inventory.py — Blood inventory management page.
"""

import sys
from pathlib import Path
from datetime import date, timedelta

import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from inventory_service import (
    VALID_BLOOD_GROUPS,
    VALID_COMPONENTS,
    VALID_STATUSES,
    get_unit_detail,
    get_unit_screening_history,
    list_blood_banks,
    list_inventory,
    register_donation_and_units,
    update_unit_status,
)
from donor_service import list_donors

st.title("🏥 Blood Inventory")

tab_view, tab_register, tab_update = st.tabs(
    ["View Inventory", "Register Donation", "Update Unit Status"]
)

# ── Tab 1: View Inventory ──────────────────────────────────────────────────
with tab_view:
    st.subheader("Filter Inventory")

    banks = list_blood_banks()
    bank_options = {0: "All Banks"} | {b[0]: b[1] for b in banks}

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        bg_sel = st.selectbox("Blood Group", ["All"] + list(VALID_BLOOD_GROUPS), key="inv_bg")
    with col2:
        comp_sel = st.selectbox(
            "Component", ["All"] + list(VALID_COMPONENTS),
            format_func=lambda x: x.replace("_", " ").title() if x != "All" else "All",
            key="inv_comp",
        )
    with col3:
        bank_sel = st.selectbox("Blood Bank", list(bank_options.values()), key="inv_bank")
    with col4:
        status_sel = st.selectbox(
            "Status", ["All"] + list(VALID_STATUSES), key="inv_status"
        )

    if st.button("Load Inventory"):
        try:
            selected_bank_id = None
            for bid, bname in bank_options.items():
                if bname == bank_sel and bid != 0:
                    selected_bank_id = bid

            cols, rows = list_inventory(
                blood_group="" if bg_sel == "All" else bg_sel,
                component="" if comp_sel == "All" else comp_sel,
                bank_id=selected_bank_id,
                status="" if status_sel == "All" else status_sel,
            )

            if rows:
                import pandas as pd
                df = pd.DataFrame(rows, columns=cols)
                df = df.rename(columns={
                    "unit_id": "Unit ID", "bank_name": "Blood Bank",
                    "component": "Component", "blood_group": "Blood Group",
                    "collection_date": "Collected", "expiry_date": "Expires",
                    "days_until_expiry": "Days Left", "status": "Status",
                    "donation_id": "Donation ID", "donor_name": "Donor",
                })
                df["Component"] = df["Component"].str.replace("_", " ").str.title()
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.caption(f"{len(rows)} unit(s) found.")
            else:
                st.info("No blood units match the selected filters.")
        except Exception as exc:
            st.error("Failed to load inventory.")
            st.exception(exc)

    # Unit detail expander
    st.divider()
    st.subheader("Unit Detail")
    unit_id_inp = st.number_input("Unit ID", min_value=1, step=1, key="detail_unit")
    if st.button("View Unit"):
        try:
            unit = get_unit_detail(int(unit_id_inp))
            if unit is None:
                st.warning(f"No unit found with ID {unit_id_inp}.")
            else:
                (uid, bank, donor, don_date, comp, bg,
                 coll_date, exp_date, days_left, status) = unit
                st.markdown(f"""
| Field | Value |
|---|---|
| Unit ID | {uid} |
| Blood Bank | {bank} |
| Donor | {donor} |
| Donation Date | {don_date} |
| Component | {comp.replace('_', ' ').title()} |
| Blood Group | {bg} |
| Collected | {coll_date} |
| Expires | {exp_date} |
| Days Until Expiry | {days_left} |
| Status | **{status}** |
""")
                # Screening history
                s_cols, s_rows = get_unit_screening_history(int(unit_id_inp))
                if s_rows:
                    import pandas as pd
                    sdf = pd.DataFrame(s_rows, columns=s_cols)
                    sdf = sdf.rename(columns={
                        "screening_id": "ID", "screening_date": "Date",
                        "result": "Result", "remarks": "Remarks",
                    })
                    st.caption("Screening History")
                    st.dataframe(sdf, use_container_width=True, hide_index=True)
                else:
                    st.info("No screening records for this unit.")
        except Exception as exc:
            st.error("Failed to load unit detail.")
            st.exception(exc)


# ── Tab 2: Register Donation ───────────────────────────────────────────────
with tab_register:
    st.subheader("Register a New Donation")

    banks = list_blood_banks()
    _donor_cols, all_donors = list_donors()

    bank_map  = {b[1]: b[0] for b in banks}
    # all_donors rows: (donor_id, donor_name, blood_group, location, phone)
    donor_map = {f"{d[1]} (ID {d[0]})": d[0] for d in all_donors}

    with st.form("register_donation_form"):
        col1, col2 = st.columns(2)
        with col1:
            donor_sel = st.selectbox(
                "Donor *",
                options=list(donor_map.keys()) if donor_map else ["No donors registered"],
            )
            donation_date = st.date_input(
                "Donation Date *",
                value=date.today(),
                max_value=date.today(),
            )
        with col2:
            bank_sel2 = st.selectbox(
                "Blood Bank *",
                options=list(bank_map.keys()),
            )
            quantity_ml = st.number_input(
                "Volume Collected (ml) *",
                min_value=50, max_value=600, value=450, step=50,
            )

        st.markdown("**Blood Unit Details**")
        unit_comp = st.selectbox(
            "Component *",
            VALID_COMPONENTS,
            format_func=lambda x: x.replace("_", " ").title(),
        )
        unit_bg = st.selectbox("Blood Group *", VALID_BLOOD_GROUPS)
        collection_date = st.date_input(
            "Collection Date *",
            value=date.today(),
            max_value=date.today(),
        )
        expiry_date = st.date_input(
            "Expiry Date *",
            value=date.today() + timedelta(days=42),
            min_value=date.today() + timedelta(days=1),
        )

        reg_btn = st.form_submit_button("Register Donation")

    if reg_btn:
        if not donor_map:
            st.error("Please register a donor first.")
        else:
            try:
                donation_id = register_donation_and_units(
                    donor_id=donor_map[donor_sel],
                    bank_id=bank_map[bank_sel2],
                    donation_date=str(donation_date),
                    quantity_ml=quantity_ml,
                    units=[{
                        "component": unit_comp,
                        "blood_group": unit_bg,
                        "collection_date": collection_date,
                        "expiry_date": expiry_date,
                    }],
                )
                st.success(
                    f"✅ Donation registered. Donation ID: **{donation_id}**. "
                    "The blood unit is now under testing and will appear in "
                    "inventory after screening approval."
                )
            except ValueError as ve:
                st.error(str(ve))
            except Exception as exc:
                st.error("Failed to register donation.")
                st.exception(exc)


# ── Tab 3: Update Unit Status ──────────────────────────────────────────────
with tab_update:
    st.subheader("Update Blood Unit Status")
    st.info(
        "Use this to record screening approvals, rejections, discards, "
        "or expiry. Status changes are recorded in status history."
    )

    with st.form("update_status_form"):
        upd_unit_id = st.number_input("Unit ID *", min_value=1, step=1)
        upd_status  = st.selectbox("New Status *", VALID_STATUSES)
        upd_actor   = st.text_input("Actor (your name or role)", value="staff")
        upd_remarks = st.text_area("Remarks", max_chars=500)

        upd_btn = st.form_submit_button("Update Status")

    if upd_btn:
        try:
            changed = update_unit_status(
                unit_id=int(upd_unit_id),
                new_status=upd_status,
                actor=upd_actor or "staff",
                remarks=upd_remarks,
            )
            if changed:
                st.success(
                    f"✅ Unit {upd_unit_id} status updated to **{upd_status}**."
                )
            else:
                st.info("The unit already has that status. No change recorded.")
        except ValueError as ve:
            st.error(str(ve))
        except Exception as exc:
            st.error("Failed to update status.")
            st.exception(exc)
