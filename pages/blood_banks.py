"""
pages/blood_banks.py — Complete CRUD management for blood banks.

Features:
- Create: Add a new blood bank facility.
- Read: View and search all registered blood banks.
- Update: Edit blood bank name, address, and phone number.
- Delete: Safe deletion restricted by foreign-key dependencies (donation records).
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT), str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.blood_bank_service import (
    create_blood_bank,
    delete_blood_bank,
    get_blood_bank_by_id,
    list_blood_banks,
    update_blood_bank,
)

st.title("🏢 Blood Bank Management")
st.caption("Manage blood bank facilities, storage centres, and collection contact points.")

tab_directory, tab_register, tab_manage = st.tabs(
    ["🏢 Blood Bank Directory", "➕ Add Blood Bank", "✏️ Edit & Manage Blood Bank"]
)

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1: Directory (READ)
# ══════════════════════════════════════════════════════════════════════════════
with tab_directory:
    st.header("Registered Blood Banks")
    search_q = st.text_input("Search Blood Bank by Name", placeholder="e.g. Chennai Central", key="bank_search")

    try:
        cols, rows = list_blood_banks(search_name=search_q)
        if rows:
            df = pd.DataFrame(rows, columns=cols)
            df = df.rename(columns={
                "bank_id": "Bank ID",
                "bank_name": "Blood Bank Name",
                "address": "Address",
                "phone": "Phone Number",
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Showing **{len(rows)}** registered blood bank(s).")
        else:
            st.info("No blood banks found.")
    except Exception as exc:
        st.error("Failed to load blood banks from PostgreSQL.")
        st.exception(exc)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2: Register (CREATE)
# ══════════════════════════════════════════════════════════════════════════════
with tab_register:
    st.header("Add New Blood Bank Facility")
    with st.form("form_register_blood_bank"):
        b_name = st.text_input("Blood Bank Name *", max_chars=50, placeholder="e.g. Metro Blood Centre")
        b_addr = st.text_area("Address *", max_chars=200, placeholder="e.g. Anna Salai, Chennai")
        b_phone = st.text_input("Phone Number (10 digits) *", max_chars=10, placeholder="e.g. 9100000010", help="Must be exactly 10 digits.")
        submit_btn = st.form_submit_button("💾 Register Blood Bank", use_container_width=True)

    if submit_btn:
        try:
            new_id = create_blood_bank(b_name, b_addr, b_phone)
            st.success(f"✅ Blood bank successfully registered with ID: **#{new_id}**.")
            st.rerun()
        except ValueError as ve:
            st.error(str(ve))
        except Exception as exc:
            st.error("Failed to register blood bank in database.")
            st.exception(exc)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3: Edit & Manage (UPDATE & DELETE)
# ══════════════════════════════════════════════════════════════════════════════
with tab_manage:
    st.header("Edit & Manage Blood Bank Record")
    select_id = st.number_input("Blood Bank ID", min_value=1, step=1, value=1, key="bank_manage_id")

    if st.button("Load Blood Bank Details", key="btn_load_bank"):
        st.session_state["loaded_bank_id"] = int(select_id)

    target_id = st.session_state.get("loaded_bank_id", int(select_id))

    try:
        bank = get_blood_bank_by_id(target_id)
        if not bank:
            st.warning(f"No blood bank found with ID **#{target_id}**.")
        else:
            bid, bname, baddr, bphone = bank
            st.markdown(f"""
| Field | Current Database Value |
|---|---|
| **Bank ID** | #{bid} |
| **Blood Bank Name** | {bname} |
| **Address** | {baddr} |
| **Phone Number** | {bphone} |
""")

            # Update Form
            with st.expander("✏️ Update Blood Bank Information", expanded=True):
                with st.form(f"form_update_bank_{bid}"):
                    edit_name = st.text_input("Blood Bank Name", value=bname, max_chars=50)
                    edit_addr = st.text_area("Address", value=baddr, max_chars=200)
                    edit_phone = st.text_input("Phone Number (10 digits)", value=bphone, max_chars=10)
                    update_btn = st.form_submit_button("💾 Save Updates")

                if update_btn:
                    try:
                        ok = update_blood_bank(bid, edit_name, edit_addr, edit_phone)
                        if ok:
                            st.success("Blood bank details updated successfully in PostgreSQL.")
                            st.rerun()
                        else:
                            st.warning("No changes were made.")
                    except ValueError as ve:
                        st.error(str(ve))
                    except Exception as exc:
                        st.error("Database error occurred while updating.")
                        st.exception(exc)

            # Delete Form
            with st.expander("🗑️ Delete Blood Bank Record"):
                st.warning(
                    "⚠️ Deletion is permanently restricted by relational integrity if any donation "
                    "records were received at this blood bank."
                )
                chk_del = st.checkbox(f"Confirm deletion of Blood Bank #{bid} ('{bname}')", key=f"del_chk_bank_{bid}")
                if st.button(f"Permanently Delete Blood Bank #{bid}", key=f"btn_del_bank_{bid}", type="primary"):
                    if not chk_del:
                        st.error("Please tick the confirmation checkbox before deleting.")
                    else:
                        try:
                            delete_blood_bank(bid)
                            st.success(f"Blood bank #{bid} successfully deleted.")
                            if "loaded_bank_id" in st.session_state:
                                del st.session_state["loaded_bank_id"]
                            st.rerun()
                        except ValueError as ve:
                            st.error(f"Referential Integrity Restriction: {ve}")
                        except Exception as exc:
                            st.error("Deletion failed due to a database error.")
                            st.exception(exc)

    except Exception as exc:
        st.error("Failed to load blood bank details.")
        st.exception(exc)

