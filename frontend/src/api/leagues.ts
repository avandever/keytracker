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
  AlliancePodSelectionInfo,
  AllianceRestrictedListVersion,
  AdminLogEntry,
  CompletedMatchDecks,
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
    week_bonus_points: number;
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

export interface TeamSealedPoolEntry {
  id: number;
  deck: DeckSummary | null;
  claimed_by_user_id: number | null;
  pods_claimed: { house_name: string; user_id: number }[];
}

export async function getTeamSealedPool(
  leagueId: number,
  weekId: number,
  teamId?: number,
): Promise<TeamSealedPoolEntry[]> {
  const params = teamId ? `?team_id=${teamId}` : '';
  const { data } = await apiClient.get(`/leagues/${leagueId}/weeks/${weekId}/team-sealed-pool${params}`);
  return data;
}

// --- Alliance Restricted List ---

export async function getRestrictedListVersions(): Promise<AllianceRestrictedListVersion[]> {
  const { data } = await apiClient.get('/alliance-restricted-list-versions');
  return data;
}

// --- Alliance Pod Selection (Sealed Alliance) ---

export async function submitAllianceSelection(
  leagueId: number,
  weekId: number,
  payload: {
    pods: { deck_id: number; house: string }[];
    token_deck_id?: number;
    prophecy_deck_id?: number;
    user_id?: number;
  },
): Promise<AlliancePodSelectionInfo[]> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/weeks/${weekId}/alliance-selection`,
    payload,
  );
  return data;
}

export async function clearAllianceSelection(
  leagueId: number,
  weekId: number,
  userId?: number,
): Promise<void> {
  const params = userId ? `?user_id=${userId}` : '';
  await apiClient.delete(`/leagues/${leagueId}/weeks/${weekId}/alliance-selection${params}`);
}

// --- Thief Format ---

export async function submitCurationDeck(
  leagueId: number,
  weekId: number,
  payload: { deck_url: string; slot_number: number; team_id?: number },
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/weeks/${weekId}/curation-deck`,
    payload,
  );
  return data;
}

export async function removeCurationDeck(
  leagueId: number,
  weekId: number,
  slot: number,
  teamId?: number,
): Promise<void> {
  const params = teamId ? `?team_id=${teamId}` : '';
  await apiClient.delete(`/leagues/${leagueId}/weeks/${weekId}/curation-deck/${slot}${params}`);
}

export async function advanceToThief(
  leagueId: number,
  weekId: number,
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/weeks/${weekId}/advance-to-thief`);
  return data;
}

export async function submitSteals(
  leagueId: number,
  weekId: number,
  curationDeckIds: number[],
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/weeks/${weekId}/steal`, {
    curation_deck_ids: curationDeckIds,
  });
  return data;
}

export async function endThief(
  leagueId: number,
  weekId: number,
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(`/leagues/${leagueId}/weeks/${weekId}/end-thief`);
  return data;
}

// --- Feature Designation ---

export async function setFeatureDesignation(
  leagueId: number,
  weekId: number,
  userId: number,
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/weeks/${weekId}/feature-designation`,
    { user_id: userId },
  );
  return data;
}

export async function clearFeatureDesignation(
  leagueId: number,
  weekId: number,
): Promise<LeagueWeek> {
  const { data } = await apiClient.delete(
    `/leagues/${leagueId}/weeks/${weekId}/feature-designation`,
  );
  return data;
}

// --- SAS Ladder ---

export async function setSasLadderAssignment(
  leagueId: number,
  weekId: number,
  rungNumber: number,
  userId?: number,
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/weeks/${weekId}/sas-ladder-assignment`,
    { rung_number: rungNumber, ...(userId !== undefined && { user_id: userId }) },
  );
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

// --- Admin ---

export async function getAdminLog(leagueId: number): Promise<AdminLogEntry[]> {
  const { data } = await apiClient.get(`/leagues/${leagueId}/admin-log`);
  return data;
}

export async function regeneratePlayerMatchups(
  leagueId: number,
  weekId: number,
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/weeks/${weekId}/regenerate-player-matchups`,
  );
  return data;
}

export async function editMatchup(
  leagueId: number,
  weekId: number,
  matchupId: number,
  payload: { player1_id?: number; player2_id?: number },
): Promise<PlayerMatchupInfo> {
  const { data } = await apiClient.put(
    `/leagues/${leagueId}/weeks/${weekId}/matchups/${matchupId}`,
    payload,
  );
  return data;
}

export async function regenerateSealedPools(
  leagueId: number,
  weekId: number,
  userIds?: number[],
): Promise<LeagueWeek> {
  const { data } = await apiClient.post(
    `/leagues/${leagueId}/weeks/${weekId}/regenerate-sealed-pools`,
    userIds ? { user_ids: userIds } : {},
  );
  return data;
}

export async function getCompletedMatchDecks(
  leagueId: number,
  weekId: number,
): Promise<CompletedMatchDecks> {
  const { data } = await apiClient.get(
    `/leagues/${leagueId}/weeks/${weekId}/completed-match-decks`,
  );
  return data;
}
