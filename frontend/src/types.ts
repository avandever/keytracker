export interface AuthUser {
  id: number;
  email: string;
  name: string;
  avatar_url: string | null;
  is_patron: boolean;
  is_member: boolean;
  patreon_tier_title: string | null;
  patreon_linked: boolean;
  google_linked: boolean;
  discord_linked: boolean;
  discord_username: string | null;
  dok_api_key: string | null;
  tco_usernames: string[];
  is_league_admin: boolean;
  show_test_user_picker: boolean;
  dok_profile_url: string | null;
  country: string | null;
  timezone: string | null;
  mailing_address_line1: string | null;
  mailing_address_line2: string | null;
  mailing_city: string | null;
  mailing_state: string | null;
  mailing_postal_code: string | null;
  mailing_country: string | null;
}

export interface TurnTimingEntry {
  turn: number;
  player: string;
  house: string;
  timestamp_ms: number;
}

export interface KeyForgeEvent {
  turn: number;
  player: string;
  key_color: string;
  amber_paid: number;
  timestamp_ms: number;
}

export interface HouseTimingStat {
  house: string;
  avg_seconds: number;
  turn_count: number;
}

export interface TimingStats {
  avg_turn_seconds: number;
  house_breakdown: HouseTimingStat[];
  turn_count: number;
  games_sampled: number;
}

export interface TimingLeaderboardEntry {
  username: string;
  avg_turn_seconds: number;
  turn_count: number;
  games_sampled: number;
}

export interface HandCardSnapshot {
  id: string;
  name: string;
  type: string;
  house: string;
  amber: number;
  can_play: boolean;
  enhancements?: string[];
}

export interface BoardCardSnapshot {
  id: string;
  name: string;
  type: string;
  house: string;
  power: number;
  amber: number;
  exhausted: boolean;
  stunned: boolean;
  taunt: boolean;
  enhancements?: string[];
}

export interface TurnSnapshot {
  turn: number;
  player: string;
  house: string;
  timestamp_ms: number;
  local_hand: HandCardSnapshot[];
  boards: Record<string, BoardCardSnapshot[]>;
  amber: Record<string, number>;
  deck_size: Record<string, number>;
  discard_size: Record<string, number>;
  archive_size: Record<string, number>;
}

export interface KeySlotStat {
  avg_turn: number;
  avg_amber: number;
  count: number;
}

export interface KeyStats {
  key_1: KeySlotStat | null;
  key_2: KeySlotStat | null;
  key_3: KeySlotStat | null;
  total_keys: number;
  games_sampled: number;
}

