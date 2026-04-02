-- Tertiate: per-game house purge choices
-- Previously one purge per player per match; now one per player per game_number.

ALTER TABLE tertiate_house_purge
    ADD COLUMN game_number INT NOT NULL DEFAULT 1;

-- MySQL uses the unique key as the covering index for the FK on player_matchup_id,
-- so we must add an explicit index before we can drop and recreate the unique key.
ALTER TABLE tertiate_house_purge ADD INDEX idx_thp_matchup (player_matchup_id);

-- Drop old unique constraint (player_matchup_id, choosing_user_id)
-- and replace with (player_matchup_id, choosing_user_id, game_number).
ALTER TABLE tertiate_house_purge DROP INDEX uq_tertiate_house_purge;
ALTER TABLE tertiate_house_purge
    ADD CONSTRAINT uq_tertiate_house_purge
    UNIQUE (player_matchup_id, choosing_user_id, game_number);
