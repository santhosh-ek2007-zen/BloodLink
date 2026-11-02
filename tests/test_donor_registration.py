"""
tests/test_donor_registration.py — Unit and integration tests for donor registration.

Can be run with:
    python tests/test_donor_registration.py
or with pytest (if installed):
    python -m pytest tests/test_donor_registration.py
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import psycopg
from donor_service import (
    VALID_BLOOD_GROUPS,
    mask_phone,
    register_donor,
    validate_blood_group,
    validate_name,
    validate_phone,
    get_donor_by_id,
    list_donors,
)
from db import get_connection


# ══════════════════════════════════════════════════════════════════════════════
# 1. Validation Unit Tests (No Database Required)
# ══════════════════════════════════════════════════════════════════════════════

def test_validate_name_valid():
    assert validate_name("Ananya Rao") == "Ananya Rao"
    assert validate_name("Dr. J. Watson-Smith") == "Dr. J. Watson-Smith"
    assert validate_name("O'Connor") == "O'Connor"


def test_validate_name_invalid():
    for bad in ["", "   "]:
        try:
            validate_name(bad)
            assert False, f"Expected ValueError for empty name: {bad!r}"
        except ValueError:
            pass

    try:
        validate_name("A")
        assert False, "Expected ValueError for single character name"
    except ValueError:
        pass

    try:
        validate_name("A" * 51)
        assert False, "Expected ValueError for name > 50 chars"
    except ValueError:
        pass

    try:
        validate_name("User123")
        assert False, "Expected ValueError for name with numbers"
    except ValueError:
        pass


def test_validate_phone_valid():
    assert validate_phone("9876543210") == "9876543210"
    assert validate_phone("+91 9876543210") == "+91 9876543210"
    assert validate_phone("044-22334455") == "044-22334455"


def test_validate_phone_invalid():
    for bad in ["", "   ", "12345", "1234567890123456", "98765abcde", "+91-abc"]:
        try:
            validate_phone(bad)
            assert False, f"Expected ValueError for invalid phone: {bad!r}"
        except ValueError:
            pass


def test_validate_blood_group_valid():
    for bg in VALID_BLOOD_GROUPS:
        assert validate_blood_group(bg) == bg


def test_validate_blood_group_invalid():
    for bad in ["", "XYZ", "A", "O", "C+"]:
        try:
            validate_blood_group(bad)
            assert False, f"Expected ValueError for invalid blood group: {bad!r}"
        except ValueError:
            pass


def test_mask_phone():
    assert mask_phone("9000000001") == "******0001"
    assert mask_phone("+91 9000000002") == "**********0002"
    assert mask_phone("") == "—"


# ══════════════════════════════════════════════════════════════════════════════
# 2. Database Integration Tests
# ══════════════════════════════════════════════════════════════════════════════

def run_db_tests():
    """Runs database tests if PostgreSQL is accessible, skips gracefully otherwise."""
    print("Testing PostgreSQL connection for integration tests...")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
    except Exception as e:
        print(f"Skipping DB tests: PostgreSQL is not reachable ({e})")
        return

    print("PostgreSQL connected! Running integration tests...")
    test_phone_1 = "9999900001"
    test_phone_2 = "9999900002"
    test_phone_3 = "9999900003"
    cleanup_phones = [test_phone_1, test_phone_2, test_phone_3]

    try:
        # 1. Register valid donor
        donor_id = register_donor(
            name="Integration Test Donor",
            phone=test_phone_1,
            blood_group="O+",
            location="Chennai",
        )
        assert isinstance(donor_id, int) and donor_id > 0
        print(f"PASS: Donor registered with ID {donor_id}")

        # 2. Retrieve donor
        record = get_donor_by_id(donor_id)
        assert record is not None
        assert record[0] == donor_id
        assert record[1] == "Integration Test Donor"
        assert record[2] == test_phone_1
        assert record[3] == "O+"
        print("PASS: Donor record verified in PostgreSQL")

        # 3. Duplicate phone test
        try:
            register_donor(
                name="Duplicate Donor",
                phone=test_phone_1,
                blood_group="A+",
                location="Chennai",
            )
            assert False, "Expected duplicate phone registration to fail"
        except ValueError as ve:
            assert "Duplicate Registration" in str(ve)
            print("PASS: Duplicate registration safely blocked")

        # 4. List donors reflects masked phone
        cols, rows = list_donors(search_name="Integration Test", mask_contacts=True)
        assert len(rows) >= 1
        assert rows[0][4] == "******0001"
        print("PASS: Donor list displays privacy-masked phone")

    finally:
        # Cleanup test records
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM donor WHERE phone = ANY(%s);", (cleanup_phones,))
            conn.commit()
        print("PASS: Test records cleaned up from database")


def main():
    print("=== Running Donor Registration Unit Tests ===")
    test_validate_name_valid()
    print("PASS: test_validate_name_valid")
    test_validate_name_invalid()
    print("PASS: test_validate_name_invalid")
    test_validate_phone_valid()
    print("PASS: test_validate_phone_valid")
    test_validate_phone_invalid()
    print("PASS: test_validate_phone_invalid")
    test_validate_blood_group_valid()
    print("PASS: test_validate_blood_group_valid")
    test_validate_blood_group_invalid()
    print("PASS: test_validate_blood_group_invalid")
    test_mask_phone()
    print("PASS: test_mask_phone")

    print("\n=== Running Database Integration Tests ===")
    run_db_tests()
    print("\nAll donor registration tests completed successfully!")


if __name__ == "__main__":
    main()
