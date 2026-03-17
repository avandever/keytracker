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

export interface CollectionPod {
  house: string;
  sas_rating: number;
  deck_name: string;
  deck_kf_id: string;
  deck_mv_url: string;
  deck_dok_url: string;
  expansion: number;
  expansion_name: string;
}

export const getCollectionPods = (params: { house?: string; expansion?: number; sort_dir?: 'asc' | 'desc' } = {}) =>
  apiClient.get<{ pods: CollectionPod[] }>('/collection/pods', { params });
