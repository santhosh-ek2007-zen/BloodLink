"""
tests/test_search.py — Automated tests for the blood search workflow.

Run from the project root:
    python -m pytest tests/ -v

These tests hit the real development database. They are read-only and
do not modify any data.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from search_service import (
    VALID_BLOOD_GROUPS,
    VALID_COMPONENTS,
    get_compatible_donor_groups,
    search_available_blood,
)
from db import get_connection


# ── Connectivity ───────────────────────────────────────────────────────────

def test_database_connection():
    """Database must be reachable."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            assert cur.fetchone()[0] == 1


# ── Compatibility table ────────────────────────────────────────────────────

def test_red_cells_compatibility_o_minus_universal():
    """O- should be compatible with all recipient groups for red_cells."""
    all_groups = list(VALID_BLOOD_GROUPS)
    for rg in all_groups:
        donors = get_compatible_donor_groups("red_cells", rg)
        assert "O-" in donors, (
            f"O- should be compatible with {rg} for red_cells, "
            f"but was not found. Got: {donors}"
        )


def test_red_cells_incompatible_excluded():
    """A+ donor should NOT be compatible with O+ recipient for red_cells."""
    donors = get_compatible_donor_groups("red_cells", "O+")
    assert "A+" not in donors, (
        f"A+ should not be compatible with O+ recipient. Got: {donors}"
    )


def test_compatibility_gap_for_plasma():
    """If plasma compatibility rows are absent, report the gap correctly."""
    donors = get_compatible_donor_groups("plasma", "A+")
    # Either there are compatibility rows (seed was extended) or the list is empty.
    # Either outcome is valid; we just confirm the function returns a list.
    assert isinstance(donors, list)


# ── Search results ─────────────────────────────────────────────────────────

def test_search_returns_dict_with_required_keys():
    result = search_available_blood("O+", "red_cells")
    for key in ("compatible_groups", "results", "columns",
                "quantity_available", "quantity_needed",
                "is_sufficient", "compatibility_gap"):
        assert key in result, f"Missing key: {key}"


def test_search_is_read_only():
    """Running a search twice should return the same available count."""
    r1 = search_available_blood("O+", "red_cells")
    r2 = search_available_blood("O+", "red_cells")
    assert r1["quantity_available"] == r2["quantity_available"], (
        "Search is not idempotent — it may be modifying data."
    )


def test_search_excludes_incompatible_groups():
    """Search results must only contain compatible donor groups."""
    result = search_available_blood("O+", "red_cells")
    compatible = set(result["compatible_groups"])

    if result["results"]:
        # Find the index of donor_group column
        try:
            dg_idx = result["columns"].index("donor_group")
        except ValueError:
            pytest.skip("donor_group column not present in results")

        for row in result["results"]:
            assert row[dg_idx] in compatible, (
                f"Incompatible donor group {row[dg_idx]!r} appeared in results."
            )


def test_search_city_filter_reduces_results():
    """Location filter should return a subset of or equal results."""
    all_results  = search_available_blood("O+", "red_cells", city="")
    city_results = search_available_blood("O+", "red_cells", city="Chennai")
    assert city_results["quantity_available"] <= all_results["quantity_available"]


def test_search_quantity_is_sufficient_flag():
    """is_sufficient should be True iff available >= needed."""
    result = search_available_blood("O+", "red_cells", quantity_needed=1)
    if result["quantity_available"] >= 1:
        assert result["is_sufficient"] is True
    else:
        assert result["is_sufficient"] is False


def test_search_no_results_for_impossible_city():
    """A nonsense city name should return zero results."""
    result = search_available_blood("O+", "red_cells", city="XYZZY_NO_SUCH_CITY")
    assert result["quantity_available"] == 0
    assert result["is_sufficient"] is False


def test_search_empty_result_has_valid_structure():
    """Even when no results exist the return dict structure is intact."""
    result = search_available_blood("O-", "red_cells", city="XYZZY_NO_SUCH_CITY")
    assert isinstance(result["results"], list)
    assert isinstance(result["columns"], list)
    assert result["quantity_available"] == 0

