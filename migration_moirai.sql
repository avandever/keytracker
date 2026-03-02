-- Migration: Moirai format
-- Run this before deploying the Moirai format.

CREATE TABLE moirai_assignment (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    player_matchup_id INT NOT NULL,
    assigning_user_id INT NOT NULL,
    game_number TINYINT NOT NULL,
    assigned_deck_selection_id INT NOT NULL,
    CONSTRAINT uq_moirai_assignment UNIQUE (player_matchup_id, assigning_user_id, game_number),
    CONSTRAINT fk_moirai_matchup FOREIGN KEY (player_matchup_id) REFERENCES tracker_player_matchup(id),
    CONSTRAINT fk_moirai_user FOREIGN KEY (assigning_user_id) REFERENCES tracker_user(id),
    CONSTRAINT fk_moirai_deck_sel FOREIGN KEY (assigned_deck_selection_id) REFERENCES tracker_player_deck_selection(id)
);
