-- Report 1: Available Blood Inventory by Bank, Component, and Blood Group

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

-- Report 2: Hospital Blood Demand by Component and Blood Group

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

-- Report 3: Expired and Soon-to-Expire Blood Units

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

-- Report 4: Hospital Request Fulfillment Status

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