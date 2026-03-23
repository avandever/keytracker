CREATE TABLE tracker_feature_volunteer (
    id INT AUTO_INCREMENT PRIMARY KEY,
    week_id INT NOT NULL,
    team_id INT NOT NULL,
    user_id INT NOT NULL,
    CONSTRAINT fk_fv_week FOREIGN KEY (week_id) REFERENCES tracker_league_week(id),
    CONSTRAINT fk_fv_team FOREIGN KEY (team_id) REFERENCES tracker_team(id),
    CONSTRAINT fk_fv_user FOREIGN KEY (user_id) REFERENCES tracker_user(id),
    CONSTRAINT uq_feature_volunteer UNIQUE (week_id, team_id, user_id)
);

CREATE TABLE tracker_deck_suggestion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    week_id INT NOT NULL,
    team_id INT NOT NULL,
    suggesting_user_id INT NOT NULL,
    deck_id INT NOT NULL,
    CONSTRAINT fk_ds_week FOREIGN KEY (week_id) REFERENCES tracker_league_week(id),
    CONSTRAINT fk_ds_team FOREIGN KEY (team_id) REFERENCES tracker_team(id),
    CONSTRAINT fk_ds_user FOREIGN KEY (suggesting_user_id) REFERENCES tracker_user(id),
    CONSTRAINT fk_ds_deck FOREIGN KEY (deck_id) REFERENCES tracker_deck(id),
    CONSTRAINT uq_deck_suggestion UNIQUE (week_id, team_id, deck_id)
);
