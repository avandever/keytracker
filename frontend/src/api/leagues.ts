import apiClient from './client';
import type {
  LeagueSummary,
  LeagueDetail,
  TeamDetail,
  DraftState,
} from '../types';

export async function listLeagues(): Promise<LeagueSummary[]> {
  const { data } = await apiClient.get('/leagues/');
  return data;
}

export async function createLeague(payload: {
  name: string;
  description?: string;
  fee_amount?: number | null;
  team_size: number;
  num_teams: number;
}): Promise<LeagueDetail> {
  const { data } = await apiClient.post('/leagues/', payload);
  return data;
}

export async function getLeague(leagueId: number): Promise<LeagueDetail> {
  const { data } = await apiClient.get(`/leagues/${leagueId}`);
  return data;
}

export async function updateLeague(
  leagueId: number,
  payload: Partial<{
    name: string;
    description: string;
    fee_amount: number | null;
    team_size: number;
    num_teams: number;
  }>,
): Promise<LeagueDetail> {
  const { data } = await apiClient.put(`/leagues/${leagueId}`, payload);
  return data;
}

export async function signup(leagueId: number): Promise<void> {
  await apiClient.post(`/leagues/${leagueId}/signup`);
}

export async function withdraw(leagueId: number): Promise<void> {
  await apiClient.delete(`/leagues/${leagueId}/signup`);
}

export async function listTeams(leagueId: number): Promise<TeamDetail[]> {
  const { data } = await apiClient.get(`/leagues/${leagueId}/teams`);
  return data;
}

export async function createTeam(
  leagueId: number,
  name: string,
): Promise<TeamDetail> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/teams`, { name });
  return data;
}

export async function updateTeam(
  leagueId: number,
  teamId: number,
  name: string,
): Promise<TeamDetail> {
  const { data } = await apiClient.put(`/leagues/${leagueId}/teams/${teamId}`, { name });
  return data;
}

export async function deleteTeam(
  leagueId: number,
  teamId: number,
): Promise<void> {
  await apiClient.delete(`/leagues/${leagueId}/teams/${teamId}`);
}

export async function assignCaptain(
  leagueId: number,
  teamId: number,
  userId: number,
): Promise<TeamDetail> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/teams/${teamId}/captain`,
    { user_id: userId },
  );
  return data;
}

export async function toggleFeePaid(
  leagueId: number,
  teamId: number,
  userId: number,
  hasPaid: boolean,
): Promise<TeamDetail> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/teams/${teamId}/fees/${userId}`,
    { has_paid: hasPaid },
  );
  return data;
}

export async function addAdmin(
  leagueId: number,
  userId: number,
): Promise<void> {
  await apiClient.post(`/leagues/${leagueId}/admins`, { user_id: userId });
}

export async function removeAdmin(
  leagueId: number,
  userId: number,
): Promise<void> {
  await apiClient.delete(`/leagues/${leagueId}/admins/${userId}`);
}

export async function startDraft(leagueId: number): Promise<DraftState> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/draft/start`);
  return data;
}

export async function getDraft(leagueId: number): Promise<DraftState> {
  const { data } = await apiClient.get(`/leagues/${leagueId}/draft`);
  return data;
}

export async function makePick(
  leagueId: number,
  userId: number,
): Promise<DraftState> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/draft/pick`, {
    user_id: userId,
  });
  return data;
}
