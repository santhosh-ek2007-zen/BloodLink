"""
pages/donors.py — Donor registration and management page.

Features:
- Complete CRUD operations:
  - Create: "Register as Donor" section with full validation.
  - Read: "Donor Directory" with search, blood group, location, and active status filters.
  - Update: Edit name, phone, blood group, and location.
  - Deactivate / Reactivate: Logical state toggle preserving history.
  - Delete: Safe physical deletion allowed ONLY when no donation records exist.
"""

import sys
from pathlib import Path
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT), str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.donor_service import (
    VALID_BLOOD_GROUPS,
    deactivate_donor,
    delete_donor,
    get_donation_history,
    get_donor_by_id,
    list_donors,
    reactivate_donor,
    register_donor,
    update_donor,
)

st.title("👤 Donor Registration & Management")
st.caption(
    "Register voluntary blood donors, manage donor information, and track donation history. "
    "All records are persisted directly into PostgreSQL."
)

tab_register, tab_directory, tab_detail = st.tabs(
    ["📝 Register as Donor", "📋 Donor Directory", "🔍 Donor Detail & Actions"]
)

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1: Register as Donor (CREATE)
# ══════════════════════════════════════════════════════════════════════════════
with tab_register:
    st.header("Register as Donor")
    st.write(
        "Complete the registration form below. All fields marked with **(*)** are required. "
        "Your record will be saved in PostgreSQL and assigned a unique Donor ID."
    )

    # Display confirmation card if a donor was just registered in this session
    if "last_registered_donor" in st.session_state:
        last = st.session_state["last_registered_donor"]
        st.success(f"🎉 **Registration Successful!** Donor registered with Database ID: **#{last['id']}**")
        with st.container():
            st.markdown(
                f"""
                <div style="padding: 1rem; border-radius: 8px; border: 1px solid #4CAF50; background-color: rgba(76, 175, 80, 0.08); margin-bottom: 1.5rem;">
                    <h4 style="margin: 0 0 0.5rem 0; color: #2E7D32;">Verified Database Record</h4>
                    <p style="margin: 0.2rem 0;"><strong>Donor ID:</strong> #{last['id']}</p>
                    <p style="margin: 0.2rem 0;"><strong>Name:</strong> {last['name']}</p>
                    <p style="margin: 0.2rem 0;"><strong>Blood Group:</strong> {last['blood_group']}</p>
                    <p style="margin: 0.2rem 0;"><strong>Phone:</strong> {last['phone']}</p>
                    <p style="margin: 0.2rem 0;"><strong>Location:</strong> {last['location'] or 'Not specified'}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        if st.button("Register Another Donor"):
            del st.session_state["last_registered_donor"]
            st.rerun()

    with st.form("register_donor_form", clear_on_submit=False):
        col1, col2 = st.columns(2)

        with col1:
            name_input = st.text_input(
                "Full Name *",
                placeholder="e.g. Ramesh Kumar",
                max_chars=50,
                help="2 to 50 characters; letters, spaces, hyphens, and periods.",
            )
            phone_input = st.text_input(
                "Phone Number *",
                placeholder="e.g. 9876543210",
                max_chars=10,
                help="Exactly 10 digits. Used to prevent duplicate registrations.",
            )

        with col2:
            blood_group_input = st.selectbox(
                "Blood Group *",
                options=["— Select Blood Group —"] + list(VALID_BLOOD_GROUPS),
                index=0,
                help="Select the donor's medically verified blood group.",
            )
            location_input = st.text_input(
                "City / Location (optional)",
                placeholder="e.g. Chennai, Tambaram",
                max_chars=100,
                help="Residential city or blood bank region.",
            )

        st.caption("🔒 *Donor phone numbers are protected and masked in public views for privacy.*")
        submit_btn = st.form_submit_button("💾 Complete Registration", use_container_width=True)

    if submit_btn:
        errors = []
        if not name_input.strip():
            errors.append("Donor Name is required.")
        if not phone_input.strip():
            errors.append("Phone Number is required.")
        if blood_group_input not in VALID_BLOOD_GROUPS:
            errors.append("Please select a valid Blood Group from the list.")

        if errors:
            for err in errors:
                st.error(err)
        else:
            try:
                new_donor_id = register_donor(
                    name=name_input,
                    phone=phone_input,
                    blood_group=blood_group_input,
                    location=location_input,
                )

                st.session_state["last_registered_donor"] = {
                    "id": new_donor_id,
                    "name": name_input.strip(),
                    "phone": phone_input.strip(),
                    "blood_group": blood_group_input,
                    "location": location_input.strip(),
                }
                st.rerun()

            except ValueError as ve:
                st.error(f"Validation Error: {ve}")
            except Exception as exc:
                st.error("Database operation failed. The transaction was rolled back and no record was saved.")
                st.exception(exc)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2: Donor Directory (READ)
# ══════════════════════════════════════════════════════════════════════════════
with tab_directory:
    st.header("Registered Donors Directory")
    st.write("Browse and filter registered donors directly from PostgreSQL.")

    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        search_name = st.text_input("Search by Name", key="dir_name", placeholder="Search name...")
    with col_s2:
        bg_filter = st.selectbox("Filter Blood Group", ["All"] + list(VALID_BLOOD_GROUPS), key="dir_bg")
    with col_s3:
        loc_filter = st.text_input("Filter Location", key="dir_loc", placeholder="Search city...")
    with col_s4:
        active_filter = st.selectbox("Filter Status", ["All Donors", "Active Only"], key="dir_act")

    mask_toggle = st.checkbox(
        "Mask contact information (privacy protection)",
        value=True,
        help="When enabled, phone numbers are masked (e.g. ******0001) to protect donor privacy.",
    )

    try:
        cols, rows = list_donors(
            search_name=search_name,
            blood_group="" if bg_filter == "All" else bg_filter,
            location=loc_filter,
            mask_contacts=mask_toggle,
            active_only=(active_filter == "Active Only"),
        )

        if rows:
            import pandas as pd
            df = pd.DataFrame(rows, columns=cols)
            rename_dict = {
                "donor_id": "Donor ID",
                "donor_name": "Full Name",
                "blood_group": "Blood Group",
                "location": "Location",
                "phone": "Contact Number",
            }
            if "is_active" in df.columns:
                rename_dict["is_active"] = "Active"
                df["is_active"] = df["is_active"].apply(lambda x: "✅ Active" if x else "❌ Inactive")

            df = df.rename(columns=rename_dict)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Showing **{len(rows)}** registered donor(s) from PostgreSQL.")
        else:
            st.info("No registered donors found matching the specified filters.")

    except Exception as exc:
        st.error("Failed to retrieve donor records from PostgreSQL.")
        st.exception(exc)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3: Donor Detail & Actions (UPDATE & DELETE / DEACTIVATE)
# ══════════════════════════════════════════════════════════════════════════════
with tab_detail:
    st.header("Donor Profile & Management Actions")
    st.write("Inspect a specific donor profile, update contact information, or manage donor status.")

    lookup_id = st.number_input("Enter Donor ID", min_value=1, step=1, value=1, key="lk_donor_id")

    if st.button("Load Donor Profile", key="btn_load_donor"):
        st.session_state["loaded_donor_id"] = int(lookup_id)

    target_id = st.session_state.get("loaded_donor_id", int(lookup_id))

    try:
        donor = get_donor_by_id(target_id)
        if donor is None:
            st.warning(f"No donor found with Donor ID **#{target_id}** in the database.")
        else:
            d_id, d_name, d_phone, d_bg, d_loc, *extra = donor
            is_active = extra[0] if extra else True
            status_badge = "🟢 Active" if is_active else "🔴 Inactive (Deactivated)"

            st.markdown(f"""
| Field | Database Record |
|---|---|
| **Donor ID** | #{d_id} |
| **Full Name** | {d_name} |
| **Blood Group** | **{d_bg}** |
| **Phone Number** | {d_phone} |
| **Location** | {d_loc or '—'} |
| **Account Status** | **{status_badge}** |
""")

            # ── Action 1: UPDATE Donor Details ──
            with st.expander("✏️ Edit Donor Details"):
                with st.form(f"form_update_donor_{d_id}"):
                    u_name = st.text_input("Full Name", value=d_name, max_chars=50)
                    u_phone = st.text_input("Phone Number (10 digits)", value=d_phone, max_chars=10)
                    u_bg = st.selectbox(
                        "Blood Group",
                        VALID_BLOOD_GROUPS,
                        index=list(VALID_BLOOD_GROUPS).index(d_bg),
                    )
                    u_loc = st.text_input("Location", value=d_loc or "", max_chars=100)
                    save_btn = st.form_submit_button("💾 Save Changes")

                if save_btn:
                    try:
                        ok = update_donor(d_id, u_name, u_phone, u_bg, u_loc)
                        if ok:
                            st.success("Donor record updated successfully in PostgreSQL.")
                            st.rerun()
                        else:
                            st.warning("No changes were applied.")
                    except ValueError as ve:
                        st.error(str(ve))
                    except Exception as exc:
                        st.error("Failed to update donor record.")
                        st.exception(exc)

            # ── Action 2: Deactivate / Reactivate (Logical Delete) ──
            with st.expander("🔒 Deactivation & Reactivation (Logical Delete)"):
                st.caption(
                    "Deactivating a donor prevents them from participating in new donations while "
                    "preserving all historical donation and medical testing records."
                )
                col_act1, col_act2 = st.columns(2)
                with col_act1:
                    if is_active:
                        if st.button(f"🚫 Deactivate Donor #{d_id}", key=f"btn_deact_{d_id}"):
                            try:
                                deactivate_donor(d_id)
                                st.success(f"Donor #{d_id} has been deactivated.")
                                st.rerun()
                            except Exception as exc:
                                st.error("Failed to deactivate donor.")
                                st.exception(exc)
                    else:
                        if st.button(f"✅ Reactivate Donor #{d_id}", key=f"btn_react_{d_id}"):
                            try:
                                reactivate_donor(d_id)
                                st.success(f"Donor #{d_id} has been reactivated.")
                                st.rerun()
                            except Exception as exc:
                                st.error("Failed to reactivate donor.")
                                st.exception(exc)

            # ── Action 3: DELETE Donor (Physical Delete) ──
            with st.expander("🗑️ Delete Donor Record (Physical Delete)"):
                st.warning(
                    "⚠️ Physical deletion permanently removes the donor record from PostgreSQL. "
                    "By database integrity rules, deletion is **strictly prohibited** if any donation records exist."
                )
                confirm_delete = st.checkbox(f"I understand and want to permanently delete Donor #{d_id}", key=f"chk_del_{d_id}")
                if st.button(f"Delete Donor #{d_id}", key=f"btn_del_{d_id}", type="primary"):
                    if not confirm_delete:
                        st.error("Please confirm the deletion checkbox above before proceeding.")
                    else:
                        try:
                            delete_donor(d_id)
                            st.success(f"Donor #{d_id} successfully deleted from the database.")
                            del st.session_state["loaded_donor_id"]
                            st.rerun()
                        except ValueError as ve:
                            st.error(str(ve))
                        except Exception as exc:
                            st.error("Deletion failed due to a database error.")
                            st.exception(exc)

            # ── Donation History ──
            st.divider()
            st.subheader("Donation History")
            h_cols, h_rows = get_donation_history(int(d_id))
            if h_rows:
                import pandas as pd
                hdf = pd.DataFrame(h_rows, columns=h_cols)
                hdf = hdf.rename(columns={
                    "donation_id": "Donation ID",
                    "bank_name": "Blood Bank",
                    "donation_date": "Donation Date",
                    "quantity_ml": "Volume (ml)",
                    "unit_id": "Unit ID",
                    "component": "Component",
                    "blood_group": "Unit Group",
                    "status": "Unit Status",
                    "expiry_date": "Expiry Date",
                })
                hdf["Component"] = hdf["Component"].str.replace("_", " ").str.title()
                st.dataframe(hdf, use_container_width=True, hide_index=True)
            else:
                st.info(f"No donation history recorded yet for Donor #{d_id}.")

    except Exception as exc:
        st.error("Failed to load donor profile.")
        st.exception(exc)
