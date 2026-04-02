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
    "A best-of-three where game 1 is played with your own decks, game 2 with your opponent's deck, and game 3 (if needed) involves bidding chains for the right to choose which deck to play.",
  alliance:
    "Build a custom alliance deck from three houses — one from each of three different decks in your collection.",
  sas_ladder:
    "Players are arranged by SAS rung. Submit a deck within your assigned rung's SAS range to compete.",
  reversal:
    "Your opponent will play the deck you submit, and you'll play theirs. Choose accordingly!",
  oubliette:
    "Submit two decks and name a banned house. Decks that contain your banned house cannot be used by your opponent — and vice versa.",
  adaptive_short:
    "A single game where both players bid chains for the right to choose which deck they play. Higher bidder pays the chains cost and picks first.",
  exchange:
    "Each player secretly names one of their opponent's decks to borrow. You must win using both your own deck and your borrowed deck — but so must your opponent.",
  nordic_hexad:
    "Submit six decks. Each player bans one of their opponent's decks, then protects one of their own from being banned, then bans again — leaving four decks each for a four-game series.",
  moirai:
    "Submit three decks. Your opponent assigns one of your decks to each game type (archon, reversal, or adaptive short), and you do the same to theirs.",
  tertiate:
    "Submit one deck. Before each game, both players secretly pick a house to purge from their opponent's deck — that house cannot be used for that game. Players may choose the same or a different house each game.",
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
