# League Format Rules Reference

This document describes the league formats supported by Bear Tracks.

## Overview

A league consists of multiple **weeks**, each with a configurable format. Teams are matched up round-robin across weeks. Within each team matchup, individual players are paired based on strength (random for week 1).

## Week Lifecycle

1. **SETUP** — Admin creates week, sets format and constraints
2. **DECK_SELECTION** — Admin advances week; players/captains enter deck choices
3. **PAIRING** — Admin triggers pairing generation. Blocked unless previous week is COMPLETED and all deck selections are entered. Admin can view and manually adjust pairings.
4. **PUBLISHED** — Admin publishes pairings. Blocked unless all deck selections are entered. Deck choices become locked. Players can see matchups and start matches.
5. **COMPLETED** — All matches in the week are finished. Unlocks pairing for next week.

## Formats

### Archon Standard

- Each player brings **1 deck**
- Optional constraints: allowed sets, max SAS
- Best-of-N games (odd number)
- Players play all games with their selected deck

### Triad

- Each player brings **3 decks**
- Optional constraints: combined max SAS, set diversity (no two decks share an expansion), house diversity (no two decks share any house)
- After both players start their match, each **strikes** one of the opponent's decks
- Remaining 2 decks per player are used in games
- A deck that wins a game cannot be used again
- If the same player wins games 1 and 2, no game 3 is played
- Game reporting requires specifying which deck each player used

### Sealed Archon

- Admin generates sealed pools: random decks from allowed sets assigned to each player
- Each player selects **1 deck** from their assigned pool
- Plays like Archon Standard from there
- `decks_per_player` configures pool size

## Team Pairing: Round-Robin

Teams are paired using the circle method round-robin algorithm across all weeks. Each team plays every other team exactly once (for leagues with N teams, there are N-1 weeks of team matchups).

## Player Pairing: Strength-Based

- **Week 1**: Random player pairings within each team matchup
- **Week 2+**: Players are ranked by strength within their team
  - Base strength = number of match wins
  - Strength of schedule bonus = sum of (opponent_strength × 0.01) for each past opponent
  - Players sorted by strength (ties randomized), paired by position
- Admin can override any auto-generated player pairing

## Match Flow

1. Both players see their matchup after pairings are published
2. Each player clicks "Start Match" to indicate readiness
3. Once both have started, game reporting is unlocked
4. Players report game results (winner, keys forged by each player, time/concede flags)
5. Games are played sequentially up to best-of-N
6. Match winner is determined by majority of games won
