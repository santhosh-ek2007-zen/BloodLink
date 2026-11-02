"""
app/main.py — BloodLink Streamlit application entry point.

Launch from the project root:
    python -m streamlit run app/main.py

Navigation is handled by st.navigation(). Each page lives in
BloodLink/pages/ and is a self-contained Streamlit script.
"""

import sys
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────────────────────
# Ensures that `from db import get_connection` and service imports resolve
# correctly when the app is launched from the project root with:
#   python -m streamlit run app/main.py
_APP_DIR      = Path(__file__).resolve().parent        # BloodLink/app/
_PROJECT_ROOT = _APP_DIR.parent                        # BloodLink/
_SERVICES_DIR = _PROJECT_ROOT / "services"
_PAGES_DIR    = _PROJECT_ROOT / "pages"

for _p in [str(_APP_DIR), str(_SERVICES_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st

st.set_page_config(
    page_title="BloodLink",
    page_icon="🩸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Register pages ─────────────────────────────────────────────────────────
dashboard_page  = st.Page(str(_PAGES_DIR / "dashboard.py"),        title="Dashboard",       icon="🏠", default=True)
search_page     = st.Page(str(_PAGES_DIR / "emergency_search.py"), title="Find Blood Now",  icon="🚨")
donors_page     = st.Page(str(_PAGES_DIR / "donors.py"),           title="Donors",          icon="👤")
inventory_page  = st.Page(str(_PAGES_DIR / "inventory.py"),        title="Inventory",       icon="🏥")
requests_page   = st.Page(str(_PAGES_DIR / "requests.py"),         title="Blood Requests",  icon="📋")
allocation_page = st.Page(str(_PAGES_DIR / "allocation.py"),       title="Allocation",      icon="🩸")
history_page    = st.Page(str(_PAGES_DIR / "history.py"),          title="Status History",  icon="📜")
reports_page    = st.Page(str(_PAGES_DIR / "reports.py"),          title="Reports",         icon="📊")

pg = st.navigation(
    {
        "Overview":   [dashboard_page, search_page],
        "Management": [donors_page, inventory_page, requests_page, allocation_page],
        "Analytics":  [history_page, reports_page],
    }
)

pg.run()
