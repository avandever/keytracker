-- Migration: Add sas_floor constraint to LeagueWeek and StandaloneMatch
ALTER TABLE tracker_league_week ADD COLUMN sas_floor INT NULL AFTER max_sas;
ALTER TABLE standalone_match ADD COLUMN sas_floor INT NULL AFTER max_sas;
