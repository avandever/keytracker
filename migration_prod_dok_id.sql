-- Migration: add prod_dok_id to tracker_dok_deck
-- Stores DoK's internal deck ID as returned by the production DoK instance.
-- Only populated when data is fetched from decksofkeyforge.com (not a local instance).

ALTER TABLE tracker_dok_deck ADD COLUMN prod_dok_id BIGINT NULL;
