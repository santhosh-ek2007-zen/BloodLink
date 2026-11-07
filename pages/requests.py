"""
pages/requests.py — Blood request management page.

Features:
- View Requests: Multi-parameter filtering by status, component, and hospital.
- Create Request: Register a new blood requisition for a hospital.
- Edit Request: Modify requested quantity and urgency prior to allocation.
- Cancel Request: Advance pending request status to 'cancelled'.
- Delete Request: Restricted physical deletion permitted only when zero allocation records exist.
"""

import sys
from pathlib import Path

import streamlit as st
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT), str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.request_service import (
    VALID_COMPONENTS,
    VALID_GROUPS,
    VALID_URGENCIES,
    cancel_request,
    create_request,
    delete_request,
    get_request_detail,
    list_hospitals,
    list_requests,
    update_request,
)
from services.allocation_service import get_allocation_history

st.title("📋 Blood Requests Management")
st.caption("Coordinate hospital blood requisitions, edit unallocated demands, and track fulfillment lifecycles.")

tab_list, tab_create, tab_detail = st.tabs(
    ["📋 View Requests", "➕ Create Request", "🔍 Request Detail & Actions"]
)

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1: View Requests (READ)
# ══════════════════════════════════════════════════════════════════════════════
with tab_list:
    st.subheader("Filter Blood Requests")

    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox(
            "Status",
            ["All", "pending", "partially_fulfilled", "fulfilled", "cancelled"],
            key="req_status",
        )
    with col2:
        comp_filter = st.selectbox(
            "Component",
            ["All"] + list(VALID_COMPONENTS),
            format_func=lambda x: x.replace("_", " ").title() if x != "All" else "All",
            key="req_comp",
        )
    with col3:
        hosp_filter = st.number_input(
            "Hospital ID (0 = all)", min_value=0, step=1, value=0, key="req_hosp"
        )

    if st.button("Load Requests", key="btn_load_reqs"):
        try:
            cols, rows = list_requests(
                status="" if status_filter == "All" else status_filter,
                hospital_id=int(hosp_filter) if hosp_filter > 0 else None,
                component="" if comp_filter == "All" else comp_filter,
            )
            if rows:
                df = pd.DataFrame(rows, columns=cols)
                df = df.rename(columns={
                    "request_id": "ID", "hospital_name": "Hospital",
                    "component": "Component", "recipient_group": "Recipient Group",
                    "quantity_requested": "Qty Requested", "urgency": "Urgency",
                    "request_date": "Date", "status": "Status",
                    "issued_units": "Issued", "reserved_units": "Reserved",
                    "still_needed": "Still Needed",
                })
                df["Component"] = df["Component"].str.replace("_", " ").str.title()
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.caption(f"{len(rows)} request(s) found.")
            else:
                st.info("No requests match the selected filters.")
        except Exception as exc:
            st.error("Failed to load requests.")
            st.exception(exc)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2: Create Request (CREATE)
# ══════════════════════════════════════════════════════════════════════════════
with tab_create:
    st.subheader("Create a Blood Request")

    hospitals = list_hospitals()
    hosp_map = {f"{h[1]} (ID #{h[0]})": h[0] for h in hospitals}

    with st.form("create_request_form"):
        hosp_sel = st.selectbox(
            "Hospital *",
            options=list(hosp_map.keys()) if hosp_map else ["No hospitals found"],
        )
        col1, col2 = st.columns(2)
        with col1:
            req_component = st.selectbox(
                "Blood Component *",
                VALID_COMPONENTS,
                format_func=lambda x: x.replace("_", " ").title(),
            )
            req_group = st.selectbox("Recipient Blood Group *", VALID_GROUPS)
        with col2:
            req_qty = st.number_input("Units Requested *", min_value=1, max_value=100, value=1)
            req_urgency = st.selectbox("Urgency *", VALID_URGENCIES)

        create_btn = st.form_submit_button("Submit Request", use_container_width=True)

    if create_btn:
        if not hosp_map:
            st.error("No hospitals available. Register a hospital first.")
        else:
            try:
                rid = create_request(
                    hospital_id=hosp_map[hosp_sel],
                    component=req_component,
                    recipient_group=req_group,
                    quantity_requested=int(req_qty),
                    urgency=req_urgency,
                )
                st.success(
                    f"✅ Blood request created. Request ID: **#{rid}**. "
                    "Proceed to the Allocation page to allocate compatible units."
                )
            except ValueError as ve:
                st.error(str(ve))
            except Exception as exc:
                st.error("Failed to create request.")
                st.exception(exc)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3: Request Detail & Actions (UPDATE & DELETE)
