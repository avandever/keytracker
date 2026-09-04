"""Replay the ABR 12 fantasy season through keytracker.fantasy and check the
result against jtrussell's published standings.

This is the acceptance test for the scoring engine: the rules live in a Google
Form, so the only real proof they are implemented correctly is reproducing a
season that was scored by hand.

Usage:
    python keytracker/scripts/validate_fantasy_abr12.py <dir-with-csv-exports>

Expects these files in that directory:
    ABR 12 - Fantasy League - Player Costs.csv
    ABR 12 - Fantasy League - All Results.csv
    ABR 12 - Fantasy League - Standings.csv

Note the scarcity bonus is NOT exercised here: it was never applied in ABR 12,
and we do not have the list of which players carried a star. Every roster entry
is replayed with is_new=False, which is what makes the totals reconcile.
"""

import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from keytracker.fantasy import (  # noqa: E402
    RosterEntry,
    ScoringConfig,
    rank_teams,
    score_teams,
)


def load(directory):
    costs = {}
    with open(os.path.join(directory, "ABR 12 - Fantasy League - Player Costs.csv")) as f:
        for row in csv.reader(f):
            if len(row) >= 2 and row[0].strip():
                costs[row[0].strip()] = int(row[1])

    # The results sheet is raw form submissions and contains duplicates -- 290
    # rows for 279 real outcomes. A player wins at most one match per round, so
    # collapsing to a set per round is both the dedupe and the model.
    winners_by_week = defaultdict(set)
    raw = 0
    with open(os.path.join(directory, "ABR 12 - Fantasy League - All Results.csv")) as f:
        for row in csv.reader(f):
            if len(row) < 5:
                continue
            winner, rnd = row[1].strip(), row[2].strip()
            if winner and rnd.startswith("Round"):
                raw += 1
                winners_by_week[rnd].add(winner)

    with open(os.path.join(directory, "ABR 12 - Fantasy League - Standings.csv")) as f:
        rows = list(csv.reader(f))
    head = {name: i for i, name in enumerate(rows[0])}
    player_cols = [head["Captain"]] + [head[f"Column {i}"] for i in range(1, 8)]

    rosters, expected = {}, {}
    for row in rows[1:]:
        if not row or not row[head["Team Name"]]:
            continue
        team = row[head["Team Name"]]
        captain = row[head["Captain"]].strip()
        entries = []
        for idx in player_cols:
            name = row[idx].strip()
            if not name:
                continue
            entries.append(
                RosterEntry(
                    player=name,
                    cost=costs.get(name, 0),
                    is_captain=(idx == head["Captain"] and name == captain),
                )
            )
        rosters[team] = entries
        expected[team] = int(row[head["Total Points"]])

    return rosters, expected, winners_by_week, raw


def main():
    directory = sys.argv[1] if len(sys.argv) > 1 else "."
    rosters, expected, winners_by_week, raw = load(directory)
    weeks = sorted(winners_by_week, key=lambda r: int(r.split()[1]))

    print(f"result rows {raw} -> {sum(len(v) for v in winners_by_week.values())} unique")
    print(f"weeks: {len(weeks)}   teams: {len(rosters)}")

    scores = score_teams(ScoringConfig(), rosters, weeks, winners_by_week)

    failures = 0
    print(f"\n{'#':>2} {'team':34} {'calc':>5} {'sheet':>5}  detail")
    for rank, (team, score) in enumerate(rank_teams(scores), 1):
        ok = score.total == expected[team]
        failures += 0 if ok else 1
        detail = (
            f"wins={score.match_wins} weekly={score.weekly_bonus} "
            f"capt={score.captain_bonus} cost={score.roster_cost}"
        )
        mark = "" if ok else "   <-- MISMATCH"
        print(f"{rank:2} {team[:34]:34} {score.total:5} {expected[team]:5}  {detail}{mark}")

    print()
    if failures:
        print(f"FAIL: {failures} of {len(rosters)} teams do not match")
        return 1
    print(f"PASS: all {len(rosters)} teams reproduce the published standings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
