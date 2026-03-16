-- Migration: Add Tertiate format support
-- TertiateHousePurge table for secret simultaneous house-purge choices
CREATE TABLE tertiate_house_purge (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    player_matchup_id INT NOT NULL,
    choosing_user_id INT NOT NULL,
    purged_house TEXT NOT NULL,
    CONSTRAINT fk_thp_matchup FOREIGN KEY (player_matchup_id) REFERENCES tracker_player_matchup(id) ON DELETE CASCADE,
    CONSTRAINT fk_thp_user FOREIGN KEY (choosing_user_id) REFERENCES tracker_user(id),
    CONSTRAINT uq_tertiate_house_purge UNIQUE (player_matchup_id, choosing_user_id)
);
