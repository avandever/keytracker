-- Migration: Add Adaptive Short format support
-- Run after migration_oubliette.sql

CREATE TABLE adaptive_short_choice (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    player_matchup_id INT NOT NULL,
    choosing_user_id INT NOT NULL,
    chosen_deck_selection_id INT NOT NULL,
    CONSTRAINT uq_adaptive_short_choice UNIQUE (player_matchup_id, choosing_user_id),
    CONSTRAINT fk_asc_matchup FOREIGN KEY (player_matchup_id) REFERENCES tracker_player_matchup(id),
    CONSTRAINT fk_asc_user FOREIGN KEY (choosing_user_id) REFERENCES tracker_user(id),
    CONSTRAINT fk_asc_deck_sel FOREIGN KEY (chosen_deck_selection_id) REFERENCES tracker_player_deck_selection(id)
);

ALTER TABLE tracker_player_matchup
    ADD COLUMN adaptive_short_bid_chains INT NULL,
    ADD COLUMN adaptive_short_bidder_id INT NULL,
    ADD COLUMN adaptive_short_bidding_complete BOOLEAN NOT NULL DEFAULT FALSE,
    ADD CONSTRAINT fk_pm_adaptive_short_bidder FOREIGN KEY (adaptive_short_bidder_id) REFERENCES tracker_user(id);
