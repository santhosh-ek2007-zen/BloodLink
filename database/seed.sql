INSERT INTO donor(donor_name, phone, blood_group, location)
VALUES
    ('Arun Kumar', '9000000001', 'O+', 'Chennai'),
    ('Priya Sharma', '9000000002', 'A+', 'Tambaram'),
    ('Karthik Raj', '9000000003', 'B+', 'Chengalpattu'),
    ('Divya Nair', '9000000004', 'AB+', 'Chennai'),
    ('Rahul Verma', '9000000005', 'O-', 'Pallavaram'),
    ('Meena Krishnan', '9000000006', 'A-', 'Chromepet'),
    ('Sanjay Kumar', '9000000007', 'B-', 'Chennai'),
    ('Ananya Rao', '9000000008', 'AB-', 'Tambaram');

INSERT INTO blood_bank(bank_name, address, phone)
VALUES
    ('Chennai Central Blood Bank', 'Anna Salai, Chennai', '9100000001'),
    ('Tambaram Blood Centre', 'West Tambaram, Chennai', '9100000002'),
    ('Government Blood Bank', 'Chromepet, Chennai', '9100000003'),
    ('City Life Blood Bank', 'Velachery, Chennai', '9100000004');

INSERT INTO hospital(hospital_name, address, phone)
VALUES
    ('Rajiv Gandhi Government General Hospital', 'Park Town, Chennai', '9200000001'),
    ('Government Hospital Tambaram', 'Tambaram West, Chennai', '9200000002'),
    ('Chromepet Multispeciality Hospital', 'Chromepet, Chennai', '9200000003'),
    ('City Care Hospital', 'Velachery, Chennai', '9200000004');

INSERT INTO blood_compatibility (component, recipient_group, donor_group)
VALUES
    ('red_cells', 'A+', 'A+'),
    ('red_cells', 'A+', 'A-'),
    ('red_cells', 'A+', 'O+'),
    ('red_cells', 'A+', 'O-'),
    ('red_cells', 'A-', 'A-'),
    ('red_cells', 'A-', 'O-'),
    ('red_cells', 'B+', 'B+'),
    ('red_cells', 'B+', 'B-'),
    ('red_cells', 'B+', 'O+'),
    ('red_cells', 'B+', 'O-'),
    ('red_cells', 'B-', 'B-'),
    ('red_cells', 'B-', 'O-'),
    ('red_cells', 'AB+', 'A+'),
    ('red_cells', 'AB+', 'A-'),
    ('red_cells', 'AB+', 'B+'),
    ('red_cells', 'AB+', 'B-'),
    ('red_cells', 'AB+', 'AB+'),
    ('red_cells', 'AB+', 'AB-'),
    ('red_cells', 'AB+', 'O+'),
    ('red_cells', 'AB+', 'O-'),
    ('red_cells', 'AB-', 'A-'),
    ('red_cells', 'AB-', 'B-'),
    ('red_cells', 'AB-', 'AB-'),
    ('red_cells', 'AB-', 'O-'),
    ('red_cells', 'O+', 'O+'),
    ('red_cells', 'O+', 'O-'),
    ('red_cells', 'O-', 'O-');

INSERT INTO donation (donor_id, bank_id, donation_date, quantity_ml)
VALUES
    (1, 1, CURRENT_DATE - 30, 450),
    (2, 2, CURRENT_DATE - 25, 450),
    (3, 3, CURRENT_DATE - 20, 450),
    (4, 4, CURRENT_DATE - 15, 450),
    (5, 1, CURRENT_DATE - 10, 450),
    (6, 2, CURRENT_DATE - 8, 450),
    (7, 3, CURRENT_DATE - 5, 450),
    (8, 4, CURRENT_DATE - 2, 450);

INSERT INTO blood_unit
    (donation_id, component, blood_group, collection_date,
     expiry_date, status)
VALUES
(1, 'red_cells', 'O+',  CURRENT_DATE - 30, CURRENT_DATE + 12, 'available'),
(2, 'red_cells', 'A+',  CURRENT_DATE - 25, CURRENT_DATE + 17, 'available'),
(3, 'red_cells', 'B+',  CURRENT_DATE - 20, CURRENT_DATE + 22, 'under_testing'),
(4, 'red_cells', 'AB+', CURRENT_DATE - 15, CURRENT_DATE + 27, 'rejected'),
(5, 'red_cells', 'O-',  CURRENT_DATE - 10, CURRENT_DATE + 32, 'available'),
(6, 'platelets', 'A-', CURRENT_DATE - 8,  CURRENT_DATE - 3, 'expired'),
(7, 'plasma',    'B-', CURRENT_DATE - 5,  CURRENT_DATE + 360, 'available'),
(8, 'red_cells', 'AB-', CURRENT_DATE - 2, CURRENT_DATE + 40, 'under_testing');

INSERT INTO screening (unit_id, result, remarks)
VALUES
(1, 'approved', 'Sample screening approved'),
(2, 'approved', 'Sample screening approved'),
(3, 'pending',  'Screening pending'),
(4, 'rejected', 'Sample screening rejected'),
(5, 'approved', 'Sample screening approved'),
(6, 'approved', 'Sample screening approved'),
(7, 'approved', 'Sample screening approved'),
(8, 'pending',  'Screening pending');

INSERT INTO blood_request
    (hospital_id, component, recipient_group, quantity_requested, urgency, request_date, status)
VALUES
    (1, 'red_cells', 'O+', 2, 'emergency', CURRENT_TIMESTAMP, 'pending'),
    (2, 'red_cells', 'A+', 3, 'urgent', CURRENT_TIMESTAMP, 'pending'),
    (3, 'platelets', 'A-', 2, 'normal', CURRENT_TIMESTAMP, 'pending'),
    (4, 'plasma', 'B-', 2, 'urgent', CURRENT_TIMESTAMP, 'pending');

INSERT INTO allocation (request_id, unit_id, status)
SELECT
    br.request_id,
    bu.unit_id,
    'reserved'
FROM blood_request AS br
JOIN blood_unit AS bu
    ON bu.component = br.component
   AND bu.blood_group = br.recipient_group
JOIN screening AS s
    ON s.unit_id = bu.unit_id
WHERE br.hospital_id = 1
  AND br.status = 'pending'
  AND bu.status = 'available'
  AND bu.expiry_date >= CURRENT_DATE
  AND s.result = 'approved'
LIMIT 1;

INSERT INTO status_history
    (unit_id, old_status, new_status, actor, remarks)
SELECT
    unit_id,
    NULL,
    status,
    'system',
    'Initial sample status'
FROM blood_unit;
