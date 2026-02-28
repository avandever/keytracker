-- Migration: Add Alliance format support
-- Run this against your database before deploying the Alliance format feature.

-- 1. Create the alliance_restricted_list_version table
CREATE TABLE IF NOT EXISTS alliance_restricted_list_version (
    id INT AUTO_INCREMENT PRIMARY KEY,
    version FLOAT NOT NULL UNIQUE
);

-- 2. Create the alliance_restricted_entry table
CREATE TABLE IF NOT EXISTS alliance_restricted_entry (
    id INT AUTO_INCREMENT PRIMARY KEY,
    list_version_id INT NOT NULL REFERENCES alliance_restricted_list_version(id),
    platonic_card_id INT NOT NULL REFERENCES tracker_platonic_card(id),
    max_copies_per_alliance INT NULL
);

-- 3. Add alliance_restricted_list_version_id to tracker_league_week
ALTER TABLE tracker_league_week
    ADD COLUMN alliance_restricted_list_version_id INT NULL REFERENCES alliance_restricted_list_version(id);

-- 4. Add alliance_restricted_list_version_id to standalone_match
ALTER TABLE standalone_match
    ADD COLUMN alliance_restricted_list_version_id INT NULL REFERENCES alliance_restricted_list_version(id);

-- 5. Extend standalone_match format_type ENUM to include 'alliance'
ALTER TABLE standalone_match
    MODIFY format_type ENUM('archon_standard','triad','sealed_archon','sealed_alliance','thief','adaptive','alliance') NOT NULL;
