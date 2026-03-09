CREATE TABLE extended_game_data (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    crucible_game_id VARCHAR(36) NOT NULL,
    game_id INT NULL,
    submitter_username VARCHAR(100) NOT NULL DEFAULT '',
    extension_version VARCHAR(20) NULL,
    turn_timing JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_crucible_game_id (crucible_game_id),
    INDEX idx_game_id (game_id),
    FOREIGN KEY (game_id) REFERENCES tracker_game(id) ON DELETE SET NULL
);
