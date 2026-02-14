import apiClient from './client';
import type { DeckSummary, DeckDetail } from '../types';

export async function searchDecks(params: Record<string, string | undefined>): Promise<DeckSummary[]> {
  const filtered = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
  );
  const { data } = await apiClient.get('/decks/search', { params: filtered });
  return data;
}

export async function getDeck(deckId: string, username?: string): Promise<DeckDetail> {
  const params = username ? { username } : {};
  const { data } = await apiClient.get(`/decks/${deckId}`, { params });
  return data;
}
