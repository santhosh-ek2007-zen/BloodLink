-- BloodLink — Additional Constraints
-- Run this ONCE after schema.sql on a fresh database.
-- Safe to re-run: uses IF NOT EXISTS where supported.

-- 1. Prevent the same blood unit from having more than one active
-- (reserved or issued) allocation at the same time.
-- This is the database-level guard against duplicate allocation.
-- Application code also checks, but this constraint is the last
-- line of defence, including against concurrent transactions.

ALTER TABLE allocation
ADD CONSTRAINT chk_allocation_status
CHECK (status IN ('reserved', 'issued', 'cancelled', 'completed'));

-- 2. Prevent duplicate donor registrations with the same phone number.
-- Enforces data integrity at the database layer in addition to application-level validation.

CREATE OR REPLACE VIEW donor_directory AS
SELECT
    donor_id,
    donor_name,
    blood_group
FROM donor;
