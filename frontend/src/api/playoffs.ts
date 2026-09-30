import apiClient from './client';
import type { RequiredCardCategory } from '../types';

/**
 * The constraints a bracket is played under, in the same shape a week holds
 * them. Starting a round copies these onto the week it makes.
 */
export interface PlayoffBracketConstraints {
  allowed_sets?: number[] | null;
  max_sas?: number | null;
  sas_floor?: number | null;
  combined_max_sas?: number | null;
  set_diversity?: boolean | null;
  house_diversity?: boolean | null;
  decks_per_player?: number | null;
  no_keycheat?: boolean | null;
  alliance_restricted_list_version_id?: number | null;
  sas_ladder_maxes?: number[] | null;
  sas_ladder_feature_rung?: number | null;
  team_max_raw_amber?: number | null;
  team_min_raw_amber?: number | null;
  required_card_names?: string[] | null;
  required_card_categories?: RequiredCardCategory[] | null;
  custom_description?: string | null;
  hide_standard_description?: boolean | null;
}

/** One bracket: a format, and which player each team puts in it. */
export interface PlayoffBracketInfo extends PlayoffBracketConstraints {
  id: number;
  bracket_number: number;
  name: string | null;
  format_type: string;
  best_of_n: number;
  assignments: { id: number; team_id: number; user_id: number; user_name: string | null }[];
  matches?: PlayoffMatchInfo[];
  /** The week this bracket plays in each round, once the round is open. */
  weeks?: PlayoffBracketWeek[];
}

/** One bracket's week in one round, as the setup screen needs it. */
export interface PlayoffBracketWeek {
  id: number;
  week_number: number;
  round_number: number | null;
  status: string;
  format_type: string;
  sealed_pools_generated: boolean;
}

export interface PlayoffMatchInfo {
  id: number;
  round_number: number;
  slot_index: number;
  team1_id: number | null;
  team2_id: number | null;
  winner_team_id: number | null;
  is_bye: boolean;
  is_consolation: boolean;
  player_matchup_id: number | null;
}

export interface PlayoffConfigInfo {
  teams_advancing: number;
  points_per_round: number[];
  consolation_enabled: boolean;
  consolation_points: number;
  bye_policy: 'random_even' | 'team_record' | 'admin' | 'player_record';
  /** Set when the admin shows the setup to the teams, which is what lets
   *  captains fill their brackets on My Team. */
  published_at: string | null;
  drawn_at: string | null;
  /** One bracket per player on a team. */
  expected_brackets: number;
}

export interface PlayoffSetup {
  league_id: number;
  config: PlayoffConfigInfo;
  brackets: PlayoffBracketInfo[];
  qualifiers: { team_id: number; team_name: string | null; position: number }[];
  is_admin: boolean;
  my_team_id: number | null;
  is_captain: boolean;
}

export interface PlayoffTree {
  rounds: number;
  teams: Record<string, string>;
  drawn_at: string | null;
  brackets: PlayoffBracketInfo[];
  started_round?: number;
}

export async function getPlayoffSetup(leagueId: number): Promise<PlayoffSetup> {
  const { data } = await apiClient.get(`/leagues/${leagueId}/playoffs`);
  return data;
}

export async function updatePlayoffConfig(
  leagueId: number,
  config: Partial<PlayoffConfigInfo>,
): Promise<PlayoffConfigInfo> {
  const { data } = await apiClient.put(`/leagues/${leagueId}/playoffs/config`, config);
  return data;
}

export async function publishPlayoffs(
  leagueId: number,
  published = true,
): Promise<PlayoffConfigInfo> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/playoffs/publish`, {
    published,
  });
  return data;
}

export async function setPlayoffBrackets(
  leagueId: number,
  brackets: (PlayoffBracketConstraints & {
    name?: string | null;
    format_type: string;
    best_of_n?: number;
  })[],
): Promise<{ brackets: PlayoffBracketInfo[] }> {
  const { data } = await apiClient.put(`/leagues/${leagueId}/playoffs/brackets`, { brackets });
  return data;
}

export async function setPlayoffQualifiers(
  leagueId: number,
  teamIds: number[],
): Promise<{ qualifiers: PlayoffSetup['qualifiers'] }> {
  const { data } = await apiClient.put(`/leagues/${leagueId}/playoffs/qualifiers`, {
    team_ids: teamIds,
  });
  return data;
}

export async function setPlayoffAssignments(
  leagueId: number,
  teamId: number,
  assignments: { bracket_id: number; user_id: number }[],
): Promise<{ brackets: PlayoffBracketInfo[] }> {
  const { data } = await apiClient.put(`/leagues/${leagueId}/playoffs/assignments`, {
    team_id: teamId,
    assignments,
  });
  return data;
}

export async function drawPlayoffs(leagueId: number): Promise<PlayoffTree> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/playoffs/draw`, {});
  return data;
}

export async function getPlayoffTree(leagueId: number): Promise<PlayoffTree> {
  const { data } = await apiClient.get(`/leagues/${leagueId}/playoffs/brackets/tree`);
  return data;
}

/**
 * Open a round: a week per bracket, and its matches.
 *
 * The deadlines belong to the round rather than the bracket -- a bracket runs
 * for the whole playoffs, a date does not -- so they are given here and apply
 * to every bracket in the round. Sending them for a round already open moves
 * the dates.
 */
export async function startPlayoffRound(
  leagueId: number,
  round: number,
  deadlines?: {
    deck_submission_deadline?: string | null;
    match_completion_deadline?: string | null;
  },
): Promise<PlayoffTree> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/playoffs/rounds/${round}/start`,
    deadlines || {},
  );
  return data;
}

export interface PlayoffStandingRow {
  team_id: number;
  team_name: string | null;
  points: number;
  wins: number;
  matches_played: number;
  /** Rounds come through without playing; they score, but they are not wins. */
  byes: number;
}

export interface PlayoffStandings {
  standings: PlayoffStandingRow[];
  points_per_round: number[];
  consolation_points: number;
}

/** Playoff points, which start from zero rather than carrying the season on. */
export async function getPlayoffStandings(leagueId: number): Promise<PlayoffStandings> {
  const { data } = await apiClient.get(`/leagues/${leagueId}/playoffs/standings`);
  return data;
}
