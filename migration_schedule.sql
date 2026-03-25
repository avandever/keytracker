CREATE TABLE match_schedule_proposal (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    player_matchup_id INT NOT NULL,
    proposed_by_user_id INT NOT NULL,
    proposed_time DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_msp_matchup FOREIGN KEY (player_matchup_id)
        REFERENCES tracker_player_matchup(id) ON DELETE CASCADE,
    CONSTRAINT fk_msp_user FOREIGN KEY (proposed_by_user_id)
        REFERENCES tracker_user(id),
    INDEX idx_msp_matchup (player_matchup_id)
);

CREATE TABLE match_schedule_confirmation (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    player_matchup_id INT NOT NULL UNIQUE,
    confirmed_time DATETIME NOT NULL,
    confirmed_by_user_id INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_msc_matchup FOREIGN KEY (player_matchup_id)
        REFERENCES tracker_player_matchup(id) ON DELETE CASCADE,
    CONSTRAINT fk_msc_user FOREIGN KEY (confirmed_by_user_id)
        REFERENCES tracker_user(id)
);
