-- Add is_double_loss flag to WeekMatchup
ALTER TABLE tracker_week_matchup
    ADD COLUMN is_double_loss TINYINT(1) NOT NULL DEFAULT 0;
