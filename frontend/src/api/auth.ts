import apiClient from './client';
import type { AuthUser } from '../types';

export async function getAuthMe(): Promise<AuthUser | null> {
  try {
    const response = await apiClient.get<AuthUser>('/auth/me');
    return response.data;
  } catch {
    return null;
  }
}
