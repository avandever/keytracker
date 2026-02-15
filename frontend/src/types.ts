export interface AuthUser {
  id: number;
  email: string;
  name: string;
  avatar_url: string | null;
}

export interface GameSummary {
  crucible_game_id: string;
  date: string | null;
  winner: string;
  loser: string;
  winner_keys: number;
  loser_keys: number;
  winner_deck_name: string;
  loser_deck_name: string;
  winner_deck_id: string | null;
  loser_deck_id: string | null;
  winner_sas_rating: number | null;
  loser_sas_rating: number | null;
  winner_aerc_score: number | null;
  loser_aerc_score: number | null;
  first_player: string;
}

export interface LogEntry {
  message: string;
  time: string | null;
  winner_perspective: boolean;
}

export interface HouseTurnCount {
  player: string | null;
  house: string;
  turns: number;
  winner: boolean;
}

export interface GameDetail extends GameSummary {
  logs: LogEntry[];
  house_turn_counts: HouseTurnCount[];
}

export interface DeckSummary {
  kf_id: string;
  name: string;
  expansion: number;
  expansion_name: string;
  sas_rating: number | null;
  aerc_score: number | null;
  mv_url: string;
  dok_url: string;
}

export interface PodStat {
  house: string;
  sas_rating: number;
  aerc_score: number;
  enhanced_amber: number;
  enhanced_capture: number;
  enhanced_draw: number;
  enhanced_damage: number;
  enhanced_discard: number;
  num_enhancements: number;
  num_mutants: number;
  creatures: number;
  raw_amber: number;
  total_amber: number;
}

export interface DeckDetail extends DeckSummary {
  houses: string[];
  pod_stats: PodStat[];
  games_won: number;
  games_lost: number;
  games: GameSummary[];
}

export interface UserStats {
  username: string;
  games_won: number;
  games_lost: number;
  games: GameSummary[];
}

export interface CsvPod {
  name: string;
  sas: number;
  expansion: string;
  house: string;
  cards: string;
  link: string;
  on_market: boolean;
  price: string;
}