# ══════════════════════════════════════════════════════════════════════════════
with tab_detail:
    st.subheader("Request Detail & Management Actions")

    req_id_inp = st.number_input("Enter Request ID", min_value=1, step=1, key="det_req_id")

    if st.button("Load Request Details", key="btn_load_req"):
        st.session_state["loaded_req_id"] = int(req_id_inp)

    target_rid = st.session_state.get("loaded_req_id", int(req_id_inp))

    try:
        req = get_request_detail(target_rid)
        if req is None:
            st.warning(f"No blood request found with ID **#{target_rid}**.")
        else:
            (rid, hname, haddr, hphone, comp, rgroup,
             qty, urgency, req_date, status) = req

            st.markdown(f"""
| Field | Value |
|---|---|
| **Request ID** | #{rid} |
| **Hospital** | {hname} |
| **Hospital Address** | {haddr} |
| **Hospital Phone** | {hphone} |
| **Component** | {comp.replace('_', ' ').title()} |
| **Recipient Blood Group** | **{rgroup}** |
| **Quantity Requested** | {qty} unit(s) |
| **Urgency** | **{urgency}** |
| **Requested At** | {req_date} |
| **Current Status** | **'{status}'** |
""")

            # ── Action 1: UPDATE Request Details (Before Allocation) ──
            with st.expander("✏️ Edit Request Details (Quantity & Urgency)", expanded=(status == "pending")):
                if status != "pending":
                    st.info(f"Editing is locked because this request is currently '{status}'.")
                else:
                    with st.form(f"form_edit_req_{rid}"):
                        new_qty = st.number_input("New Quantity Requested *", min_value=1, max_value=100, value=int(qty))
                        new_urg = st.selectbox(
                            "New Urgency *",
                            VALID_URGENCIES,
                            index=list(VALID_URGENCIES).index(urgency),
                        )
                        save_req_btn = st.form_submit_button("💾 Save Request Updates")

                    if save_req_btn:
                        try:
                            update_request(rid, int(new_qty), new_urg)
                            st.success(f"✅ Request #{rid} updated successfully.")
                            st.rerun()
                        except ValueError as ve:
                            st.error(str(ve))
                        except Exception as exc:
                            st.error("Failed to update request.")
                            st.exception(exc)

            # ── Action 2: Cancel Request (Logical Close) ──
            if status in ("pending", "partially_fulfilled"):
                with st.expander("❌ Cancel Request"):
                    st.caption("Cancelling the request stops further allocations while preserving all prior transaction records.")
                    if st.button(f"Confirm Cancellation of Request #{rid}", key=f"btn_cancel_{rid}"):
                        try:
                            ok = cancel_request(rid)
                            if ok:
                                st.success(f"Request #{rid} has been cancelled.")
                                st.rerun()
                            else:
                                st.warning("Could not cancel request. It may have already been closed.")
                        except Exception as exc:
                            st.error("Failed to cancel request.")
                            st.exception(exc)

            # ── Action 3: DELETE Request (Physical Delete) ──
            with st.expander("🗑️ Delete Request (Physical Delete)"):
                st.warning(
                    "⚠️ Physical deletion permanently removes the request from PostgreSQL. "
                    "By referential integrity rules, deletion is **strictly prohibited** if any unit allocations exist."
                )
                chk_del_req = st.checkbox(f"Confirm deletion of Blood Request #{rid}", key=f"chk_del_req_{rid}")
                if st.button(f"Permanently Delete Request #{rid}", key=f"btn_del_req_{rid}", type="primary"):
                    if not chk_del_req:
                        st.error("Please confirm the deletion checkbox above before proceeding.")
                    else:
                        try:
                            delete_request(rid)
                            st.success(f"Request #{rid} successfully deleted from the database.")
                            if "loaded_req_id" in st.session_state:
                                del st.session_state["loaded_req_id"]
                            st.rerun()
                        except ValueError as ve:
                            st.error(f"Integrity Restriction: {ve}")
                        except Exception as exc:
                            st.error("Deletion failed due to a database error.")
                            st.exception(exc)

            # ── Linked Allocation Records ──
            st.divider()
            st.subheader("Linked Unit Allocations")
            a_cols, a_rows = get_allocation_history(rid)
            if a_rows:
                adf = pd.DataFrame(a_rows, columns=a_cols)
                adf = adf.rename(columns={
                    "allocation_id": "Alloc ID",
                    "unit_id": "Unit ID",
                    "blood_group": "Blood Group",
                    "component": "Component",
                    "bank_name": "Blood Bank",
                    "allocation_status": "Status",
                    "allocated_at": "Allocated At",
                    "issued_at": "Issued At",
                    "cancelled_at": "Cancelled At",
                })
                adf["Component"] = adf["Component"].str.replace("_", " ").str.title()
                st.dataframe(adf, use_container_width=True, hide_index=True)
            else:
                st.info("No units have been allocated to this request yet.")

    except Exception as exc:
        st.error("Failed to load request details.")
        st.exception(exc)
