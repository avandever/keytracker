# Match Formats

## Supported in leagues AND standalone matches
- `archon_standard` — Standard 1v1 Archon
- `triad` — 3 decks, best of 3, with strikes
- `sealed_archon` — Sealed pool, pick 1 deck
- `sealed_alliance` — Sealed pool, pick 3 pods to form an alliance deck
- `adaptive` — Best of 3: G1 own decks, G2 swapped, G3 (if 1-1) after asynchronous chain-bidding auction

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
