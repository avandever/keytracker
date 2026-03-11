ALTER TABLE extended_game_data ADD COLUMN turn_snapshots JSON NULL AFTER player2_key_events;
ALTER TABLE extended_game_data ADD COLUMN player2_turn_snapshots JSON NULL AFTER turn_snapshots;
