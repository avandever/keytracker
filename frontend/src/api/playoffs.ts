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
  banned_card_names?: string[] | null;
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
  /** Only the viewer's own team until an admin publishes the assignments. */
  assignments: { id: number; team_id: number; user_id: number; user_name: string | null }[];
  /** False while the list above is scoped to the viewer's own team. */
  assignments_revealed?: boolean;
  /** True once the bracket has matchups, after which its players are fixed. */
  assignments_locked?: boolean;
  /** True while the bracket is still being filled, so its teams read null. */
  pairings_hidden?: boolean;
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
  /** Who each team put in this bracket; null until assignments are published. */
  team1_player?: string | null;
  team2_player?: string | null;
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
  /** Set when the admin reveals who each team put in each bracket. */
  assignments_published_at: string | null;
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
  /** How far each qualifying team has got, saying nothing about who. */
  assignment_progress: PlayoffAssignmentProgress[];
  /** Decks in per team, per open round. Empty until a round opens. */
  deck_progress: PlayoffDeckProgress[];
}

/** One round's deck submissions, by team, with no deck named. */
export interface PlayoffDeckProgress {
  round_number: number;
  teams: {
    team_id: number;
    team_name: string | null;
    submitted: number;
    expected: number;
  }[];
}

/** One team's progress through the brackets, with no names in it. */
export interface PlayoffAssignmentProgress {
  team_id: number;
  team_name: string | null;
  assigned: number;
  total: number;
}

export interface PlayoffTree {
  rounds: number;
  teams: Record<string, string>;
  drawn_at: string | null;
  brackets: PlayoffBracketInfo[];
  started_round?: number;
  /** Matches left unmade because the assignments are not published yet. */
  matches_deferred?: number;
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

/**
 * Reveal who each team put in each bracket, or take the reveal back.
 *
 * Separate from publishing the setup: that one lets captains assign, this one
 * shows everybody what they assigned, and it is refused until every bracket is
 * filled so that nobody picks against an opponent they can already see.
 */
export async function publishPlayoffAssignments(
  leagueId: number,
  published = true,
): Promise<PlayoffConfigInfo> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/playoffs/assignments/publish`,
    { published },
  );
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
    /** Open this bracket alone, rather than every bracket in the round. */
    bracket_id?: number;
  },
): Promise<PlayoffTree> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/playoffs/rounds/${round}/start`,
    deadlines || {},
  );
  return data;
}

/**
 * Publish a round's pairings, which is what lets results be reported.
 *
 * Separate from opening the round: opening makes the weeks and their
 * matchups so decks can go in, this says the matches are live. Refused while
 * anyone still owes a deck unless `force` is set, and `published: false` puts
 * a round back as long as nothing has been played.
 */
export async function publishPlayoffRound(
  leagueId: number,
  round: number,
  opts?: { bracket_id?: number; force?: boolean; published?: boolean },
): Promise<PlayoffTree> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/playoffs/rounds/${round}/publish`,
    opts || {},
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
