-- ============================================================================
-- BloodLink — SQL Operational & Analytical Reports
-- Mapped to DBMS Syllabus: DDL, DML, Joins, Aggregates, Grouping, Views,
-- Nested Queries, Three-Valued Logic, and Set Operations (UNION, EXCEPT, INTERSECT).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Report 1: View Query with Grouping & Aggregates
-- Concept: Views, Aggregate functions (COUNT), GROUP BY, ORDER BY
-- ----------------------------------------------------------------------------
SELECT
    bank_id,
    bank_name,
    component,
    blood_group,
    COUNT(*) AS available_units
FROM available_blood_inventory
GROUP BY
    bank_id,
    bank_name,
    component,
    blood_group
ORDER BY
    bank_name,
    component,
    blood_group;


-- ----------------------------------------------------------------------------
-- Report 2: Hospital Blood Demand
-- Concept: Filtering (WHERE), Multiple Aggregates (COUNT, SUM), GROUP BY
-- ----------------------------------------------------------------------------
SELECT
    component,
    recipient_group,
    COUNT(*) AS total_requests,
    SUM(quantity_requested) AS total_units_requested
FROM blood_request
WHERE status IN ('pending', 'partially_fulfilled')
GROUP BY
    component,
    recipient_group
ORDER BY
    total_units_requested DESC,
    component,
    recipient_group;


-- ----------------------------------------------------------------------------
-- Report 3: Expiry Tracking with Three-Valued Logic and CASE Expressions
-- Concept: Date arithmetic, CASE conditional logic, View querying
-- ----------------------------------------------------------------------------
SELECT
    unit_id,
    bank_name,
    component,
    blood_group,
    expiry_date,
    days_until_expiry,
    expiry_category,
    status
FROM blood_expiry_report
WHERE days_until_expiry <= 7
ORDER BY
    days_until_expiry ASC,
    bank_name;


-- ----------------------------------------------------------------------------
-- Report 4: Complex Multi-Table Join & Conditional Aggregation
-- Concept: INNER JOIN, LEFT JOIN, Aggregation with FILTER clause, GREATEST function
-- ----------------------------------------------------------------------------
SELECT
    br.request_id,
    h.hospital_name,
    br.component,
    br.recipient_group,
    br.quantity_requested,

    COUNT(a.allocation_id) FILTER (
        WHERE a.status = 'reserved'
    ) AS reserved_units,

    COUNT(a.allocation_id) FILTER (
        WHERE a.status = 'issued'
    ) AS issued_units,

    GREATEST(
        br.quantity_requested -
        COUNT(a.allocation_id) FILTER (
            WHERE a.status = 'issued'
        ),
        0
    ) AS units_not_yet_issued,

    br.status AS request_status

FROM blood_request AS br
JOIN hospital AS h
    ON h.hospital_id = br.hospital_id
LEFT JOIN allocation AS a
    ON a.request_id = br.request_id
GROUP BY
    br.request_id,
    h.hospital_name,
    br.component,
    br.recipient_group,
    br.quantity_requested,
    br.status
ORDER BY
    br.request_date DESC,
    br.request_id;


-- ----------------------------------------------------------------------------
-- Report 5: Set Operation (UNION)
-- Concept: Set Operations — Relational Union of blood banks and hospitals
-- ----------------------------------------------------------------------------
SELECT
    bank_name AS facility_name,
    address,
    phone,
    'Blood Bank' AS facility_type
FROM blood_bank
UNION
SELECT
    hospital_name AS facility_name,
    address,
    phone,
    'Hospital' AS facility_type
FROM hospital
ORDER BY
    facility_type,
    facility_name;


-- ----------------------------------------------------------------------------
-- Report 6: Set Operation (EXCEPT / Difference)
-- Concept: Relational Difference — Donors who have NOT made any donations yet
-- ----------------------------------------------------------------------------
SELECT
    d.donor_id,
    d.donor_name,
    d.phone,
    d.blood_group,
    d.location
FROM donor AS d
WHERE d.donor_id IN (
    SELECT donor_id FROM donor
    EXCEPT
    SELECT donor_id FROM donation
)
ORDER BY d.donor_id;


-- ----------------------------------------------------------------------------
-- Report 7: Nested Query with HAVING and Subquery in FROM
-- Concept: Nested subqueries, Derived tables, HAVING with Aggregate comparison
-- ----------------------------------------------------------------------------
SELECT
    bb.bank_name,
    COUNT(bu.unit_id) AS total_units_stored
FROM blood_bank AS bb
JOIN donation AS d
    ON d.bank_id = bb.bank_id
JOIN blood_unit AS bu
    ON bu.donation_id = d.donation_id
GROUP BY
    bb.bank_id,
    bb.bank_name
HAVING COUNT(bu.unit_id) >= (
    SELECT AVG(bank_count)
    FROM (
        SELECT COUNT(bu2.unit_id) AS bank_count
        FROM blood_bank AS bb2
        JOIN donation AS d2 ON d2.bank_id = bb2.bank_id
        JOIN blood_unit AS bu2 ON bu2.donation_id = d2.donation_id
        GROUP BY bb2.bank_id
    ) AS avg_subquery
)
ORDER BY total_units_stored DESC;
