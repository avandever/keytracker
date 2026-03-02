-- Migration: Nordic Hexad format
-- Run this before deploying the Nordic Hexad format.

CREATE TABLE nordic_hexad_action (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    player_matchup_id INT NOT NULL,
    player_id INT NOT NULL,
    phase TINYINT NOT NULL,
    target_deck_selection_id INT NOT NULL,
    CONSTRAINT uq_nordic_hexad_action UNIQUE (player_matchup_id, player_id, phase),
    CONSTRAINT fk_nordic_action_matchup FOREIGN KEY (player_matchup_id) REFERENCES tracker_player_matchup(id),
    CONSTRAINT fk_nordic_action_player FOREIGN KEY (player_id) REFERENCES tracker_user(id),
    CONSTRAINT fk_nordic_action_deck_sel FOREIGN KEY (target_deck_selection_id) REFERENCES tracker_player_deck_selection(id)
);

ALTER TABLE tracker_player_matchup
    ADD COLUMN nordic_hexad_phase TINYINT NULL;
