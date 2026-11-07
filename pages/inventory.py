"""
pages/inventory.py — Blood inventory management page.

Features:
- View Inventory: Multi-parameter filtering by blood group, component, bank, and status.
- Register Donation: Atomic creation of donation and blood units.
- Update Unit Status: Status transition with audit logging in status_history.
- Edit & Manage Unit: Safe expiry date updates and restricted deletion (preventing deletion of units with screening/allocation history).
"""

import sys
from pathlib import Path
from datetime import date, timedelta

import streamlit as st
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT), str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.inventory_service import (
    VALID_BLOOD_GROUPS,
    VALID_COMPONENTS,
    VALID_STATUSES,
    delete_blood_unit,
    get_unit_detail,
    get_unit_screening_history,
    list_blood_banks,
    list_inventory,
    record_screening,
    register_donation_and_units,
    update_unit_expiry,
    update_unit_status,
)
from services.donor_service import list_donors

st.title("📦 Blood Inventory Management")
st.caption("Track blood unit inventory, process new donations, update screening statuses, and manage unit details.")

tab_view, tab_register, tab_screening, tab_status, tab_manage = st.tabs(
    ["📋 View Inventory", "➕ Register Donation", "🔬 Lab Screening", "🔄 Update Status", "✏️ Edit & Manage Unit"]
)

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1: View Inventory (READ)
# ══════════════════════════════════════════════════════════════════════════════
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

    if st.button("Load Inventory", key="btn_load_inv"):
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


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2: Register Donation (CREATE)
# ══════════════════════════════════════════════════════════════════════════════
with tab_register:
    st.subheader("Register a New Donation")

    banks = list_blood_banks()
    _donor_cols, all_donors = list_donors(active_only=True)

    bank_map  = {b[1]: b[0] for b in banks}
    donor_map = {f"{d[1]} (ID #{d[0]}, {d[2]})": d[0] for d in all_donors}

    with st.form("register_donation_form"):
        col1, col2 = st.columns(2)
        with col1:
            donor_sel = st.selectbox(
                "Active Donor *",
                options=list(donor_map.keys()) if donor_map else ["No active donors registered"],
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

        reg_btn = st.form_submit_button("Register Donation", use_container_width=True)

    if reg_btn:
        if not donor_map:
            st.error("Please register or reactivate an active donor first.")
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
                    f"✅ Donation registered. Donation ID: **#{donation_id}**. "
                    "The blood unit is now 'under_testing' and will appear in "
                    "available inventory after screening approval."
                )
            except ValueError as ve:
                st.error(str(ve))
            except Exception as exc:
                st.error("Failed to register donation.")
                st.exception(exc)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3: Lab Screening & Quality Testing
# ══════════════════════════════════════════════════════════════════════════════
with tab_screening:
    st.subheader("🔬 Record Lab Screening Test")
    st.caption(
        "Units in 'under_testing' must have an **approved** screening result to qualify "
        "for the available inventory view and emergency matching."
    )

    with st.form("form_record_screening"):
        sc_uid = st.number_input("Blood Unit ID *", min_value=1, step=1, key="sc_uid_input")
        sc_res = st.selectbox(
            "Screening Result *",
            options=["approved", "rejected", "pending"],
            index=0,
            help="'approved' automatically marks the unit as 'available'. 'rejected' marks it as 'discarded'.",
        )
        sc_actor = st.text_input("Lab Technician / Pathologist", value="Lab Staff", max_chars=50)
        sc_notes = st.text_area("Remarks / Test Results", placeholder="e.g. Negative for HIV, HBV, HCV, Syphilis, and Malaria.")
        sc_btn = st.form_submit_button("💾 Record Screening Result", use_container_width=True)

    if sc_btn:
        try:
            sid = record_screening(int(sc_uid), sc_res, sc_notes, sc_actor or "lab_tech")
            st.success(f"✅ Screening record **#{sid}** saved with result **'{sc_res}'**. Unit #{sc_uid} status updated.")
            st.rerun()
        except ValueError as ve:
            st.error(str(ve))
        except Exception as exc:
            st.error("Failed to record screening test.")
            st.exception(exc)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 4: Update Unit Status (UPDATE Status)
# ══════════════════════════════════════════════════════════════════════════════
with tab_status:
    st.subheader("Update Blood Unit Status")
    st.info(
        "Record screening approvals, rejections, discards, "
        "or expiry. Status changes are permanently recorded in status_history."
    )

    with st.form("update_status_form"):
        upd_unit_id = st.number_input("Unit ID *", min_value=1, step=1, key="st_upd_uid")
        upd_status  = st.selectbox("New Status *", VALID_STATUSES, key="st_upd_st")
        upd_actor   = st.text_input("Actor (Staff Name / Lab Tech)", value="Lab Tech")
        upd_remarks = st.text_area("Remarks", max_chars=500, placeholder="e.g. Lab tests cleared of pathogens")

        upd_btn = st.form_submit_button("Update Status", use_container_width=True)

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
                    f"✅ Unit #{upd_unit_id} status updated to **'{upd_status}'**."
                )
            else:
                st.info("The unit already has that status. No change recorded.")
        except ValueError as ve:
            st.error(str(ve))
        except Exception as exc:
            st.error("Failed to update status.")
            st.exception(exc)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 4: Edit & Manage Unit (UPDATE Expiry & DELETE Unit)
