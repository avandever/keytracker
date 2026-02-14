import apiClient from './client';
import type { UserStats } from '../types';

export async function getUser(username: string, page: number = 1): Promise<UserStats> {
  const { data } = await apiClient.get(`/users/${username}`, { params: { page } });
  return data;
}
