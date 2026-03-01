import apiClient from './client';
import type { StandaloneMatch, MatchGameInfo, DeckSelectionInfo, AlliancePodSelectionInfo, AllianceRestrictedListVersion } from '../types';
import type { SealedPoolEntry } from './leagues';

export interface DeckImportResult {
  id: number;
  kf_id: string;
  name: string;
  expansion: number;
  houses: string[];
  sas_rating: number | null;
}

export interface DokAllianceImportResult {
  pods: { deck_id: number; kf_id: string; deck_name: string; house: string; expansion: number; houses: string[]; sas_rating: number | null }[];
  token_deck_id: number | null;
  prophecy_deck_id: number | null;
  valid_alliance: boolean;
}

export async function importDeckByUrl(url: string): Promise<DeckImportResult> {
  const { data } = await apiClient.post('/decks/import', { url });
  return data;
}

export async function importDokAlliance(url: string): Promise<DokAllianceImportResult> {
  const { data } = await apiClient.post('/dok-alliance/import', { url });
  return data;
}

export async function getRestrictedListVersions(): Promise<AllianceRestrictedListVersion[]> {
  const { data } = await apiClient.get('/alliance-restricted-list-versions');
  return data;
}

export async function createStandaloneMatch(payload: {
  format_type: string;
  best_of_n?: number;
  is_public?: boolean;
  max_sas?: number | null;
  combined_max_sas?: number | null;
  set_diversity?: boolean;
  house_diversity?: boolean;
  allowed_sets?: number[] | null;
  decks_per_player?: number;
}): Promise<StandaloneMatch> {
  const { data } = await apiClient.post('/standalone-matches/', payload);
  return data;
}

export async function getPublicMatches(): Promise<StandaloneMatch[]> {
  const { data } = await apiClient.get('/standalone-matches/public');
  return data;
}

export async function getStandaloneMatch(matchId: number, matchUuid?: string): Promise<StandaloneMatch> {
  const params = matchUuid ? { uuid: matchUuid } : {};
  const { data } = await apiClient.get(`/standalone-matches/${matchId}`, { params });
  return data;
}

export async function joinStandaloneMatch(matchId: number, matchUuid: string): Promise<StandaloneMatch> {
  const { data } = await apiClient.post(`/standalone-matches/${matchId}/join`, { uuid: matchUuid });
  return data;
}

export async function getStandaloneSealedPool(matchId: number): Promise<SealedPoolEntry[]> {
  const { data } = await apiClient.get(`/standalone-matches/${matchId}/sealed-pool`);
  return data;
}

export async function submitStandaloneDeckSelection(
  matchId: number,
  payload: { deck_url?: string; deck_id?: number; slot_number?: number },
): Promise<DeckSelectionInfo[]> {
  const { data } = await apiClient.post(`/standalone-matches/${matchId}/deck-selection`, payload);
  return data;
}

export async function removeStandaloneDeckSelection(
  matchId: number,
  slotNumber: number,
): Promise<void> {
  await apiClient.delete(`/standalone-matches/${matchId}/deck-selection`, {
    data: { slot_number: slotNumber },
  });
}

export async function submitStandaloneAllianceSelection(
  matchId: number,
  payload: {
    pods: { deck_id: number; house: string }[];
    token_deck_id?: number;
    prophecy_deck_id?: number;
  },
): Promise<AlliancePodSelectionInfo[]> {
  const { data } = await apiClient.post(
    `/standalone-matches/${matchId}/alliance-selection`,
    payload,
  );
  return data;
}

export async function clearStandaloneAllianceSelection(matchId: number): Promise<void> {
  await apiClient.delete(`/standalone-matches/${matchId}/alliance-selection`);
}

export async function startStandaloneMatch(matchId: number): Promise<StandaloneMatch> {
  const { data } = await apiClient.post(`/standalone-matches/${matchId}/start`);
  return data;
}

export async function submitStandaloneStrike(
  matchId: number,
  struckDeckSelectionId: number,
): Promise<StandaloneMatch> {
  const { data } = await apiClient.post(`/standalone-matches/${matchId}/strike`, {
    struck_deck_selection_id: struckDeckSelectionId,
  });
  return data;
}

export async function reportStandaloneGame(
  matchId: number,
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
  const { data } = await apiClient.post(`/standalone-matches/${matchId}/games`, payload);
  return data;
}

export async function submitAdaptiveBid(
  matchId: number,
  payload: { chains?: number; concede?: boolean },
): Promise<StandaloneMatch> {
  const { data } = await apiClient.post(`/standalone-matches/${matchId}/adaptive-bid`, payload);
  return data;
}
