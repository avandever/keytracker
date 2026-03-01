-- Migration: Add Triad Short format support
-- Run this migration before deploying the Triad Short format.

CREATE TABLE triad_short_pick (
    id INT NOT NULL AUTO_INCREMENT,
    player_matchup_id INT NOT NULL,
    picking_user_id INT NOT NULL,
    picked_deck_selection_id INT NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_triad_short_pick (player_matchup_id, picking_user_id),
    CONSTRAINT fk_tsp_matchup FOREIGN KEY (player_matchup_id) REFERENCES tracker_player_matchup (id) ON DELETE CASCADE,
    CONSTRAINT fk_tsp_user FOREIGN KEY (picking_user_id) REFERENCES tracker_user (id),
    CONSTRAINT fk_tsp_deck_sel FOREIGN KEY (picked_deck_selection_id) REFERENCES tracker_player_deck_selection (id)
);
