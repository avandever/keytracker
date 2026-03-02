-- Migration: add game_id FK to tracker_match_game
-- Allows a MatchGame to be linked to a full Game record created from an uploaded log.
ALTER TABLE tracker_match_game
    ADD COLUMN game_id INT NULL,
    ADD CONSTRAINT fk_match_game_game
        FOREIGN KEY (game_id) REFERENCES tracker_game(id);
