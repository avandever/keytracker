-- Migration: per-admin impersonation toggle + mailing address fields

ALTER TABLE tracker_user
    ADD COLUMN show_test_user_picker BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN mailing_address_line1 VARCHAR(200) NULL,
    ADD COLUMN mailing_address_line2 VARCHAR(200) NULL,
    ADD COLUMN mailing_city VARCHAR(100) NULL,
    ADD COLUMN mailing_state VARCHAR(100) NULL,
    ADD COLUMN mailing_postal_code VARCHAR(20) NULL,
    ADD COLUMN mailing_country VARCHAR(100) NULL;
