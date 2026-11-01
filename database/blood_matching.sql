SELECT
    br.request_id,
    h.hospital_name,
    br.component AS requested_component,
    br.recipient_group,
    br.quantity_requested,
    br.urgency,
    bu.unit_id,
    bu.blood_group AS donor_blood_group,
    bu.component,
    bb.bank_name,
    bu.expiry_date,
    bu.expiry_date - CURRENT_DATE AS days_until_expiry
FROM blood_request AS br
JOIN hospital AS h
    ON h.hospital_id = br.hospital_id
JOIN blood_compatibility AS bc
    ON bc.component = br.component
   AND bc.recipient_group = br.recipient_group
JOIN blood_unit AS bu
    ON bu.blood_group = bc.donor_group
   AND bu.component = br.component
JOIN donation AS d
    ON d.donation_id = bu.donation_id
JOIN blood_bank AS bb
    ON bb.bank_id = d.bank_id
WHERE br.request_id = 1
  AND br.component = 'red_cells'
  AND br.status IN ('pending', 'partially_fulfilled')
  AND bu.status = 'available'
  AND bu.expiry_date >= CURRENT_DATE
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
  AND NOT EXISTS (
      SELECT 1
      FROM allocation AS a
      WHERE a.unit_id = bu.unit_id
        AND a.status IN ('reserved', 'issued')
  )
ORDER BY
    bu.expiry_date ASC,
    bu.unit_id ASC;