import apiClient from './client';

export interface FantasyPlayerCost {
  player_user_id: number;
  player_name: string | null;
  cost: number;
  is_new_player: boolean;
  source_wins: number | null;
}

export interface FantasyRosterSlot {
  player_user_id: number;
  player_name: string | null;
  slot_number: number;
  is_captain: boolean;
  cost_at_draft: number;
  is_new_at_draft: boolean;
}

export interface FantasyTeam {
  id: number;
  name: string;
  manager_user_id: number;
  manager_name: string | null;
  joined_week_number: number | null;
  roster_cost: number;
  /** Absent while rosters are private and this is not your own team. */
  roster?: FantasyRosterSlot[];
}

export interface FantasyLeague {
  id: number;
  league_id: number;
  league_name: string | null;
  name: string;
  status: 'setup' | 'open' | 'locked' | 'completed';
  commissioner_id: number;
  commissioner_name: string | null;
  viewer_is_commissioner: boolean;
  roster_lock_at: string | null;
  allow_late_entry: boolean;
  roster_size: number;
  salary_cap: number;
  cost_source_league_id: number | null;
  cost_min: number;
  cost_max: number;
  points_per_match_win: number;
  weekly_threshold: number | null;
  weekly_threshold_bonus: number;
  captain_bonus_enabled: boolean;
  feature_win_bonus: number;
  scarcity_bonus_enabled: boolean;
  scarcity_bands: [number | null, number][] | null;
  rosters_public: boolean;
  team_count: number;
  teams?: FantasyTeam[];
}

export interface FantasyStandingRow {
  rank: number;
  team_id: number;
  team_name: string;
  manager_name: string | null;
  joined_week_number: number | null;
  match_wins: number;
  weekly_bonus: number;
  captain_bonus: number;
  scarcity_bonus: number;
  feature_bonus: number;
  total: number;
  roster_cost: number;
  weekly: number[];
}

export async function listFantasyLeagues(leagueId?: number): Promise<FantasyLeague[]> {
  const { data } = await apiClient.get('/fantasy/', {
    params: leagueId ? { league_id: leagueId } : undefined,
  });
  return data;
}

export async function getFantasyLeague(id: number): Promise<FantasyLeague> {
  const { data } = await apiClient.get(`/fantasy/${id}`);
  return data;
}

export async function createFantasyLeague(payload: {
  league_id: number;
  name: string;
  cost_source_league_id?: number | null;
}): Promise<FantasyLeague> {
  const { data } = await apiClient.post('/fantasy/', payload);
  return data;
}

export async function updateFantasyLeague(
  id: number,
  payload: Partial<FantasyLeague>,
): Promise<FantasyLeague> {
  const { data } = await apiClient.put(`/fantasy/${id}`, payload);
  return data;
}

export async function setFantasyStatus(
  id: number,
  status: FantasyLeague['status'],
): Promise<FantasyLeague> {
  const { data } = await apiClient.post(`/fantasy/${id}/status`, { status });
  return data;
}

export async function getFantasyCosts(id: number): Promise<FantasyPlayerCost[]> {
  const { data } = await apiClient.get(`/fantasy/${id}/costs`);
  return data;
}

export async function regenerateFantasyCosts(id: number): Promise<FantasyPlayerCost[]> {
  const { data } = await apiClient.post(`/fantasy/${id}/costs/generate`);
  return data;
}

export async function updateFantasyCost(
  id: number,
  playerUserId: number,
  payload: { cost?: number; is_new_player?: boolean },
): Promise<FantasyPlayerCost> {
  const { data } = await apiClient.put(`/fantasy/${id}/costs/${playerUserId}`, payload);
  return data;
}

export async function getMyFantasyTeam(id: number): Promise<FantasyTeam | null> {
  const { data } = await apiClient.get(`/fantasy/${id}/teams/mine`);
  return data;
}

export async function submitFantasyEntry(
  id: number,
  payload: { name: string; player_user_ids: number[]; captain_user_id: number },
): Promise<FantasyTeam> {
  const { data } = await apiClient.post(`/fantasy/${id}/teams`, payload);
  return data;
}

export async function withdrawFantasyEntry(id: number): Promise<void> {
  await apiClient.delete(`/fantasy/${id}/teams/mine`);
}

export async function getFantasyStandings(
  id: number,
): Promise<{ status: string; standings: FantasyStandingRow[] }> {
  const { data } = await apiClient.get(`/fantasy/${id}/standings`);
  return data;
}
