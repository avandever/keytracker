import apiClient from './client';
import type { UserBrief } from '../types';

/** One bracket: a format, and which player each team puts in it. */
export interface PlayoffBracketInfo {
  id: number;
  bracket_number: number;
  name: string | null;
  format_type: string;
  best_of_n: number;
  assignments: { id: number; team_id: number; user_id: number; user_name: string | null }[];
  matches?: PlayoffMatchInfo[];
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

/** A team's decks for one round, every bracket in one list. */
export interface PlayoffRoundRow {
  bracket: {
    id: number;
    bracket_number: number;
    name: string | null;
    format_type: string;
    best_of_n: number;
  };
  week: any;
  player: UserBrief | null;
  opponent: { team_id: number; team_name: string | null; player: UserBrief | null } | null;
  selections: any[];
  max_slots: number;
  player_matchup_id: number | null;
  is_bye: boolean;
}

export interface PlayoffRoundDecks {
  round: number;
  team_id: number;
  team_name: string | null;
  rows: PlayoffRoundRow[];
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

export async function setPlayoffBrackets(
  leagueId: number,
  brackets: { name?: string | null; format_type: string; best_of_n?: number }[],
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

export async function startPlayoffRound(
  leagueId: number,
  round: number,
): Promise<PlayoffTree> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/playoffs/rounds/${round}/start`,
    {},
  );
  return data;
}

export async function getPlayoffRoundDecks(
  leagueId: number,
  round: number,
  teamId?: number,
): Promise<PlayoffRoundDecks> {
  const { data } = await apiClient.get(`/leagues/${leagueId}/playoffs/rounds/${round}/decks`, {
    params: teamId ? { team_id: teamId } : undefined,
  });
  return data;
}
