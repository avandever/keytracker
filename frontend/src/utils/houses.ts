/**
 * Houses the player may ban in Oubliette, with the illegal ones marked.
 *
 * The candidates come from the week's allowed sets (the server derives them
 * from card data), so a DM-only week offers DM's seven houses rather than
 * every house that has ever been printed. A house appearing in the player's
 * own decks cannot be banned, but is still listed and disabled — hiding it
 * makes a short list look broken rather than explained.
 */
export interface BanOption {
  house: string;
  disabled: boolean;
  reason?: string;
}

export function banOptions(
  allowedHouses: string[] | undefined,
  ownDeckHouseLists: (string[] | null | undefined)[],
): BanOption[] {
  const own = new Set<string>();
  for (const houses of ownDeckHouseLists) {
    for (const h of houses || []) own.add(h);
  }
  return (allowedHouses || []).map((house) => ({
    house,
    disabled: own.has(house),
    reason: own.has(house) ? 'in one of your decks' : undefined,
  }));
}
