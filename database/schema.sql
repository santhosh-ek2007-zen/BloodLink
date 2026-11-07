
CREATE TABLE donor (
    donor_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    donor_name VARCHAR(50) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    blood_group VARCHAR(3) NOT NULL
        CHECK (blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
    location VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE blood_bank (
    bank_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bank_name VARCHAR(50) NOT NULL,
    address VARCHAR(200) NOT NULL,
    phone VARCHAR(20) NOT NULL
);

CREATE TABLE hospital (
    hospital_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    hospital_name VARCHAR(50) NOT NULL,
    address VARCHAR(200) NOT NULL,
    phone VARCHAR(20) NOT NULL
);

CREATE TABLE blood_compatibility (
    component VARCHAR(20) NOT NULL
        CHECK (component IN ('whole_blood', 'red_cells', 'plasma', 'platelets')),
    recipient_group VARCHAR(3) NOT NULL
        CHECK (recipient_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
    donor_group VARCHAR(3) NOT NULL
        CHECK (donor_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
    PRIMARY KEY (component, recipient_group, donor_group)
);

CREATE TABLE donation (
    donation_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    donor_id INT NOT NULL,
    bank_id INT NOT NULL,
    donation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    quantity_ml INT NOT NULL CHECK (quantity_ml > 0),

    CONSTRAINT fk_donation_donor
        FOREIGN KEY (donor_id) REFERENCES donor(donor_id),

    CONSTRAINT fk_donation_bank
        FOREIGN KEY (bank_id) REFERENCES blood_bank(bank_id)
);

CREATE TABLE blood_unit (
    unit_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    donation_id INT NOT NULL,
    component VARCHAR(20) NOT NULL
        CHECK (component IN ('whole_blood', 'red_cells', 'plasma', 'platelets')),
    blood_group VARCHAR(3) NOT NULL
        CHECK (blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
    collection_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expiry_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'under_testing'
        CHECK (status IN (
            'under_testing',
            'available',
            'reserved',
            'issued',
            'rejected',
            'discarded',
            'expired'
        )),

    CONSTRAINT fk_blood_unit_donation
        FOREIGN KEY (donation_id) REFERENCES donation(donation_id),

    CONSTRAINT chk_blood_unit_dates
        CHECK (expiry_date > collection_date)
);

CREATE TABLE screening (
    screening_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    unit_id INT NOT NULL,
    screening_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result VARCHAR(20) NOT NULL
        CHECK (result IN ('pending', 'approved', 'rejected')),
    remarks TEXT,

    CONSTRAINT fk_screening_unit
        FOREIGN KEY (unit_id) REFERENCES blood_unit(unit_id)
);

CREATE TABLE blood_request (
    request_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    hospital_id INT NOT NULL,
    component VARCHAR(20) NOT NULL
        CHECK (component IN ('whole_blood', 'red_cells', 'plasma', 'platelets')),
    recipient_group VARCHAR(3) NOT NULL
        CHECK (recipient_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
    quantity_requested INT NOT NULL CHECK (quantity_requested > 0),
    urgency VARCHAR(20) NOT NULL DEFAULT 'normal'
        CHECK (urgency IN ('normal', 'urgent', 'emergency')),
    request_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending',
            'partially_fulfilled',
            'fulfilled',
            'cancelled'
        )),

    CONSTRAINT fk_blood_request_hospital
        FOREIGN KEY (hospital_id) REFERENCES hospital(hospital_id)
);

CREATE TABLE allocation (
    allocation_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id INT NOT NULL,
    unit_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'reserved'
        CHECK (status IN ('reserved', 'issued', 'cancelled')),
    allocated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    issued_at TIMESTAMP,
    cancelled_at TIMESTAMP,

    CONSTRAINT fk_allocation_request
        FOREIGN KEY (request_id) REFERENCES blood_request(request_id),

    CONSTRAINT fk_allocation_unit
        FOREIGN KEY (unit_id) REFERENCES blood_unit(unit_id),

    CONSTRAINT chk_allocation_timestamps
        CHECK (
            (status <> 'issued' OR issued_at IS NOT NULL)
            AND
            (status <> 'cancelled' OR cancelled_at IS NOT NULL)
        )
);

CREATE TABLE status_history (
    history_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    unit_id INT NOT NULL,
    old_status VARCHAR(20),
    new_status VARCHAR(20) NOT NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actor VARCHAR(100),
    remarks TEXT,

    CONSTRAINT fk_status_history_unit
        FOREIGN KEY (unit_id) REFERENCES blood_unit(unit_id),

    CONSTRAINT chk_old_status
        CHECK (
            old_status IS NULL
            OR old_status IN (
                'under_testing', 'available', 'reserved', 'issued',
                'rejected', 'discarded', 'expired'
            )
        ),

    CONSTRAINT chk_new_status
        CHECK (
            new_status IN (
                'under_testing', 'available', 'reserved', 'issued',
                'rejected', 'discarded', 'expired'
            )
        )
);
