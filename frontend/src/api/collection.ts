import apiClient from './client';

export const syncCollection = () =>
  apiClient.post<{ standard_decks: number; alliance_decks: number }>('/collection/sync');

export const getCollection = (page = 0, type: 'standard' | 'alliance' | 'all' = 'all') =>
  apiClient.get('/collection', { params: { page, type } });
