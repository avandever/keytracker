# Integration scripts

Each file here builds a league from nothing — sets, houses, decks, teams,
players, brackets — and then drives the real API through a Flask test client,
asserting on what comes back. They cover the parts of the league machinery
that are easy to break and expensive to get wrong in front of players:
playoff draws and advancement, sealed pools, deck reuse, bans, and who is
allowed to see or do what.

They are not pytest tests. Each is a standalone script whose module body runs
on import and calls `db.drop_all()`, so pytest is kept out of this directory
by `conftest.py`. The pytest suite is the directory above.

## Running them

The app container has to be up; everything else is handled.

```bash
tests/integration/run.sh                      # all of them, with a summary
tests/integration/run.sh test_publish_round.py   # just one, full output
```

The runner copies the **working tree's** `keytracker/` into the container and
puts it first on `sys.path`, so it tests what you have edited, not what is
deployed. The site keeps running its own code throughout.

Set `KEYTRACKER_CONTAINER` if the container is not named `keytracker`.

## The database

They run against `keytracker_playoff_scratch`, derived by `scratch_url.py`
from the container's own `DATABASE_URL` with the database name swapped. The
runner sets both `DATABASE_URL` and `TEST_DATABASE_URL` to it for the test
process, so a script that forgot to read the override cannot reach
production — which matters, because every one of them drops every table on
startup.

**A script added here must never be run against a database anyone cares
about.** If you write one, take the scratch URL from the environment the way
the others do and do not reach for `DATABASE_URL` yourself.

## Reading the output

Each script prints a `[PASS]`/`[FAIL]` line per assertion and ends with
`all checks passed` or `FAILED: [...]`, exiting non-zero on failure. The
container's background threads (deck collector, card refresher) print their
own debug lines and sometimes a traceback of their own into the same stream;
judge a run by its exit status and its final line, not by stray output.

## What is covered

| script | what it pins down |
| --- | --- |
| `test_assign_privacy.py` | a team's bracket assignments stay hidden until an admin publishes them |
| `test_bracket_roster.py` | a bracket week belongs to the one player in it, not the whole roster |
| `test_captain_unblock.py` | Triad decks are hidden before both start and visible after; a captain can make the strike their player owes, recorded as the player's |
| `test_carry_suggestions.py` | deck suggestions carry from one playoff round into the next, except in sealed |
| `test_collector_retry.py` | the deck enrichment worker survives an error without dying |
| `test_deck_reuse.py` | a deck played in a season week is still free for a playoff week, and vice versa |
| `test_double_bans.py` | Double Oubliette's two bans, one per allowed set |
| `test_early_advance.py` | a verified result advances the bracket at once; the next round opens on whoever has come through; a knocked-out team is not shown it and cannot submit |
| `test_four_decks.py` | Double Oubliette takes four decks, two per set |
| `test_late_alliance.py` | an alliance can still be recorded after the deadline, and is logged as late |
| `test_per_set_bans.py` | a ban names a house within one set, and eliminates only that set's decks |
| `test_placeholder_draw.py` | a bracket can be drawn with placeholders before every team has a player |
| `test_pod_restricted.py` | the alliance restricted list is enforced per pod |
| `test_pool_on_advance.py` | a sealed round deals a pool to a team when it wins in, not to every qualifier in advance |
| `test_publish_round.py` | a round will not publish while decks are missing, and will not unpublish once a game is in |
| `test_survival_reveal.py` | Sealed Survival shows the opponent's keeps once both have kept, which is what makes a game reportable |
| `test_team_pools.py` | a playoff sealed pool belongs to the team's slot, so whoever ends up in it plays it |
