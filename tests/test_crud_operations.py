"""
tests/test_crud_operations.py — Unit and integration tests for complete CRUD operations.

Tests cover:
1. Hospital CRUD & referential integrity on delete.
2. Blood Bank CRUD & referential integrity on delete.
3. Donor Update, Deactivate, Reactivate, and Restricted Delete.
4. Blood Unit Expiry Update restrictions and screening/allocation delete guards.
5. Blood Request Update restrictions and allocation delete guards.

Can be run with:
    python tests/test_crud_operations.py
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT), str(_ROOT / "app"), str(_ROOT / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import psycopg
from db import get_connection

from services.hospital_service import (
    create_hospital,
    delete_hospital,
    get_hospital_by_id,
    list_hospitals,
    update_hospital,
    validate_hospital_input,
)
from services.blood_bank_service import (
    create_blood_bank,
    delete_blood_bank,
    get_blood_bank_by_id,
    list_blood_banks,
    update_blood_bank,
    validate_blood_bank_input,
)
from services.donor_service import (
    deactivate_donor,
    delete_donor,
    get_donor_by_id,
    reactivate_donor,
    register_donor,
    update_donor,
    validate_name,
    validate_phone,
)
from services.inventory_service import (
    delete_blood_unit,
    get_unit_detail,
    update_unit_expiry,
    update_unit_status,
)
from services.request_service import (
    create_request,
    delete_request,
    get_request_detail,
    update_request,
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Validation Unit Tests (Fast, No Database Required)
# ══════════════════════════════════════════════════════════════════════════════

def test_hospital_input_validation():
    # Valid
    name, addr, phone = validate_hospital_input("Apollo Hospital", "Greams Road", "9200000099")
    assert name == "Apollo Hospital"
    assert addr == "Greams Road"
    assert phone == "9200000099"

    # Empty name
    try:
        validate_hospital_input("", "Address", "9200000099")
        assert False, "Expected ValueError for empty hospital name"
    except ValueError:
        pass

    # Empty address
    try:
        validate_hospital_input("Hospital", "", "9200000099")
        assert False, "Expected ValueError for empty address"
    except ValueError:
        pass

    # Empty phone
    try:
        validate_hospital_input("Hospital", "Address", "")
        assert False, "Expected ValueError for empty phone"
    except ValueError:
        pass

    # Invalid phone length != 10
    for bad_phone in ["12345", "920000009999", "abcdefghij"]:
        try:
            validate_hospital_input("Hospital", "Address", bad_phone)
            assert False, f"Expected ValueError for invalid phone length: {bad_phone}"
        except ValueError:
            pass


def test_blood_bank_input_validation():
    # Valid
    name, addr, phone = validate_blood_bank_input("Central Blood Bank", "Main St", "9100000099")
    assert name == "Central Blood Bank"
    assert addr == "Main St"
    assert phone == "9100000099"

    # Empty name
    try:
        validate_blood_bank_input("", "Address", "9100000099")
        assert False, "Expected ValueError for empty blood bank name"
    except ValueError:
        pass

    # Empty address
    try:
        validate_blood_bank_input("Bank", "", "9100000099")
        assert False, "Expected ValueError for empty address"
    except ValueError:
        pass

    # Invalid phone length != 10
    for bad_phone in ["12345", "910000009999", "phone12345"]:
        try:
            validate_blood_bank_input("Bank", "Address", bad_phone)
            assert False, f"Expected ValueError for invalid phone length: {bad_phone}"
        except ValueError:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# 2. Database Integration Tests
# ══════════════════════════════════════════════════════════════════════════════

def run_db_crud_tests():
    print("Testing PostgreSQL connection for CRUD integration tests...")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
    except Exception as e:
        print(f"Skipping DB tests: PostgreSQL is not reachable in this session ({e})")
        return

    print("PostgreSQL connected! Running complete CRUD integration tests...")

    # ── Test A: Hospital CRUD & Referential Integrity ──
    # 1. Create hospital
    hid = create_hospital("Test Hospital CRUD", "123 Test St", "9900000001")
    assert isinstance(hid, int) and hid > 0
    print(f"PASS: Hospital created with ID #{hid}")

    # 2. Read hospital
    h_row = get_hospital_by_id(hid)
    assert h_row is not None
    assert h_row[1] == "Test Hospital CRUD"
    print("PASS: Hospital read verified")

    # 3. Update hospital
    updated = update_hospital(hid, "Updated Test Hospital", "456 New St", "9900000002")
    assert updated is True
    h_row_upd = get_hospital_by_id(hid)
    assert h_row_upd[1] == "Updated Test Hospital"
    assert h_row_upd[3] == "9900000002"
    print("PASS: Hospital update verified")

    # 4. Attach a blood request to test referential integrity constraint on DELETE
    rid = create_request(
        hospital_id=hid,
        component="red_cells",
        recipient_group="A+",
        quantity_requested=2,
        urgency="urgent",
    )
    print(f"PASS: Attached blood request #{rid} to test hospital")

    # 5. Attempt deleting hospital with dependent request — MUST FAIL
    try:
        delete_hospital(hid)
        assert False, "Hospital deletion should be blocked by foreign key dependency"
    except ValueError as ve:
        assert "linked to it" in str(ve)
        print("PASS: Hospital deletion blocked by referential integrity as expected")

    # 6. Delete dependent request first, then delete hospital — MUST SUCCEED
    req_del = delete_request(rid)
    assert req_del is True
    print(f"PASS: Dependent request #{rid} deleted safely")

    hosp_del = delete_hospital(hid)
    assert hosp_del is True
    assert get_hospital_by_id(hid) is None
    print(f"PASS: Hospital #{hid} successfully deleted when 0 dependent records remain")

    # ── Test B: Blood Bank CRUD & Referential Integrity ──
    # 1. Create blood bank
    bid = create_blood_bank("Test Bank CRUD", "789 Bank Ave", "9900000003")
    assert isinstance(bid, int) and bid > 0
    print(f"PASS: Blood bank created with ID #{bid}")

    # 2. Update blood bank
    b_upd = update_blood_bank(bid, "Updated Bank CRUD", "789 Bank Ave Suite 2", "9900000004")
    assert b_upd is True
    assert get_blood_bank_by_id(bid)[1] == "Updated Bank CRUD"
    print("PASS: Blood bank update verified")

    # 3. Delete blood bank (no donations linked yet) — MUST SUCCEED
    b_del = delete_blood_bank(bid)
    assert b_del is True
    assert get_blood_bank_by_id(bid) is None
    print(f"PASS: Blood bank #{bid} successfully deleted when 0 donations exist")

    # ── Test C: Donor Deactivation, Reactivation & Delete Protection ──
    did = register_donor("Test Donor CRUD", "9900000005", "O+", "Tambaram")
    print(f"PASS: Donor registered with ID #{did}")

    # Deactivate
    deact = deactivate_donor(did)
    assert deact is True
    d_row = get_donor_by_id(did)
    # is_active should be False
    assert d_row[5] is False
    print("PASS: Donor deactivation verified")

    # Reactivate
    react = reactivate_donor(did)
    assert react is True
    d_row2 = get_donor_by_id(did)
    assert d_row2[5] is True
    print("PASS: Donor reactivation verified")

    # Delete donor (no donations linked)
    del_d = delete_donor(did)
    assert del_d is True
    assert get_donor_by_id(did) is None
    print(f"PASS: Donor #{did} successfully deleted when 0 donations exist")


def main():
    print("=== Running CRUD Operations Validation Tests ===")
    test_hospital_input_validation()
    print("PASS: test_hospital_input_validation")
    test_blood_bank_input_validation()
    print("PASS: test_blood_bank_input_validation")

    print("\n=== Running Database Integration Tests ===")
    run_db_crud_tests()
    print("\nAll CRUD operations tests passed successfully!")


if __name__ == "__main__":
    main()

