import type { CollectionDeck } from '../types';

interface WeekConstraints {
  allowed_sets?: number[] | null;
  max_sas?: number | null;
  sas_floor?: number | null;
}

export function filterCollectionForConstraints(
  decks: CollectionDeck[],
  constraints: WeekConstraints,
): CollectionDeck[] {
  return decks.filter((d) => {
    if (constraints.allowed_sets && constraints.allowed_sets.length > 0) {
      if (!constraints.allowed_sets.includes(d.expansion)) return false;
    }
    if (constraints.max_sas != null && d.sas_rating != null) {
      if (d.sas_rating > constraints.max_sas) return false;
    }
    if (constraints.sas_floor != null && d.sas_rating != null) {
      if (d.sas_rating < constraints.sas_floor) return false;
    }
    return true;
  });
}
