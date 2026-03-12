-- Migration: Collection sync job queue table

CREATE TABLE IF NOT EXISTS collection_sync_job (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL,
    started_at DATETIME NULL,
    completed_at DATETIME NULL,
    standard_decks INT NULL,
    alliance_decks INT NULL,
    error TEXT NULL,
    INDEX idx_collection_sync_job_user_id (user_id),
    CONSTRAINT fk_collection_sync_job_user FOREIGN KEY (user_id) REFERENCES tracker_user(id)
);
