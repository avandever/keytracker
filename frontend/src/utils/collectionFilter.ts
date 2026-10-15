import type { CollectionDeck } from '../types';

interface WeekConstraints {
  allowed_sets?: number[] | null;
  max_sas?: number | null;
  sas_floor?: number | null;
  /**
   * Raw aember -- "pips" -- still available to spend, on a week that caps the
   * team total. Null when the week does not cap it.
   */
  max_raw_amber?: number | null;
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
    // A deck DoK has no data for is kept rather than dropped: the cap check on
    // submission skips those too, so there is nothing to judge it on and
    // hiding it would lose a deck that may well be legal.
    if (constraints.max_raw_amber != null && d.raw_amber != null) {
      if (d.raw_amber > constraints.max_raw_amber) return false;
    }
    return true;
  });
}

/**
 * What a deck costs against a pip cap, as a label suffix.
 *
 * Empty on a week with no cap, where the number would be noise, and on a deck
 * DoK cannot price, where there is no number to give.
 */
export function pipSuffix(
  deck: { raw_amber?: number | null },
  capped: boolean,
): string {
  if (!capped || deck.raw_amber == null) return '';
  return ` · ${deck.raw_amber} pip${deck.raw_amber === 1 ? '' : 's'}`;
}
