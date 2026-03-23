export const FORMAT_DESCRIPTIONS: Record<string, string> = {
  archon_standard:
    "Bring the best deck from your collection (or your team's) to the Crucible, and duke it out for glory!",
  triad:
    "Submit three decks. Your opponent will assign one to each game of a best-of-three — and you'll do the same to them.",
  triad_short:
    "Submit two decks. Your opponent chooses one for you to play in game 1, then you freely choose for game 2.",
  sealed_archon:
    "A sealed pool of decks will be generated for you. Pick your best one and take it to battle.",
  sealed_alliance:
    "A sealed pool of decks will be generated for you. Build an alliance deck from the available houses.",
  team_sealed:
    "Your team shares a sealed pool of decks — each player picks one to represent the team.",
  team_sealed_alliance:
    "Your team shares a sealed pool of decks — each player builds an alliance deck from the available houses.",
  thief:
    "Your opponent curates a deck for you, and you do the same for them. You may attempt to steal one of the decks they curated — but choose wisely!",
  adaptive:
    "Submit a deck from your collection; your opponent reveals theirs before you make your final pick.",
  alliance:
    "Build a custom alliance deck from three houses — one from each of three different decks in your collection.",
  sas_ladder:
    "Players are arranged by SAS rung. Submit a deck within your assigned rung's SAS range to compete.",
  reversal:
    "Your opponent will play the deck you submit, and you'll play theirs. Choose accordingly!",
  oubliette:
    "Submit two decks face-down. After your opponent locks in their hidden choice, reveal and pick which one you'll play.",
  adaptive_short:
    "Submit two decks. Your opponent assigns one to game 1; you freely choose which to play in game 2.",
  exchange:
    "Submit two decks — one will go to your opponent to play, and one stays with you.",
  nordic_hexad:
    "Submit six decks for a six-game marathon match. May the best collection win!",
  moirai:
    "Submit three decks. You assign one of your opponent's decks to each game, and they assign one of yours — the fates decide!",
  tertiate:
    "Submit three decks. Your opponent assigns one to each game of a three-game match.",
};

export function getWeekDescription(
  formatType: string,
  customDescription: string | null | undefined,
  hideStandard: boolean | null | undefined,
): string | null {
  const standard = hideStandard ? null : (FORMAT_DESCRIPTIONS[formatType] ?? null);
  const custom = customDescription || null;
  if (custom && standard) return `${standard}\n\n${custom}`;
  return custom ?? standard;
}