export interface ExtendedGameData {
  submitter_username: string;
  extension_version: string | null;
  turn_timing: TurnTimingEntry[];
  player2_username: string | null;
  player2_extension_version: string | null;
  player2_turn_timing: TurnTimingEntry[];
  key_events: KeyForgeEvent[];
  player2_key_events: KeyForgeEvent[];
  turn_snapshots: TurnSnapshot[];
  player2_turn_snapshots: TurnSnapshot[];
  both_perspectives: boolean;
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
  has_extended_data: boolean;
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
  extended_data: ExtendedGameData | null;
  card_images: Record<string, string>;
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

export interface CollectionDeck extends DeckSummary {
  dok_owned: boolean;
  dok_wishlist: boolean;
  dok_funny: boolean;
  dok_notes: string | null;
}

export interface AllianceDeckEntry {
  kf_id: string;
  name: string;
  sas_rating: number | null;
  aerc_score: number | null;
  pods: { house: string; source_kf_id: string; source_name: string }[] | null;
  dok_owned: boolean;
  dok_wishlist: boolean;
  dok_funny: boolean;
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
  key_stats: KeyStats | null;
}

export interface UserStats {
  username: string;
  games_won: number;
  games_lost: number;
  games: GameSummary[];
  discord_username: string | null;
  dok_profile_url: string | null;
  timing_stats: TimingStats | null;
  key_stats: KeyStats | null;
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
  tco_username: string | null;
  discord_username: string | null;
  dok_profile_url: string | null;
}

export interface DeckEntryLogEntry {
  id: number;
  week_id: number;
  week_name: string | null;
  target_user: UserBrief;
  changed_by: UserBrief;
  action: 'added' | 'removed';
  deck_name: string | null;
  deck_kf_id: string | null;
  slot_number: number | null;
  created_at: string;
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
  allow_peer_deck_entry: boolean;
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
  url_name: string | null;
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
  deck?: DeckBrief | null;
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
  sas_floor: number | null;
  combined_max_sas: number | null;
  set_diversity: boolean | null;
  house_diversity: boolean | null;
  decks_per_player: number | null;
  sealed_pools_generated: boolean;
  no_keycheat: boolean | null;
  thief_floor_team_id?: number | null;
  matchups: WeekMatchup[];
  deck_selections: DeckSelectionInfo[];
  feature_designations: { team_id: number; user_id: number }[];
  alliance_selections?: AlliancePodSelectionInfo[];
  thief_curation_decks?: ThiefCurationDeckInfo[];
  thief_steals?: ThiefStealInfo[];
  alliance_restricted_list_version?: AllianceRestrictedListVersion | null;
  sas_ladder_maxes: number[] | null;
  sas_ladder_feature_rung: number | null;
  sas_ladder_assignments?: { id: number; user_id: number; team_id: number; rung_number: number }[];
  custom_description?: string | null;
  hide_standard_description?: boolean;
  feature_volunteers?: { team_id: number; user_id: number }[];
  deck_suggestions?: {
    id: number;
    team_id: number;
    suggesting_user_id: number;
    deck: DeckSummary | null;
  }[];
}

export interface WeekMatchup {
  id: number;
  week_id: number;
  team1: TeamDetail;
  team2: TeamDetail;
  thief_stolen_team_id?: number | null;
  is_double_loss: boolean;
  player_matchups: PlayerMatchupInfo[];
}

export interface TriadShortPickInfo {
  picking_user_id: number;
  picked_deck_selection_id: number;
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
  adaptive_bid_chains: number | null;
  adaptive_bidder_id: number | null;
  adaptive_bidding_complete: boolean;
  adaptive_winning_deck_player_id: number | null;
  triad_short_picks_count?: number;
  triad_short_picks?: TriadShortPickInfo[];
  oubliette_p1_banned_house?: string | null;
  oubliette_p2_banned_house?: string | null;
  oubliette_p1_eligible_deck_ids?: number[] | null;
  oubliette_p2_eligible_deck_ids?: number[] | null;
  adaptive_short_choices_count?: number;
  adaptive_short_choices?: AdaptiveShortChoiceInfo[];
  adaptive_short_bid_chains?: number | null;
  adaptive_short_bidder_id?: number | null;
  adaptive_short_bidding_complete?: boolean;
  exchange_borrows_count?: number;
  exchange_borrows?: ExchangeBorrowInfo[] | null;
  nordic_hexad_phase?: number | null;
  nordic_hexad_actions?: NordicHexadActionInfo[];
  nordic_hexad_pending_phase_count?: number | null;
  nordic_p1_remaining_deck_ids?: number[] | null;
  nordic_p2_remaining_deck_ids?: number[] | null;
  moirai_assignments_count?: number | null;
  moirai_assignments?: MoiraiAssignmentInfo[] | null;
  tertiate_purge_choices?: TertiatePurgeChoiceInfo[];
  result_confirmed: boolean;
  result_confirmed_at: string | null;
  schedule_confirmed_time?: string | null;
  schedule_proposals?: { user_id: number; times: string[] }[];
}

export interface AdaptiveShortChoiceInfo {
  choosing_user_id: number;
  chosen_deck_selection_id: number;
}

export interface ExchangeBorrowInfo {
  borrowing_user_id: number;
  borrowed_deck_selection_id: number;
}

export interface NordicHexadActionInfo {
  player_id: number;
  phase: number;
  target_deck_selection_id: number;
}

export interface MoiraiAssignmentInfo {
  assigning_user_id: number;
  game_number: number;
  assigned_deck_selection_id: number;
}

export interface TertiatePurgeChoiceInfo {
  choosing_user_id: number;
  purged_house: string;
  game_number: number;
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
  game_id: number | null;
  created_at: string | null;
}

export interface StrikeInfo {
  striking_user_id: number;
  struck_deck_selection_id: number;
}

// --- Alliance Restricted List ---

export interface AllianceRestrictedListVersion {
  id: number;
  version: number;
}

// --- Standalone Match types ---

export type StandaloneMatchStatus = 'setup' | 'deck_selection' | 'published' | 'completed';

export interface StandaloneMatch {
  id: number;
  uuid: string;
  creator: UserBrief;
  opponent: UserBrief | null;
  format_type: string;
  status: StandaloneMatchStatus;
  best_of_n: number;
  is_public: boolean;
  max_sas: number | null;
  sas_floor: number | null;
  combined_max_sas: number | null;
  set_diversity: boolean;
  house_diversity: boolean;
  decks_per_player: number;
  sealed_pools_generated: boolean;
  no_keycheat: boolean;
  allowed_sets: number[] | null;
  created_at: string | null;
  matchup: PlayerMatchupInfo | null;
  creator_selections: DeckSelectionInfo[];
  opponent_selections: DeckSelectionInfo[];
  creator_pods: AlliancePodSelectionInfo[];
  opponent_pods: AlliancePodSelectionInfo[];
  alliance_restricted_list_version: AllianceRestrictedListVersion | null;
}

export interface AdminLogEntry {
  id: number;
  league_id: number;
  week_id: number | null;
  user: UserBrief;
  action_type: string;
  details: string | null;
  created_at: string | null;
}

export interface DeckBrief {
  db_id: number;
  kf_id: string;
  name: string;
  expansion: number;
  expansion_name: string;
  sas_rating: number | null;
  mv_url: string | null;
  dok_url: string | null;
  houses: string[];
}

export interface AlliancePodEntry {
  deck: DeckBrief;
  house_name: string | null;
  slot_type: 'pod' | 'token' | 'prophecy';
  slot_number: number;
}

export type CompletedMatchDecks = Record<string, {
  player1_decks?: DeckBrief[];
  player2_decks?: DeckBrief[];
  player1_pods?: AlliancePodEntry[];
  player2_pods?: AlliancePodEntry[];
}>;

export interface DeckExportSlot {
  slot_number: number;
  dok_url: string | null;
  deck_name: string;
}

export interface DeckExportPod {
  slot_number: number;
  dok_url: string | null;
  house_name: string | null;
}

export interface DeckExportPlayerData {
  user_id: number;
  slots?: DeckExportSlot[];
  stolen?: boolean | null;
  pods?: DeckExportPod[];
  extra?: string;
}

export interface DeckExportWeek {
  week_id: number;
  week_number: number;
  name: string | null;
  format_type: string;
  status: string;
  player_data: DeckExportPlayerData[];
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

export type AuctionStatus = 'setup' | 'deck_submission' | 'auction' | 'completed';

export interface AuctionParticipantInfo {
  user_id: number;
  username: string;
  has_submitted: boolean;
}

export interface AuctionDeckInfo {
  id: number;
  brought_by_user_id: number;
  deck: DeckSummary | null;
  has_submitted: boolean;
  assigned_to_user_id: number | null;
  chains_bid: number;
  bids: AuctionBidInfo[];
}

export interface AuctionBidInfo {
  user_id: number;
  username: string;
  chains: number | null;
}

export interface AuctionDetail {
  id: number;
  status: AuctionStatus;
  creator_id: number;
  passphrase?: string | null;
  player_order: number[];
  participants: AuctionParticipantInfo[];
  decks: AuctionDeckInfo[];
  active_deck_id: number | null;
  active_deck_bids: AuctionBidInfo[];
  current_picker_id: number | null;
  current_bidder_id: number | null;
}

export interface DeckCardEntry {
  card_title: string;
  card_type: string;
  front_image: string | null;
  is_maverick: boolean;
  is_anomaly: boolean;
}
