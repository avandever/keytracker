ALTER TABLE tracker_league_week ADD COLUMN custom_description TEXT;
ALTER TABLE tracker_league_week ADD COLUMN hide_standard_description BOOLEAN NOT NULL DEFAULT FALSE;
