-- Migration: Add standalone match support
-- Run this against your database before deploying the standalone match feature.

-- 1. Create the standalone_match table
CREATE TABLE IF NOT EXISTS standalone_match (
    id INT AUTO_INCREMENT PRIMARY KEY,
    uuid VARCHAR(36) UNIQUE NOT NULL,
    creator_id INT NOT NULL REFERENCES tracker_user(id),
    opponent_id INT REFERENCES tracker_user(id),
    format_type ENUM('archon_standard','triad','sealed_archon','sealed_alliance','thief') NOT NULL,
    status ENUM('setup','deck_selection','published','completed') NOT NULL DEFAULT 'setup',
    best_of_n INT NOT NULL DEFAULT 3,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    max_sas INT,
    combined_max_sas INT,
    set_diversity BOOLEAN NOT NULL DEFAULT FALSE,
    house_diversity BOOLEAN NOT NULL DEFAULT FALSE,
    decks_per_player INT NOT NULL DEFAULT 4,
    sealed_pools_generated BOOLEAN NOT NULL DEFAULT FALSE,
    allowed_sets JSON,
    created_at DATETIME DEFAULT NOW()
);

-- 2. Make week_matchup_id nullable on tracker_player_matchup
ALTER TABLE tracker_player_matchup MODIFY week_matchup_id INT NULL;

-- 3. Add standalone_match_id to tracker_player_matchup
ALTER TABLE tracker_player_matchup
    ADD COLUMN standalone_match_id INT NULL REFERENCES standalone_match(id);

-- 4. Make week_id nullable on tracker_player_deck_selection
ALTER TABLE tracker_player_deck_selection MODIFY week_id INT NULL;

-- 5. Add standalone_match_id to tracker_player_deck_selection
ALTER TABLE tracker_player_deck_selection
    ADD COLUMN standalone_match_id INT NULL REFERENCES standalone_match(id);

-- Add unique constraint for standalone deck selections
ALTER TABLE tracker_player_deck_selection
    ADD CONSTRAINT uq_deck_selection_standalone
    UNIQUE (standalone_match_id, user_id, slot_number);

-- 6. Make week_id nullable on tracker_alliance_pod_selection
ALTER TABLE tracker_alliance_pod_selection MODIFY week_id INT NULL;

-- 7. Add standalone_match_id to tracker_alliance_pod_selection
ALTER TABLE tracker_alliance_pod_selection
    ADD COLUMN standalone_match_id INT NULL REFERENCES standalone_match(id);

-- 8. Make week_id nullable on tracker_sealed_pool_deck
ALTER TABLE tracker_sealed_pool_deck MODIFY week_id INT NULL;

-- 9. Add standalone_match_id to tracker_sealed_pool_deck
ALTER TABLE tracker_sealed_pool_deck
    ADD COLUMN standalone_match_id INT NULL REFERENCES standalone_match(id);

-- 10. Ensure the guest user exists
INSERT IGNORE INTO tracker_user (email, name)
VALUES ('nobody@example.com', 'Guest Player');
