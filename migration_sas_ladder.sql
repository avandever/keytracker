-- SAS Ladder format migration
-- Run this before deploying the SAS Ladder feature

ALTER TABLE tracker_league_week ADD COLUMN sas_ladder_maxes TEXT NULL;
ALTER TABLE tracker_league_week ADD COLUMN sas_ladder_feature_rung INT NULL;

CREATE TABLE sas_ladder_assignment (
    id INT AUTO_INCREMENT PRIMARY KEY,
    week_id INT NOT NULL,
    user_id INT NOT NULL,
    team_id INT NOT NULL,
    rung_number INT NOT NULL,
    FOREIGN KEY (week_id) REFERENCES tracker_league_week(id),
    FOREIGN KEY (user_id) REFERENCES tracker_user(id),
    FOREIGN KEY (team_id) REFERENCES tracker_team(id),
    UNIQUE KEY uq_sla_week_user (week_id, user_id),
    UNIQUE KEY uq_sla_week_team_rung (week_id, team_id, rung_number)
);
