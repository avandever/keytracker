-- Migration: DoK collection sync + Alliance deck schema

CREATE TABLE IF NOT EXISTS tracker_alliance_deck (
    id INT AUTO_INCREMENT PRIMARY KEY,
    kf_id VARCHAR(36) UNIQUE NOT NULL,
    name VARCHAR(256),
    sas_rating INT,
    aerc_score INT,
    synergy_rating INT,
    antisynergy_rating INT,
    valid_alliance BOOLEAN,
    pods JSON,
    last_synced DATETIME
);

CREATE TABLE IF NOT EXISTS user_deck_collection (
    user_id INT NOT NULL REFERENCES tracker_user(id),
    deck_id INT NOT NULL REFERENCES tracker_deck(id),
    dok_owned BOOLEAN NOT NULL DEFAULT FALSE,
    dok_wishlist BOOLEAN NOT NULL DEFAULT FALSE,
    dok_funny BOOLEAN NOT NULL DEFAULT FALSE,
    dok_notes TEXT,
    last_synced_at DATETIME,
    PRIMARY KEY (user_id, deck_id)
);

CREATE TABLE IF NOT EXISTS user_alliance_collection (
    user_id INT NOT NULL REFERENCES tracker_user(id),
    alliance_deck_id INT NOT NULL REFERENCES tracker_alliance_deck(id),
    dok_owned BOOLEAN NOT NULL DEFAULT FALSE,
    dok_wishlist BOOLEAN NOT NULL DEFAULT FALSE,
    dok_funny BOOLEAN NOT NULL DEFAULT FALSE,
    dok_notes TEXT,
    last_synced_at DATETIME,
    PRIMARY KEY (user_id, alliance_deck_id)
);
