"""
pages/history.py — Status history tracking page.
"""

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT), str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from db import get_connection

st.title("📜 Status History")
st.caption(
    "Audit trail of blood unit status changes. "
    "Records are written by the application whenever a unit status changes."
)


def load_status_history(unit_id: int | None = None, limit: int = 100) -> tuple[list, list]:
    if unit_id:
        query = """
            SELECT
                sh.history_id,
                sh.unit_id,
                bu.blood_group,
                bu.component,
                sh.old_status,
                sh.new_status,
                sh.changed_at,
                sh.actor,
                sh.remarks
            FROM status_history AS sh
            JOIN blood_unit AS bu ON bu.unit_id = sh.unit_id
            WHERE sh.unit_id = %s
            ORDER BY sh.changed_at DESC, sh.history_id DESC
            LIMIT %s;
        """
        params = (unit_id, limit)
    else:
        query = """
            SELECT
                sh.history_id,
                sh.unit_id,
                bu.blood_group,
                bu.component,
                sh.old_status,
                sh.new_status,
                sh.changed_at,
                sh.actor,
                sh.remarks
            FROM status_history AS sh
            JOIN blood_unit AS bu ON bu.unit_id = sh.unit_id
            ORDER BY sh.changed_at DESC, sh.history_id DESC
            LIMIT %s;
        """
        params = (limit,)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = [d.name for d in cur.description]
            rows = cur.fetchall()

    return columns, rows


col1, col2 = st.columns(2)
with col1:
    filter_unit_id = st.number_input(
        "Filter by Unit ID (0 = all units)", min_value=0, step=1, value=0
    )
with col2:
    limit = st.number_input("Max records", min_value=10, max_value=500, value=100, step=10)

if st.button("Load History"):
    try:
        uid = int(filter_unit_id) if filter_unit_id > 0 else None
        cols, rows = load_status_history(uid, int(limit))

        if rows:
            import pandas as pd
            df = pd.DataFrame(rows, columns=cols)
            df = df.rename(columns={
                "history_id": "History ID", "unit_id": "Unit ID",
                "blood_group": "Blood Group", "component": "Component",
                "old_status": "Previous Status", "new_status": "New Status",
                "changed_at": "Changed At", "actor": "Actor", "remarks": "Remarks",
            })
            df["Component"] = df["Component"].str.replace("_", " ").str.title()
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"{len(rows)} record(s) shown.")
        else:
            st.info("No status history records found.")
    except Exception as exc:
        st.error("Failed to load status history.")
        st.exception(exc)

