"""
pages/hospitals.py — Complete CRUD management for hospitals.

Features:
- Create: Register a new hospital.
- Read: View and search all registered hospitals.
- Update: Edit hospital name, address, and phone number.
- Delete: Safe deletion restricted by foreign-key dependencies (blood requests).
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT), str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.hospital_service import (
    create_hospital,
    delete_hospital,
    get_hospital_by_id,
    list_hospitals,
    update_hospital,
)

st.title("🏥 Hospital Management")
st.caption("Manage registered hospitals, contact points, and requisition privileges.")

tab_directory, tab_register, tab_manage = st.tabs(
    ["📋 Hospital Directory", "➕ Register Hospital", "✏️ Edit & Manage Hospital"]
)

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1: Directory (READ)
# ══════════════════════════════════════════════════════════════════════════════
with tab_directory:
    st.header("Registered Hospitals")
    search_q = st.text_input("Search Hospital by Name", placeholder="e.g. Rajiv Gandhi", key="hosp_search")

    try:
        cols, rows = list_hospitals(search_name=search_q)
        if rows:
            df = pd.DataFrame(rows, columns=cols)
            df = df.rename(columns={
                "hospital_id": "Hospital ID",
                "hospital_name": "Hospital Name",
                "address": "Address",
                "phone": "Phone Number",
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Showing **{len(rows)}** registered hospital(s).")
        else:
            st.info("No hospitals found.")
    except Exception as exc:
        st.error("Failed to load hospitals from PostgreSQL.")
        st.exception(exc)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2: Register (CREATE)
# ══════════════════════════════════════════════════════════════════════════════
with tab_register:
    st.header("Register New Hospital")
    with st.form("form_register_hospital"):
        h_name = st.text_input("Hospital Name *", max_chars=50, placeholder="e.g. City General Hospital")
        h_addr = st.text_area("Address *", max_chars=200, placeholder="e.g. 100 Mount Road, Chennai")
        h_phone = st.text_input("Phone Number (10 digits) *", max_chars=10, placeholder="e.g. 9200000005", help="Must be exactly 10 digits.")
        submit_btn = st.form_submit_button("💾 Register Hospital", use_container_width=True)

    if submit_btn:
        try:
            new_id = create_hospital(h_name, h_addr, h_phone)
            st.success(f"✅ Hospital successfully registered with ID: **#{new_id}**.")
            st.rerun()
        except ValueError as ve:
            st.error(str(ve))
        except Exception as exc:
            st.error("Failed to register hospital in database.")
            st.exception(exc)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3: Edit & Manage (UPDATE & DELETE)
# ══════════════════════════════════════════════════════════════════════════════
with tab_manage:
    st.header("Edit & Manage Hospital Record")
    select_id = st.number_input("Hospital ID", min_value=1, step=1, value=1, key="hosp_manage_id")

    if st.button("Load Hospital Details", key="btn_load_hosp"):
        st.session_state["loaded_hosp_id"] = int(select_id)

    target_id = st.session_state.get("loaded_hosp_id", int(select_id))

    try:
        hosp = get_hospital_by_id(target_id)
        if not hosp:
            st.warning(f"No hospital found with ID **#{target_id}**.")
        else:
            hid, hname, haddr, hphone = hosp
            st.markdown(f"""
            | Field | Current Database Value |
            |---|---|
            | **Hospital ID** | #{hid} |
            | **Hospital Name** | {hname} |
            | **Address** | {haddr} |
            | **Phone Number** | {hphone} |
            """)

            # Update Form
            with st.expander("✏️ Update Hospital Information", expanded=True):
                with st.form(f"form_update_hosp_{hid}"):
                    edit_name = st.text_input("Hospital Name", value=hname, max_chars=50) or ""
                    edit_addr = st.text_area("Address", value=haddr, max_chars=200) or ""
                    edit_phone = st.text_input("Phone Number (10 digits)", value=hphone, max_chars=10) or ""
                    update_btn = st.form_submit_button("💾 Save Updates")

                if update_btn:
                    try:
                        ok = update_hospital(hid, edit_name, edit_addr, edit_phone)
                        if ok:
                            st.success("Hospital details updated successfully in PostgreSQL.")
                            st.rerun()
                        else:
                            st.warning("No changes were made.")
                    except ValueError as ve:
                        st.error(str(ve))
                    except Exception as exc:
                        st.error("Database error occurred while updating.")
                        st.exception(exc)

            # Delete Form
            with st.expander("🗑️ Delete Hospital Record"):
                st.warning(
                    "⚠️ Deletion is permanently restricted by relational integrity if any blood requests "
                    "are linked to this hospital."
                )
                chk_del = st.checkbox(f"Confirm deletion of Hospital #{hid} ('{hname}')", key=f"del_chk_hosp_{hid}")
                if st.button(f"Permanently Delete Hospital #{hid}", key=f"btn_del_hosp_{hid}", type="primary"):
                    if not chk_del:
                        st.error("Please tick the confirmation checkbox before deleting.")
                    else:
                        try:
                            delete_hospital(hid)
                            st.success(f"Hospital #{hid} successfully deleted.")
                            if "loaded_hosp_id" in st.session_state:
                                del st.session_state["loaded_hosp_id"]
                            st.rerun()
                        except ValueError as ve:
                            st.error(f"Referential Integrity Restriction: {ve}")
                        except Exception as exc:
                            st.error("Deletion failed due to a database error.")
                            st.exception(exc)

    except Exception as exc:
        st.error("Failed to load hospital details.")
        st.exception(exc)

