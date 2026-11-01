CREATE OR REPLACE VIEW available_blood_inventory AS
SELECT
    bu.unit_id,
    d.bank_id,
    bb.bank_name,
    bb.address AS bank_address,
    bb.phone AS bank_phone,
    bu.donation_id,
    bu.component,
    bu.blood_group,
    bu.collection_date,
    bu.expiry_date,
    bu.status
FROM blood_unit AS bu
JOIN donation AS d
    ON d.donation_id = bu.donation_id
JOIN blood_bank AS bb
    ON bb.bank_id = d.bank_id
WHERE bu.status = 'available'
  AND bu.expiry_date >= CURRENT_DATE
  -- The latest screening result must be approved.
  AND EXISTS (
      SELECT 1
      FROM screening AS s
      WHERE s.unit_id = bu.unit_id
        AND s.result = 'approved'
        AND NOT EXISTS (
            SELECT 1
            FROM screening AS newer
            WHERE newer.unit_id = s.unit_id
              AND (
                  newer.screening_date > s.screening_date
                  OR (
                      newer.screening_date = s.screening_date
                      AND newer.screening_id > s.screening_id
                  )
              )
        )
  )
  -- Exclude units with active reservations or completed issues.
  AND NOT EXISTS (
      SELECT 1
      FROM allocation AS a
      WHERE a.unit_id = bu.unit_id
        AND a.status IN ('reserved', 'issued')
  );

CREATE OR REPLACE VIEW blood_request_summary AS
SELECT
    br.request_id,
    h.hospital_id,
    h.hospital_name,
    h.address AS hospital_address,
    br.component,
    br.recipient_group,
    br.quantity_requested,
    br.urgency,
    br.request_date,
    br.status
FROM blood_request AS br
JOIN hospital AS h
    ON h.hospital_id = br.hospital_id;

CREATE OR REPLACE VIEW blood_expiry_report AS
SELECT
    bu.unit_id,
    bb.bank_id,
    bb.bank_name,
    bu.component,
    bu.blood_group,
    bu.collection_date,
    bu.expiry_date,
    bu.status,
    CASE
        WHEN bu.expiry_date < CURRENT_DATE
            THEN 'Expired'
        WHEN bu.expiry_date <= CURRENT_DATE + 3
            THEN 'Expires within 3 days'
        WHEN bu.expiry_date <= CURRENT_DATE + 7
            THEN 'Expires within 7 days'
        ELSE 'Not expiring soon'
    END AS expiry_category,
    bu.expiry_date - CURRENT_DATE AS days_until_expiry
FROM blood_unit AS bu
JOIN donation AS d
    ON d.donation_id = bu.donation_id
JOIN blood_bank AS bb
    ON bb.bank_id = d.bank_id;

CREATE OR REPLACE VIEW allocation_summary AS
SELECT
    a.allocation_id,
    a.request_id,
    br.hospital_id,
    h.hospital_name,
    a.unit_id,
    bu.component,
    bu.blood_group,
    d.bank_id,
    bb.bank_name,
    a.status AS allocation_status,
    br.status AS request_status,
    bu.status AS unit_status,
    a.allocated_at,
    a.issued_at,
    a.cancelled_at
FROM allocation AS a
JOIN blood_request AS br
    ON br.request_id = a.request_id
JOIN hospital AS h
    ON h.hospital_id = br.hospital_id
JOIN blood_unit AS bu
    ON bu.unit_id = a.unit_id
JOIN donation AS d
    ON d.donation_id = bu.donation_id
JOIN blood_bank AS bb
    ON bb.bank_id = d.bank_id;