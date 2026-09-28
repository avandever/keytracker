/**
 * Display names for the week formats.
 *
 * Mirrors WeekFormat in keytracker/schema.py. Several pages carry their own
 * partial copies of this; new code should use this one.
 */
export const WEEK_FORMAT_LABELS: Record<string, string> = {
  archon_standard: 'Archon Standard',
  triad: 'Triad',
  triad_short: 'Triad Short',
  sealed_archon: 'Sealed Archon',
  sealed_alliance: 'Sealed Alliance',
  team_sealed: 'Team Sealed',
  team_sealed_alliance: 'Team Sealed Alliance',
  alliance: 'Alliance',
  thief: 'Thief',
  adaptive: 'Adaptive',
  adaptive_short: 'Adaptive Short',
  sas_ladder: 'SAS Ladder',
  reversal: 'Reversal',
  oubliette: 'Oubliette',
  exchange: 'Exchange',
  nordic_hexad: 'Nordic Hexad',
  moirai: 'Moirai',
  tertiate: 'Tertiate',
};

export function weekFormatLabel(formatType: string): string {
  return WEEK_FORMAT_LABELS[formatType] || formatType;
}
