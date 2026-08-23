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
};

export function deckSlotsForFormat(formatType: string): number {
  return DECK_SLOTS_BY_FORMAT[formatType] ?? 1;
}
