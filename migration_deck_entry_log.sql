CREATE TABLE team_deck_entry_log (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    team_id INT NOT NULL,
    week_id INT NOT NULL,
    target_user_id INT NOT NULL,
    changed_by_user_id INT NOT NULL,
    action VARCHAR(16) NOT NULL,
    deck_name VARCHAR(500),
    deck_kf_id VARCHAR(36),
    slot_number INT,
    created_at DATETIME NOT NULL,
    INDEX idx_tdel_team_id (team_id),
    CONSTRAINT fk_tdel_team FOREIGN KEY (team_id) REFERENCES tracker_team(id) ON DELETE CASCADE,
    CONSTRAINT fk_tdel_week FOREIGN KEY (week_id) REFERENCES tracker_league_week(id) ON DELETE CASCADE,
    CONSTRAINT fk_tdel_target FOREIGN KEY (target_user_id) REFERENCES tracker_user(id),
    CONSTRAINT fk_tdel_changer FOREIGN KEY (changed_by_user_id) REFERENCES tracker_user(id)
);
