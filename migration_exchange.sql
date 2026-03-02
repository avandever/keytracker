-- Migration: Add Exchange format support
-- Run after migration_adaptive_short.sql

CREATE TABLE exchange_borrow (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    player_matchup_id INT NOT NULL,
    borrowing_user_id INT NOT NULL,
    borrowed_deck_selection_id INT NOT NULL,
    CONSTRAINT uq_exchange_borrow UNIQUE (player_matchup_id, borrowing_user_id),
    CONSTRAINT fk_eb_matchup FOREIGN KEY (player_matchup_id) REFERENCES tracker_player_matchup(id),
    CONSTRAINT fk_eb_user FOREIGN KEY (borrowing_user_id) REFERENCES tracker_user(id),
    CONSTRAINT fk_eb_deck_sel FOREIGN KEY (borrowed_deck_selection_id) REFERENCES tracker_player_deck_selection(id)
);
