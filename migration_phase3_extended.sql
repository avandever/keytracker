ALTER TABLE extended_game_data
  ADD COLUMN player2_username VARCHAR(100) NULL AFTER turn_timing,
  ADD COLUMN player2_extension_version VARCHAR(20) NULL AFTER player2_username,
  ADD COLUMN player2_turn_timing JSON NULL AFTER player2_extension_version;
