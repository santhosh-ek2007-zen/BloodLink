-- BloodLink — Additional Database Integrity Constraints
-- Run this script after schema.sql.
-- Uses standard SQL relational constraints: UNIQUE and CHECK constraints.
-- Fully compatible with standard college DBMS coursework.

-- 1. Ensure donor table has the is_active column for logical deactivation/reactivation
ALTER TABLE donor ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- 2. Enforce uniqueness of donor phone numbers using a standard UNIQUE constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_donor_phone'
    ) THEN
        ALTER TABLE donor ADD CONSTRAINT uq_donor_phone UNIQUE (phone);
    END IF;
END $$;

-- 3. Enforce valid donation volume range (standard collection between 50ml and 600ml)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_donation_volume_range'
    ) THEN
        ALTER TABLE donation ADD CONSTRAINT chk_donation_volume_range CHECK (quantity_ml BETWEEN 50 AND 600);
    END IF;
END $$;

-- 4. Enforce valid blood request quantity range (1 to 100 units per request)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_request_qty_range'
    ) THEN
        ALTER TABLE blood_request ADD CONSTRAINT chk_request_qty_range CHECK (quantity_requested BETWEEN 1 AND 100);
    END IF;
END $$;

-- 5. Enforce exact 10-digit phone number length for donor records
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_donor_phone_min_len'
    ) THEN
        ALTER TABLE donor DROP CONSTRAINT chk_donor_phone_min_len;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_donor_phone_len'
    ) THEN
        ALTER TABLE donor ADD CONSTRAINT chk_donor_phone_len CHECK (LENGTH(phone) = 10);
    END IF;
END $$;

-- 6. Enforce exact 10-digit phone number length for blood bank records
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_blood_bank_phone_len'
    ) THEN
        ALTER TABLE blood_bank ADD CONSTRAINT chk_blood_bank_phone_len CHECK (LENGTH(phone) = 10);
    END IF;
END $$;

-- 7. Enforce exact 10-digit phone number length for hospital records
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_hospital_phone_len'
    ) THEN
        ALTER TABLE hospital ADD CONSTRAINT chk_hospital_phone_len CHECK (LENGTH(phone) = 10);
    END IF;
END $$;

-- 8. Enforce concurrency guard against duplicate active allocations
-- Prevents the same blood unit from having multiple active ('reserved' or 'issued') allocations.
CREATE UNIQUE INDEX IF NOT EXISTS uq_allocation_active_unit
ON allocation (unit_id)
WHERE status IN ('reserved', 'issued');
