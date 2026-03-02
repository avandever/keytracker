-- Migration: Add Oubliette format support
-- Run this migration before deploying the Oubliette format.

ALTER TABLE tracker_player_matchup
    ADD COLUMN oubliette_p1_banned_house TEXT NULL,
    ADD COLUMN oubliette_p2_banned_house TEXT NULL;
