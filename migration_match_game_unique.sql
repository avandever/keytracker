-- Add unique constraint on (player_matchup_id, game_number) to tracker_match_game.
-- Prevents duplicate game numbers from being inserted concurrently (race condition guard).
-- Safe to run if constraint already exists (IF NOT EXISTS is not supported for constraints,
-- so check first or ignore the duplicate key error).

ALTER TABLE tracker_match_game
    ADD CONSTRAINT uq_match_game UNIQUE (player_matchup_id, game_number);
