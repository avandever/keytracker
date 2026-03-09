import apiClient from './client';
import type { UserStats, TimingLeaderboardEntry } from '../types';

export async function getUser(username: string, page: number = 1): Promise<UserStats> {
  const { data } = await apiClient.get(`/users/${username}`, { params: { page } });
  return data;
}

export async function getTimingLeaderboard(): Promise<TimingLeaderboardEntry[]> {
  const { data } = await apiClient.get('/timing-leaderboard');
  return data;
}
