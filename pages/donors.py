"""
pages/donors.py — Donor registration and management page.

Features:
- Clear "Register as Donor" section with complete input validation.
- Concurrency-safe duplicate phone check and transaction management.
- Live PostgreSQL persistence and immediate confirmation.
- Privacy-conscious donor directory (masked phone numbers by default).
- Donor profile inspection, updates, and donation history.
"""

import sys
from pathlib import Path
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from donor_service import (
    VALID_BLOOD_GROUPS,
    get_donation_history,
    get_donor_by_id,
    list_donors,
    register_donor,
    update_donor,
)

st.title("👤 Donor Registration & Management")
st.caption(
    "Register voluntary blood donors, manage donor information, and track donation history. "
    "All records are persisted directly into PostgreSQL."
)

tab_register, tab_directory, tab_detail = st.tabs(
    ["📝 Register as Donor", "📋 Donor Directory", "🔍 Donor Detail & History"]
)

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1: Register as Donor
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
                placeholder="e.g. 9876543210 or +91 9876543210",
                max_chars=20,
                help="10 to 15 digits. Used to prevent duplicate registrations.",
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
        # Perform frontend checks
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
                # Backend registration with full validation, duplicate check, and transaction commit
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
# Tab 2: Donor Directory
# ══════════════════════════════════════════════════════════════════════════════
with tab_directory:
    st.header("Registered Donors Directory")
    st.write("Browse and filter registered donors directly from PostgreSQL.")

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        search_name = st.text_input("Search by Name", key="dir_name", placeholder="Search name...")
    with col_s2:
        bg_filter = st.selectbox("Filter Blood Group", ["All"] + list(VALID_BLOOD_GROUPS), key="dir_bg")
    with col_s3:
        loc_filter = st.text_input("Filter Location", key="dir_loc", placeholder="Search city...")

    # Privacy toggle for phone display
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
        )

        if rows:
            import pandas as pd
            df = pd.DataFrame(rows, columns=cols)
            df = df.rename(columns={
                "donor_id": "Donor ID",
                "donor_name": "Full Name",
                "blood_group": "Blood Group",
                "location": "Location",
                "phone": "Contact Number",
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Showing **{len(rows)}** registered donor(s) from PostgreSQL.")
        else:
            st.info("No registered donors found matching the specified filters.")

    except Exception as exc:
        st.error("Failed to retrieve donor records from PostgreSQL.")
        st.exception(exc)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3: Donor Detail & History
# ══════════════════════════════════════════════════════════════════════════════
with tab_detail:
    st.header("Donor Profile & History")
    st.write("Inspect a specific donor profile, view donation records, or update contact info.")

    lookup_id = st.number_input("Enter Donor ID", min_value=1, step=1, value=1, key="lk_donor_id")

    if st.button("Load Donor Profile", key="btn_load_donor"):
        try:
            donor = get_donor_by_id(int(lookup_id))
            if donor is None:
                st.warning(f"No donor found with Donor ID **#{lookup_id}** in the database.")
            else:
                d_id, d_name, d_phone, d_bg, d_loc = donor
                st.markdown(f"""
| Field | Database Record |
|---|---|
| **Donor ID** | #{d_id} |
| **Full Name** | {d_name} |
| **Blood Group** | **{d_bg}** |
| **Phone Number** | {d_phone} |
| **Location** | {d_loc or '—'} |
""")

                # Form to update donor
                with st.expander("✏️ Update Donor Details"):
                    with st.form(f"form_update_donor_{d_id}"):
                        u_name = st.text_input("Name", value=d_name, max_chars=50)
                        u_phone = st.text_input("Phone", value=d_phone, max_chars=20)
                        u_bg = st.selectbox(
                            "Blood Group",
                            VALID_BLOOD_GROUPS,
                            index=list(VALID_BLOOD_GROUPS).index(d_bg),
                        )
                        u_loc = st.text_input("Location", value=d_loc or "", max_chars=100)
                        save_btn = st.form_submit_button("Update Record")

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

                # History table
                st.subheader("Donation History")
                h_cols, h_rows = get_donation_history(int(lookup_id))
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
                    st.info(f"No donation history recorded yet for Donor #{lookup_id}.")

        except Exception as exc:
            st.error("Failed to load donor profile.")
            st.exception(exc)
