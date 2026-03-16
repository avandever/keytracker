import type { AuctionDetail } from '../types';

const API_BASE = '/api/v2/auctions';

export async function createAuction(): Promise<AuctionDetail> {
  const res = await fetch(API_BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listAuctions(): Promise<any[]> {
  const res = await fetch(API_BASE);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getAuction(id: number): Promise<AuctionDetail> {
  const res = await fetch(`${API_BASE}/${id}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function joinAuction(id: number, passphrase: string): Promise<AuctionDetail> {
  const res = await fetch(`${API_BASE}/${id}/join`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ passphrase }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function startAuction(id: number): Promise<AuctionDetail> {
  const res = await fetch(`${API_BASE}/${id}/start`, { method: 'POST' });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function submitAuctionDeck(
  id: number,
  data: { deck_url?: string; deck_id?: string }
): Promise<AuctionDetail> {
  const res = await fetch(`${API_BASE}/${id}/deck`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function pickAuctionDeck(
  id: number,
  auctionDeckId: number
): Promise<AuctionDetail> {
  const res = await fetch(`${API_BASE}/${id}/pick`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ auction_deck_id: auctionDeckId }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function placeBid(id: number, chains: number): Promise<AuctionDetail> {
  const res = await fetch(`${API_BASE}/${id}/bid`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chains }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function passBid(id: number): Promise<AuctionDetail> {
  const res = await fetch(`${API_BASE}/${id}/pass`, { method: 'POST' });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
