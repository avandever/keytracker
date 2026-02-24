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
  dok_profile_url: string | null;
  country: string | null;
  timezone: string | null;
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
  db_id?: number;
  houses?: string[];
  token_name?: string | null;
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
  week_bonus_points: number;
  is_test: boolean;
  created_by: UserBrief;
  signup_count: number;
  created_at: string | null;
}

export interface LeagueDetail extends LeagueSummary {
  teams: TeamDetail[];
  signups: SignupInfo[];
  admins: UserBrief[];
  weeks: LeagueWeek[];
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

// --- League Week types ---

export interface KeyforgeSetInfo {
  number: number;
  name: string;
  shortname: string;
}

// Must be kept in sync with WeekStatus enum in keytracker/schema.py
export type WeekStatus =
  | 'setup'
  | 'curation'
  | 'thief'
  | 'deck_selection'
  | 'team_paired'
  | 'pairing'
  | 'published'
  | 'completed';

export interface AlliancePodSelectionInfo {
  id: number;
  user_id: number;
  deck_id: number;
  deck_name: string | null;
  house_name: string | null;
  slot_type: 'pod' | 'token' | 'prophecy';
  slot_number: number;
}

export interface ThiefCurationDeckInfo {
  id: number;
  team_id: number;
  slot_number: number;
  deck: DeckSummary | null;
}

export interface ThiefStealInfo {
  id: number;
  stealing_team_id: number;
  curation_deck_id: number;
}

export interface LeagueWeek {
  id: number;
  league_id: number;
  week_number: number;
  name: string | null;
  format_type: string;
  status: WeekStatus;
  best_of_n: number;
  allowed_sets: number[] | null;
  max_sas: number | null;
  combined_max_sas: number | null;
  set_diversity: boolean | null;
  house_diversity: boolean | null;
  decks_per_player: number | null;
  sealed_pools_generated: boolean;
  thief_floor_team_id?: number | null;
  matchups: WeekMatchup[];
  deck_selections: DeckSelectionInfo[];
  feature_designations: { team_id: number; user_id: number }[];
  alliance_selections?: AlliancePodSelectionInfo[];
  thief_curation_decks?: ThiefCurationDeckInfo[];
  thief_steals?: ThiefStealInfo[];
}

export interface WeekMatchup {
  id: number;
  week_id: number;
  team1: TeamDetail;
  team2: TeamDetail;
  thief_stolen_team_id?: number | null;
  player_matchups: PlayerMatchupInfo[];
}

export interface PlayerMatchupInfo {
  id: number;
  week_matchup_id: number;
  player1: UserBrief;
  player2: UserBrief;
  player1_started: boolean;
  player2_started: boolean;
  is_feature: boolean;
  games: MatchGameInfo[];
  strikes: StrikeInfo[];
}

export interface DeckSelectionInfo {
  id: number;
  week_id: number;
  user_id: number;
  slot_number: number;
  deck: DeckSummary | null;
}

export interface MatchGameInfo {
  id: number;
  player_matchup_id: number;
  game_number: number;
  winner_id: number;
  player1_keys: number;
  player2_keys: number;
  went_to_time: boolean;
  loser_conceded: boolean;
  player1_deck_id: number | null;
  player2_deck_id: number | null;
  reported_by_id: number | null;
  created_at: string | null;
}

export interface StrikeInfo {
  striking_user_id: number;
  struck_deck_selection_id: number;
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