# ══════════════════════════════════════════════════════════════════════════════
with tab_manage:
    st.subheader("Edit & Manage Blood Unit")
    st.caption("Safely adjust unit expiry dates or perform restricted physical deletion for erroneously registered units.")

    manage_uid = st.number_input("Enter Unit ID to Manage", min_value=1, step=1, value=1, key="inv_mng_uid")

    if st.button("Load Unit Details", key="btn_load_mng_unit"):
        st.session_state["loaded_mng_uid"] = int(manage_uid)

    target_uid = st.session_state.get("loaded_mng_uid", int(manage_uid))

    try:
        unit = get_unit_detail(target_uid)
        if not unit:
            st.warning(f"No blood unit found with ID **#{target_uid}**.")
        else:
            (uid, bank, donor, don_date, comp, bg,
             coll_date, exp_date, days_left, status) = unit

            st.markdown(f"""
| Field | Database Record |
|---|---|
| **Unit ID** | #{uid} |
| **Blood Bank** | {bank} |
| **Donor** | {donor} |
| **Donation Date** | {don_date} |
| **Component** | {comp.replace('_', ' ').title()} |
| **Blood Group** | **{bg}** |
| **Collection Date** | {coll_date} |
| **Current Expiry Date** | {exp_date} ({days_left} days left) |
| **Current Status** | **'{status}'** |
""")

            # ── Action 1: Edit Expiry Date ──
            with st.expander("✏️ Edit Expiry Date", expanded=True):
                if status in ("reserved", "issued"):
                    st.warning(f"🔒 Unit #{uid} is currently '{status}'. Modifications are strictly prohibited to prevent allocation discrepancies.")
                else:
                    with st.form(f"form_edit_exp_{uid}"):
                        new_exp = st.date_input("New Expiry Date *", value=exp_date)
                        exp_actor = st.text_input("Staff Name", value="Medical Officer")
                        exp_remarks = st.text_input("Reason for Modification", placeholder="e.g. Extended testing validation")
                        save_exp_btn = st.form_submit_button("💾 Save Expiry Date Update")

                    if save_exp_btn:
                        try:
                            update_unit_expiry(uid, new_exp, exp_actor, exp_remarks)
                            st.success(f"✅ Expiry date for Unit #{uid} updated to {new_exp}.")
                            st.rerun()
                        except ValueError as ve:
                            st.error(str(ve))
                        except Exception as exc:
                            st.error("Failed to update expiry date.")
                            st.exception(exc)

            # ── Action 2: Delete Blood Unit ──
            with st.expander("🗑️ Delete Blood Unit"):
                st.warning(
                    "⚠️ Physical deletion is **only permitted** for units with NO screening or allocation records "
                    "(e.g., entered by clerical mistake). Units with test or allocation history must be marked 'discarded' instead."
                )
                chk_del_unit = st.checkbox(f"Confirm deletion of Blood Unit #{uid}", key=f"chk_del_unit_{uid}")
                if st.button(f"Permanently Delete Unit #{uid}", key=f"btn_del_unit_{uid}", type="primary"):
                    if not chk_del_unit:
                        st.error("Please confirm the deletion checkbox above before proceeding.")
                    else:
                        try:
                            delete_blood_unit(uid)
                            st.success(f"Unit #{uid} successfully deleted from the database.")
                            if "loaded_mng_uid" in st.session_state:
                                del st.session_state["loaded_mng_uid"]
                            st.rerun()
                        except ValueError as ve:
                            st.error(f"Integrity Restriction: {ve}")
                        except Exception as exc:
                            st.error("Deletion failed due to a database error.")
                            st.exception(exc)

            # ── Screening History ──
            st.divider()
            st.subheader("Screening History")
            s_cols, s_rows = get_unit_screening_history(uid)
            if s_rows:
                sdf = pd.DataFrame(s_rows, columns=s_cols)
                sdf = sdf.rename(columns={
                    "screening_id": "Screening ID", "screening_date": "Date",
                    "result": "Result", "remarks": "Remarks",
                })
                st.dataframe(sdf, use_container_width=True, hide_index=True)
            else:
                st.info("No screening records exist for this unit.")

    except Exception as exc:
        st.error("Failed to load unit details.")
        st.exception(exc)
