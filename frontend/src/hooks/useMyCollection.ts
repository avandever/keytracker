import { useState, useEffect } from 'react';
import { getCollection } from '../api/collection';
import type { CollectionDeck } from '../types';

let cachedDecks: CollectionDeck[] | null = null;
let cachePromise: Promise<CollectionDeck[]> | null = null;

async function fetchAllCollection(): Promise<CollectionDeck[]> {
  if (cachedDecks) return cachedDecks;
  if (cachePromise) return cachePromise;
  cachePromise = (async () => {
    const res = await getCollection({ type: 'standard', per_page: 2000, page: 0, sort: 'name' });
    const decks = res.data.standard ?? [];
    cachedDecks = decks;
    return decks;
  })();
  return cachePromise;
}

export function invalidateCollectionCache() {
  cachedDecks = null;
  cachePromise = null;
}

export default function useMyCollection() {
  const [decks, setDecks] = useState<CollectionDeck[]>(cachedDecks ?? []);
  const [loading, setLoading] = useState(cachedDecks === null);

  useEffect(() => {
    if (cachedDecks) {
      setDecks(cachedDecks);
      setLoading(false);
      return;
    }
    let cancelled = false;
    fetchAllCollection().then((d) => {
      if (!cancelled) {
        setDecks(d);
        setLoading(false);
      }
    }).catch(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, []);

  return { decks, loading, hasCollection: decks.length > 0 };
}
