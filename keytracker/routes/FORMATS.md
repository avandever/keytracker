# Match Formats

## Supported in leagues AND standalone matches
- `archon_standard` — Standard 1v1 Archon
- `triad` — 3 decks, best of 3, with strikes
- `sealed_archon` — Sealed pool, pick 1 deck
- `sealed_alliance` — Sealed pool, pick 3 pods to form an alliance deck
- `adaptive` — Best of 3: G1 own decks, G2 swapped, G3 (if 1-1) after asynchronous chain-bidding auction
- `reversal` — Each player brings 1 deck they believe is hard to win with; opponents swap and play BO1
- `oubliette` — 2 decks per player; each player secretly bans a house (not in their own decks); decks containing either banned house are eliminated; BO1 from remaining eligible decks; forfeit if all decks eliminated
- `adaptive_short` — 2 decks per player; both players simultaneously and secretly choose 1 deck from the combined 4-deck pool; reveal: if different decks chosen each plays their choice (BO1); if same deck chosen, chain-bid auction to determine who plays it with how many chains (BO1)
- `exchange` — 2 decks per player; each player secretly borrows one of the opponent's decks (reveal simultaneously); each player's exchange pool = own non-borrowed deck + borrowed deck; BO3; win condition: win at least 1 game with EACH of your 2 exchange decks
- `nordic_hexad` — 6 decks per player; 3 sequential hidden-reveal phases: (1) each player bans 1 opponent deck, (2) each player protects 1 of their own decks, (3) each player bans another opponent deck (protected deck is immune); 4 decks per player remain; BO3 where each game must use a deck not previously played
- `moirai` — 3 decks per player; each player secretly assigns all 3 of the opponent's decks to game slots 1/2/3 (simultaneous reveal); G1=Archon (P1 plays what P2 assigned; P2 plays what P1 assigned), G2=Reversal (each plays the deck they themselves assigned for G2), G3=Adaptive Short (pool = the 2 G3-assigned decks; simultaneous choice with chain-bid tiebreaker); BO3

## NOT supported in standalone matches
- `thief` — Team-based deck-stealing mechanics; incompatible with 1v1 standalone play

## When adding a new format
1. Add to `WeekFormat` enum in `keytracker/schema.py`
2. Implement in `keytracker/routes/leagues.py`
3. Extract business logic to `keytracker/match_helpers.py`
4. Add to `keytracker/routes/standalone.py` (unless team-based, like Thief)
5. Update this file

## Shared business logic
All format-agnostic validation (deck constraints, sealed pool generation, alliance validation,
strike validation, game reporting) lives in `keytracker/match_helpers.py` and is called
from both `leagues.py` and `standalone.py`.
