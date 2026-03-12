import apiClient from './client';

export const syncCollection = () =>
  apiClient.post<{ job_id: number; status: string }>('/collection/sync');

export const getSyncStatus = () =>
  apiClient.get<{
    status: string;
    job_id?: number;
    standard_decks?: number;
    alliance_decks?: number;
    error?: string;
  }>('/collection/sync/status');

export const getCollection = (page = 0, type: 'standard' | 'alliance' | 'all' = 'all') =>
  apiClient.get('/collection', { params: { page, type } });
