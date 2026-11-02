"""
pages/requests.py — Blood request management page.
"""

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from request_service import (
    VALID_COMPONENTS,
    VALID_GROUPS,
    VALID_URGENCIES,
    cancel_request,
    create_request,
    get_request_detail,
    list_hospitals,
    list_requests,
)

st.title("📋 Blood Requests")

tab_list, tab_create, tab_detail = st.tabs(
    ["View Requests", "Create Request", "Request Detail"]
)

# ── Tab 1: View Requests ───────────────────────────────────────────────────
with tab_list:
    st.subheader("Filter Requests")

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

    if st.button("Load Requests"):
        try:
            cols, rows = list_requests(
                status="" if status_filter == "All" else status_filter,
                hospital_id=int(hosp_filter) if hosp_filter > 0 else None,
                component="" if comp_filter == "All" else comp_filter,
            )
            if rows:
                import pandas as pd
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

# ── Tab 2: Create Request ──────────────────────────────────────────────────
with tab_create:
    st.subheader("Create a Blood Request")

    hospitals = list_hospitals()
    hosp_map = {f"{h[1]} (ID {h[0]})": h[0] for h in hospitals}

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

        create_btn = st.form_submit_button("Submit Request")

    if create_btn:
        if not hosp_map:
            st.error("No hospitals available. Add a hospital first.")
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
                    f"✅ Blood request created. Request ID: **{rid}**. "
                    "Go to the Allocation page to allocate units."
                )
            except ValueError as ve:
                st.error(str(ve))
            except Exception as exc:
                st.error("Failed to create request.")
                st.exception(exc)

# ── Tab 3: Request Detail ──────────────────────────────────────────────────
with tab_detail:
    st.subheader("View Request Details")

    req_id_inp = st.number_input("Request ID", min_value=1, step=1, key="det_req_id")

    if st.button("Load Request"):
        try:
            req = get_request_detail(int(req_id_inp))
            if req is None:
                st.warning(f"No request found with ID {req_id_inp}.")
            else:
                (rid, hname, haddr, hphone, comp, rgroup,
                 qty, urgency, req_date, status) = req
                st.markdown(f"""
| Field | Value |
|---|---|
| Request ID | {rid} |
| Hospital | {hname} |
| Hospital Address | {haddr} |
| Hospital Phone | {hphone} |
| Component | {comp.replace('_', ' ').title()} |
| Recipient Group | {rgroup} |
| Quantity Requested | {qty} |
| Urgency | **{urgency}** |
| Requested At | {req_date} |
| Status | **{status}** |
""")

                # Cancel option
                if status in ("pending", "partially_fulfilled"):
                    if st.button(f"❌ Cancel Request {rid}", key=f"cancel_{rid}"):
                        try:
                            ok = cancel_request(rid)
                            if ok:
                                st.success(f"Request {rid} has been cancelled.")
                                st.rerun()
                            else:
                                st.warning("Could not cancel — request may have changed.")
                        except Exception as exc:
                            st.error("Failed to cancel request.")
                            st.exception(exc)
        except Exception as exc:
            st.error("Failed to load request.")
            st.exception(exc)

