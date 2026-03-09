ALTER TABLE extended_game_data ADD COLUMN key_events JSON NULL AFTER player2_turn_timing;
ALTER TABLE extended_game_data ADD COLUMN player2_key_events JSON NULL AFTER key_events;
