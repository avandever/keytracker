/**
 * The formats dealt a sealed pool, and how many decks a player keeps from it.
 *
 * One list, in one place, because the copies kept drifting: the playoff pool
 * panel could not offer a Sealed Survival week its Generate button, and My
 * Team neither fetched the pool nor showed it once it had been dealt. A
 * format missing from a copy fails silently -- the screen simply does not
 * offer the thing, with nothing to say it should have.
 *
 * Team Sealed and Team Sealed Alliance are deliberately absent: those share
 * one pool across a roster and have their own screens for it.
 */
export const POOL_FORMATS: Record<string, number> = {
  sealed_archon: 1,
  sealed_alliance: 3,
  sealed_survival: 2,
};

/** The same formats as a list, for `includes` checks. */
export const POOL_FORMAT_TYPES = Object.keys(POOL_FORMATS);
