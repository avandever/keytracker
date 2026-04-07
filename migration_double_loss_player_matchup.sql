-- Move is_double_loss from WeekMatchup to PlayerMatchup
ALTER TABLE tracker_week_matchup
    DROP COLUMN is_double_loss;

ALTER TABLE tracker_player_matchup
    ADD COLUMN is_double_loss TINYINT(1) NOT NULL DEFAULT 0;
