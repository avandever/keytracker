export interface AuthUser {
  id: number;
  email: string;
  name: string;
  avatar_url: string | null;
  is_patron: boolean;
  is_member: boolean;
  patreon_tier_title: string | null;
  patreon_linked: boolean;
  dok_api_key: string | null;
  tco_usernames: string[];
  is_league_admin: boolean;
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

export interface MyGamesResponse {
  tco_usernames: string[];
  games_won: number;
  games_lost: number;
  games: GameSummary[];
  error?: string;
}

// --- League types ---

export interface UserBrief {
  id: number;
  name: string;
  email: string;
  avatar_url: string | null;
  is_test_user: boolean;
}

export interface TeamMemberInfo {
  id: number;
  user: UserBrief;
  is_captain: boolean;
  has_paid: boolean;
}

export interface TeamDetail {
  id: number;
  name: string;
  order_number: number;
  members: TeamMemberInfo[];
}

export interface SignupInfo {
  id: number;
  user: UserBrief;
  signup_order: number;
  status: string;
  signed_up_at: string | null;
}

export interface LeagueSummary {
  id: number;
  name: string;
  description: string | null;
  fee_amount: number | null;
  team_size: number;
  num_teams: number;
  status: string;
  is_test: boolean;
  created_by: UserBrief;
  signup_count: number;
  created_at: string | null;
}

export interface LeagueDetail extends LeagueSummary {
  teams: TeamDetail[];
  signups: SignupInfo[];
  admins: UserBrief[];
  is_admin: boolean;
  is_signed_up: boolean;
  my_team_id: number | null;
  is_captain: boolean;
}

export interface DraftPickInfo {
  round_number: number;
  pick_number: number;
  team_id: number;
  team_name: string | null;
  picked_user: UserBrief | null;
  picked_at: string | null;
}

export interface DraftSlot {
  team_id: number;
  team_name: string;
  pick: DraftPickInfo | null;
}

export interface DraftRound {
  round: number;
  picks: DraftSlot[];
}

export interface DraftState {
  league_id: number;
  status: string;
  is_complete: boolean;
  total_picks: number;
  picks_made: number;
  current_round: number | null;
  current_pick: number | null;
  current_team: TeamDetail | null;
  available_players: UserBrief[];
  pick_history: DraftPickInfo[];
  draft_board: DraftRound[];
  teams: TeamDetail[];
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
