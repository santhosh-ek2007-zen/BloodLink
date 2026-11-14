"""
pages/allocation.py — Blood allocation and issue page.
"""

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT), str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.allocation_service import (
    allocate_units,
    find_eligible_units,
    get_allocation_history,
    get_request_allocation_demand,
    issue_units,
)
from services.request_service import get_request_detail

st.title("🩸 Blood Allocation")
st.caption(
    "Allocate compatible blood units to hospital requests. "
    "All allocations use database transactions and row-level locking "
    "to prevent concurrent duplicate allocation."
)

tab_allocate, tab_issue, tab_history = st.tabs(
    ["Allocate Units", "Issue Units", "Allocation History"]
)

# ── Tab 1: Allocate Units ──────────────────────────────────────────────────
with tab_allocate:
    st.subheader("Allocate Compatible Units to a Request")

    req_id = st.number_input("Request ID", min_value=1, step=1, key="alloc_req_id")

    if st.button("Preview Eligible Units"):
        try:
            req = get_request_detail(int(req_id))
            if req is None:
                st.warning(f"No request found with ID {req_id}.")
            else:
                (rid, hname, _, _, comp, rgroup, qty, urgency, rdate, status) = req

                # Show demand summary
                demand = get_request_allocation_demand(int(req_id))
                if demand:
                    already_res = demand["already_reserved"]
                    already_iss = demand["already_issued"]
                    remaining   = demand["remaining_demand"]
                    col_a, col_b, col_c, col_d = st.columns(4)
                    col_a.metric("Requested", qty)
                    col_b.metric("Reserved",  already_res)
                    col_c.metric("Issued",    already_iss)
                    col_d.metric("Still Needed", remaining,
                                 delta=f"-{already_res + already_iss}" if (already_res + already_iss) > 0 else None,
                                 delta_color="inverse")

                st.info(
                    f"**Request {rid}** — {hname} | "
                    f"{comp.replace('_',' ').title()} | {rgroup} | "
                    f"Qty: {qty} | Urgency: {urgency} | Status: **{status}**"
                )

                if status in ("fulfilled", "cancelled"):
                    st.warning(f"This request is already **{status}**. No allocation needed.")
                elif demand and demand["remaining_demand"] == 0:
                    st.warning(
                        f"All {qty} unit(s) are already reserved or issued. "
                        "No further allocation is needed."
                    )
                else:
                    el_cols, el_rows = find_eligible_units(int(req_id))
                    if el_rows:
                        import pandas as pd
                        df = pd.DataFrame(el_rows, columns=el_cols)
                        df = df.rename(columns={
                            "unit_id": "Unit ID", "bank_name": "Blood Bank",
                            "donor_group": "Donor Group", "component": "Component",
                            "expiry_date": "Expires", "days_until_expiry": "Days Left",
                        })
                        df["Component"] = df["Component"].str.replace("_", " ").str.title()
                        st.dataframe(df, use_container_width=True, hide_index=True)
                        st.caption(
                            f"{len(el_rows)} eligible unit(s) found. "
                            "Use the form below to allocate."
                        )
                    else:
                        st.warning(
                            "No eligible units are currently available for this request. "
                            "Check inventory status and compatibility rules."
                        )
        except Exception as exc:
            st.error("Failed to load request or eligible units.")
            st.exception(exc)

    st.divider()

    with st.form("allocate_form"):
        alloc_req_id = st.number_input(
            "Request ID to Allocate", min_value=1, step=1, key="alloc_form_req"
        )
        alloc_qty = st.number_input(
            "Number of Units to Reserve", min_value=1, max_value=50, step=1, value=1
        )
        alloc_actor = st.text_input("Actor", value="staff")
        alloc_btn = st.form_submit_button("🔒 Reserve Units")

    if alloc_btn:
        try:
            result = allocate_units(
                request_id=int(alloc_req_id),
                quantity=int(alloc_qty),
                actor=alloc_actor or "staff",
            )
            if result["error"]:
                st.error(f"Allocation failed: {result['error']}")
            else:
                donor_info = ""
                if result.get("donor_summary"):
                    donor_info = " | Donors: " + ", ".join(result["donor_summary"])
                st.success(
                    f"✅ **{result['allocated']}** unit(s) reserved for Request {alloc_req_id}."
                    f"{donor_info} | "
                    f"Status: **{result['request_status']}** | "
                    f"Still needed: {result['still_needed']}."
                )
                if result["still_needed"] > 0:
                    st.info(
                        f"⚠️ {result['still_needed']} more unit(s) still needed to fully fulfil this request. "
                        "Run allocation again or check if more compatible inventory is available."
                    )
        except Exception as exc:
            st.error("Allocation failed.")
            st.exception(exc)

# ── Tab 2: Issue Units ─────────────────────────────────────────────────────
with tab_issue:
    st.subheader("Issue Reserved Units to Hospital")
    st.info(
        "This marks all **reserved** units for a request as **issued**, "
        "and updates the request status to **fulfilled** or **partially_fulfilled**."
    )

    with st.form("issue_form"):
        issue_req_id = st.number_input("Request ID", min_value=1, step=1)
        issue_actor = st.text_input("Actor", value="staff")
        issue_btn = st.form_submit_button("✅ Issue All Reserved Units")

    if issue_btn:
        try:
            result = issue_units(
                request_id=int(issue_req_id),
                actor=issue_actor or "staff",
            )
            if result["error"]:
                st.error(f"Issue failed: {result['error']}")
            else:
                st.success(
                    f"✅ **{result['issued']}** unit(s) issued for Request {issue_req_id}. "
                    f"Request status: **{result['request_status']}**."
                )
        except Exception as exc:
            st.error("Issue operation failed.")
            st.exception(exc)

# ── Tab 3: Allocation History ──────────────────────────────────────────────
with tab_history:
    st.subheader("Allocation History for a Request")
    st.caption(
        "Shows every unit reserved or issued for a request, "
        "including the donor and blood bank that contributed each unit."
    )

    hist_req_id = st.number_input("Request ID", min_value=1, step=1, key="hist_req_id")

    if st.button("Load History"):
        try:
            h_cols, h_rows = get_allocation_history(int(hist_req_id))
            if h_rows:
                import pandas as pd
                df = pd.DataFrame(h_rows, columns=h_cols)
                df = df.rename(columns={
                    "allocation_id":    "Alloc ID",
                    "request_id":       "Request ID",
                    "hospital_name":    "Hospital",
                    "unit_id":          "Unit ID",
                    "donor_id":         "Donor ID",
                    "donor_name":       "Donor",
                    "donation_id":      "Donation ID",
                    "blood_group":      "Blood Group",
                    "component":        "Component",
                    "bank_name":        "Blood Bank",
                    "allocation_status": "Status",
                    "allocated_at":     "Allocated At",
                    "issued_at":        "Issued At",
                    "cancelled_at":     "Cancelled At",
                })
                df["Component"] = df["Component"].str.replace("_", " ").str.title()
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Donor breakdown summary
                if "Donor" in df.columns:
                    st.markdown("**Donor contribution summary:**")
                    summary = (
                        df.groupby(["Donor ID", "Donor"])
                        .size()
                        .reset_index(name="Units")
                    )
                    st.dataframe(summary, use_container_width=True, hide_index=True)
            else:
                st.info("No allocation records found for this request.")
        except Exception as exc:
            st.error("Failed to load allocation history.")
            st.exception(exc)

