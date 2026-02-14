import apiClient from './client';
import type { GameSummary, GameDetail } from '../types';

export async function getRecentGames(limit: number = 5): Promise<GameSummary[]> {
  const { data } = await apiClient.get('/games/recent', { params: { limit } });
  return data;
}

export async function searchGames(params: Record<string, string | undefined>): Promise<GameSummary[]> {
  const filtered = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
  );
  const { data } = await apiClient.get('/games/search', { params: filtered });
  return data;
}

export async function getGame(crucibleGameId: string): Promise<GameDetail> {
  const { data } = await apiClient.get(`/games/${crucibleGameId}`);
  return data;
}
