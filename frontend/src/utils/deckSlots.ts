/**
 * How many decks a week format expects each player to submit.
 *
 * Mirrors the slot limits enforced by submit_deck_selection in
 * keytracker/routes/leagues.py, which is the source of truth. Keep the two
 * in step when adding a format.
 */
export const DECK_SLOTS_BY_FORMAT: Record<string, number> = {
  triad: 3,
  triad_short: 3,
  moirai: 3,
  oubliette: 2,
  adaptive_short: 2,
  exchange: 2,
  nordic_hexad: 6,
  sealed_survival: 2,
  double_oubliette: 4,
};

/**
 * Which set a slot takes, for a format that splits its slots between sets.
 *
 * Double Oubliette plays two sets side by side: slots 1 and 2 are the first
 * set, 3 and 4 the second. Null for every other format, which does not care
 * which set a slot holds.
 */
export function slotSetNumber(
  formatType: string,
  slotNumber: number,
  allowedSets: number[] | null | undefined,
): number | null {
  if (formatType !== 'double_oubliette') return null;
  const sets = allowedSets || [];
  if (sets.length !== 2) return null;
  return slotNumber <= 2 ? sets[0] : sets[1];
}

/**
 * Formats whose deck is an alliance: three pods from three decks.
 *
 * They file no deck selections at all, so anything counting those alone reads
 * a finished alliance as nothing submitted.
 */
export const ALLIANCE_FORMATS = ['alliance', 'sealed_alliance', 'team_sealed_alliance'];

export function deckSlotsForFormat(formatType: string): number {
  return DECK_SLOTS_BY_FORMAT[formatType] ?? 1;
}
