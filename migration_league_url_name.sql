-- Migration: add url_name to tracker_league

ALTER TABLE tracker_league
    ADD COLUMN url_name VARCHAR(100) NULL,
    ADD UNIQUE INDEX ix_tracker_league_url_name (url_name);
