-- Captain result confirmation: adds two columns to tracker_player_matchup.
-- result_confirmed_at: when the captain confirmed the result (NULL = unconfirmed)
-- result_confirmed_by_id: which user (captain/admin) confirmed it

ALTER TABLE tracker_player_matchup
    ADD COLUMN result_confirmed_at DATETIME NULL,
    ADD COLUMN result_confirmed_by_id INT NULL,
    ADD CONSTRAINT fk_pm_confirmed_by
        FOREIGN KEY (result_confirmed_by_id) REFERENCES tracker_user(id);
