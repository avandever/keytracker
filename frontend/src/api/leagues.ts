import apiClient from './client';
import type {
  LeagueSummary,
  LeagueDetail,
  LeagueWeek,
  TeamDetail,
  DraftState,
  UserBrief,
  DeckSummary,
  DeckSelectionInfo,
  PlayerMatchupInfo,
  MatchGameInfo,
  KeyforgeSetInfo,
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
  is_test?: boolean;
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

export async function deleteLeague(leagueId: number): Promise<void> {
  await apiClient.delete(`/leagues/${leagueId}`);
}

export async function deleteWeek(
  leagueId: number,
  weekId: number,
): Promise<void> {
  await apiClient.delete(`/leagues/${leagueId}/weeks/${weekId}`);
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

export async function reassignMember(
  leagueId: number,
  teamId: number,
  memberUserId: number,
  newUserId: number,
): Promise<TeamDetail> {
  const { data } = await apiClient.put(
    `/leagues/${leagueId}/teams/${teamId}/members/${memberUserId}`,
    { new_user_id: newUserId },
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

export async function listTestUsers(): Promise<UserBrief[]> {
  const { data } = await apiClient.get('/leagues/test-users');
  return data;
}

// --- Sets ---

export async function getSets(): Promise<KeyforgeSetInfo[]> {
  const { data } = await apiClient.get('/leagues/sets');
  return data;
}

// --- Weeks ---

export async function getWeeks(leagueId: number): Promise<LeagueWeek[]> {
  const { data } = await apiClient.get(`/leagues/${leagueId}/weeks`);
  return data;
}

export async function createWeek(
  leagueId: number,
  payload: {
    name?: string;
    format_type: string;
    best_of_n: number;
    allowed_sets?: number[] | null;
    max_sas?: number | null;
    combined_max_sas?: number | null;
    set_diversity?: boolean;
    house_diversity?: boolean;
    decks_per_player?: number | null;
  },
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/weeks`, payload);
  return data;
}

export async function updateWeek(
  leagueId: number,
  weekId: number,
  payload: Record<string, unknown>,
): Promise<LeagueWeek> {
  const { data } = await apiClient.put(`/leagues/${leagueId}/weeks/${weekId}`, payload);
  return data;
}

export async function openDeckSelection(
  leagueId: number,
  weekId: number,
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/weeks/${weekId}/open-deck-selection`);
  return data;
}

export async function generateMatchups(
  leagueId: number,
  weekId: number,
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/weeks/${weekId}/generate-matchups`);
  return data;
}

export async function generateTeamPairings(
  leagueId: number,
  weekId: number,
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/weeks/${weekId}/generate-team-pairings`);
  return data;
}

export async function generatePlayerMatchups(
  leagueId: number,
  weekId: number,
  force?: boolean,
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/weeks/${weekId}/generate-player-matchups`,
    force ? { force: true } : {},
  );
  return data;
}

export async function publishWeek(
  leagueId: number,
  weekId: number,
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/weeks/${weekId}/publish`);
  return data;
}

export async function checkWeekCompletion(
  leagueId: number,
  weekId: number,
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/weeks/${weekId}/check-completion`);
  return data;
}

// --- Deck Selection ---

export async function submitDeckSelection(
  leagueId: number,
  weekId: number,
  payload: { deck_url?: string; deck_id?: number; slot_number?: number; user_id?: number },
): Promise<DeckSelectionInfo[]> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/weeks/${weekId}/deck-selection`,
    payload,
  );
  return data;
}

export async function removeDeckSelection(
  leagueId: number,
  weekId: number,
  slot: number,
  userId?: number,
): Promise<void> {
  const params = userId ? `?user_id=${userId}` : '';
  await apiClient.delete(`/leagues/${leagueId}/weeks/${weekId}/deck-selection/${slot}${params}`);
}

// --- Sealed Pools ---

export async function generateSealedPools(
  leagueId: number,
  weekId: number,
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/weeks/${weekId}/generate-sealed-pools`);
  return data;
}

export interface SealedPoolEntry {
  id: number;
  deck: DeckSummary | null;
}

export async function getSealedPool(
  leagueId: number,
  weekId: number,
  userId?: number,
): Promise<SealedPoolEntry[]> {
  const params = userId ? `?user_id=${userId}` : '';
  const { data } = await apiClient.get(`/leagues/${leagueId}/weeks/${weekId}/sealed-pool${params}`);
  return data;
}

// --- Strikes (Triad) ---

export async function submitStrike(
  leagueId: number,
  matchupId: number,
  struckDeckSelectionId: number,
): Promise<PlayerMatchupInfo> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/matches/${matchupId}/strike`,
    { struck_deck_selection_id: struckDeckSelectionId },
  );
  return data;
}

// --- Matches ---

export async function startMatch(
  leagueId: number,
  matchupId: number,
): Promise<PlayerMatchupInfo> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/matches/${matchupId}/start`);
  return data;
}

export async function getMatch(
  leagueId: number,
  matchupId: number,
): Promise<PlayerMatchupInfo> {
  const { data } = await apiClient.get(`/leagues/${leagueId}/matches/${matchupId}`);
  return data;
}

export async function reportGame(
  leagueId: number,
  matchupId: number,
  payload: {
    game_number: number;
    winner_id: number;
    player1_keys: number;
    player2_keys: number;
    went_to_time?: boolean;
    loser_conceded?: boolean;
    player1_deck_id?: number;
    player2_deck_id?: number;
  },
): Promise<MatchGameInfo> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/matches/${matchupId}/games`,
    payload,
  );
  return data;
}
