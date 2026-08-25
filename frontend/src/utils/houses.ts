/**
 * The playable KeyForge houses, in the spelling the tracker stores.
 *
 * Excludes Prophecy and Archon Power, which are card pools rather than houses
 * a deck is built from.
 */
export const HOUSES = [
  'Brobnar',
  'Dis',
  'Ekwidon',
  'Elders',
  'Geistoid',
  'Ironyx Rebels',
  'Logos',
  'Mars',
  'Ouboros',
  'Redemption',
  'Sanctum',
  'Saurian',
  'Shadows',
  'Skyborn',
  'Star Alliance',
  'Unfathomable',
  'Untamed',
] as const;

/** Houses legal to ban in Oubliette: any house not in the player's own decks. */
export function housesNotInDecks(deckHouseLists: (string[] | null | undefined)[]): string[] {
  const own = new Set<string>();
  for (const houses of deckHouseLists) {
    for (const h of houses || []) own.add(h);
  }
  return HOUSES.filter((h) => !own.has(h));
}
