import apiClient from './client';
import type { CollectionDeck, AllianceDeckEntry } from '../types';

export interface CollectionParams {
  type?: 'standard' | 'alliance' | 'all';
  page?: number;
  per_page?: number;
  sort?: string;
  sort_dir?: 'asc' | 'desc';
  search?: string;
}

interface CollectionResponse {
  standard?: CollectionDeck[];
  standard_total?: number;
  alliance?: AllianceDeckEntry[];
}

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

export const getCollection = (params: CollectionParams = {}) =>
  apiClient.get<CollectionResponse>('/collection', { params });
