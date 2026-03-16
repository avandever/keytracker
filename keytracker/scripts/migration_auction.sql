CREATE TABLE tracker_auction (
    id INT AUTO_INCREMENT PRIMARY KEY,
    creator_id INT NOT NULL,
    passphrase VARCHAR(30) NOT NULL UNIQUE,
    status ENUM('setup','deck_submission','auction','completed') NOT NULL DEFAULT 'setup',
    player_order JSON,
    active_deck_id INT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_id) REFERENCES tracker_user(id)
);
CREATE TABLE tracker_auction_participant (
    id INT AUTO_INCREMENT PRIMARY KEY,
    auction_id INT NOT NULL,
    user_id INT NOT NULL,
    joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (auction_id) REFERENCES tracker_auction(id),
    FOREIGN KEY (user_id) REFERENCES tracker_user(id),
    UNIQUE KEY uq_auction_participant (auction_id, user_id)
);
CREATE TABLE tracker_auction_deck (
    id INT AUTO_INCREMENT PRIMARY KEY,
    auction_id INT NOT NULL,
    brought_by_user_id INT NOT NULL,
    deck_id INT,
    assigned_to_user_id INT,
    chains_bid INT NOT NULL DEFAULT 0,
    FOREIGN KEY (auction_id) REFERENCES tracker_auction(id),
    FOREIGN KEY (brought_by_user_id) REFERENCES tracker_user(id),
    FOREIGN KEY (deck_id) REFERENCES tracker_deck(id),
    FOREIGN KEY (assigned_to_user_id) REFERENCES tracker_user(id)
);
ALTER TABLE tracker_auction
    ADD CONSTRAINT fk_auction_active_deck
    FOREIGN KEY (active_deck_id) REFERENCES tracker_auction_deck(id);
CREATE TABLE tracker_auction_bid (
    id INT AUTO_INCREMENT PRIMARY KEY,
    auction_deck_id INT NOT NULL,
    user_id INT NOT NULL,
    chains INT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (auction_deck_id) REFERENCES tracker_auction_deck(id),
    FOREIGN KEY (user_id) REFERENCES tracker_user(id),
    UNIQUE KEY uq_auction_bid (auction_deck_id, user_id)
);
