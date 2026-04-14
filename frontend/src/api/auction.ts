import apiClient from './client';
import type { AuctionDetail } from '../types';

export async function createAuction(): Promise<AuctionDetail> {
  const { data } = await apiClient.post('/auctions');
  return data;
}

export async function listAuctions(): Promise<AuctionDetail[]> {
  const { data } = await apiClient.get('/auctions');
  return data;
}

export async function getAuction(id: number): Promise<AuctionDetail> {
  const { data } = await apiClient.get(`/auctions/${id}`);
  return data;
}

export async function joinAuction(id: number, passphrase: string): Promise<AuctionDetail> {
  const { data } = await apiClient.post(`/auctions/${id}/join`, { passphrase });
  return data;
}

export async function startAuction(id: number): Promise<AuctionDetail> {
  const { data } = await apiClient.post(`/auctions/${id}/start`);
  return data;
}

export async function submitAuctionDeck(
  id: number,
  payload: { deck_url?: string; deck_id?: string }
): Promise<AuctionDetail> {
  const { data } = await apiClient.post(`/auctions/${id}/deck`, payload);
  return data;
}

export async function pickAuctionDeck(
  id: number,
  auctionDeckId: number
): Promise<AuctionDetail> {
  const { data } = await apiClient.post(`/auctions/${id}/pick`, { auction_deck_id: auctionDeckId });
  return data;
}

export async function placeBid(id: number, chains: number): Promise<AuctionDetail> {
  const { data } = await apiClient.post(`/auctions/${id}/bid`, { chains });
  return data;
}

export async function passBid(id: number): Promise<AuctionDetail> {
  const { data } = await apiClient.post(`/auctions/${id}/pass`);
  return data;
}
