#!/usr/bin/env python3
"""
Analyze a keytracker extension session JSON file (kt_*.json from ~/kt_debug/).

Usage:
    python keytracker/scripts/analyze_session.py ~/kt_debug/kt_3193cf3c_2026-03-15.json
    python keytracker/scripts/analyze_session.py ~/kt_debug/kt_3193cf3c_2026-03-15.json --snapshots
    python keytracker/scripts/analyze_session.py ~/kt_debug/kt_3193cf3c_2026-03-15.json --snap 51
    python keytracker/scripts/analyze_session.py ~/kt_debug/kt_3193cf3c_2026-03-15.json --survey
"""

import argparse
import json
import sys
from collections import Counter


def load(path):
    with open(path) as f:
        return json.load(f)


def survey_snaps(snaps):
    """Show how often each player field / cardPile key appears across all snapshots."""
    player_names = set()
    cp_key_combos = Counter()
    field_counts = Counter()
    pile_counts = Counter()

    for snap in snaps:
        players = snap.get("players", {})
        for pname, pdata in players.items():
            if not isinstance(pdata, dict):
                continue
            player_names.add(pname)
            top_keys = tuple(sorted(pdata.keys()))
            field_counts[top_keys] += 1
            cp = pdata.get("cardPiles", {})
            if cp:
                combo = tuple(sorted(cp.keys()))
                cp_key_combos[combo] += 1
                for k in combo:
                    pile_counts[k] += 1

    print(f"Total snapshots: {len(snaps)}")
    print(f"Players seen: {sorted(player_names)}")
    print()
    print("Top-level player key combos:")
    for keys, count in field_counts.most_common():
        print(f"  {count:3d}x  {keys}")
    print()
    print("cardPiles key combos:")
    for keys, count in cp_key_combos.most_common():
        print(f"  {count:3d}x  {keys}")
    print()
    print("Individual pile presence:")
    for pile, count in pile_counts.most_common():
        print(f"  {pile}: {count} snaps")


def show_snap(snaps, index):
    """Print full player data for a specific snapshot index."""
    if index >= len(snaps):
        print(f"Index {index} out of range (0-{len(snaps)-1})")
        sys.exit(1)
    snap = snaps[index]
    players = snap.get("players", {})
    print(f"Snapshot {index}:")
    print(f"  Top-level keys: {list(snap.keys())}")
    for pname, pdata in players.items():
        print(f"\n  Player: {pname}")
        if not isinstance(pdata, dict):
            print(f"    (not a dict: {type(pdata).__name__})")
            continue
        for k, v in pdata.items():
            if k == "clock":
                continue
            if isinstance(v, dict):
                print(f"    {k}: dict keys={list(v.keys())[:10]}")
                if k == "cardPiles":
                    for ck, cv in v.items():
                        if isinstance(cv, dict):
                            real_keys = [x for x in cv if not x.startswith("_")]
                            print(f"      {ck}: sparse dict, {len(real_keys)} cards")
                        elif isinstance(cv, list):
                            print(f"      {ck}: list, {len(cv)} items")
            elif isinstance(v, list):
                print(f"    {k}: {v}")
            else:
                print(f"    {k}: {v!r}")


def show_snapshots_summary(snaps):
    """Show per-snapshot summary of what's captured."""
    print(f"{'idx':>4}  {'player':<12}  {'cp_keys':<40}  {'amber':>5}  {'deck':>4}  {'hand':>4}  {'board':>5}  {'discard':>7}")
    print("-" * 100)
    for i, snap in enumerate(snaps):
        players = snap.get("players", {})
        for pname, pdata in players.items():
            if not isinstance(pdata, dict):
                continue
            cp = pdata.get("cardPiles") or {}
            if not cp:
                continue
            stats = pdata.get("stats") or {}
            amber_arr = stats.get("amber")
            amber = amber_arr[1] if isinstance(amber_arr, list) and len(amber_arr) > 1 else "?"

            def pile_len(key):
                v = cp.get(key, {})
                if not isinstance(v, dict):
                    return 0
                return len([k for k in v if not k.startswith("_")])

            print(
                f"{i:>4}  {pname:<12}  {str(sorted(cp.keys())):<40}  "
                f"{str(amber):>5}  {pile_len('deck'):>4}  {pile_len('hand'):>4}  "
                f"{pile_len('cardsInPlay'):>5}  {pile_len('discard'):>7}"
            )


def main():
    parser = argparse.ArgumentParser(description="Analyze extension session JSON")
    parser.add_argument("path", help="Path to session JSON file")
    parser.add_argument("--survey", action="store_true", help="Survey all snapshot field availability")
    parser.add_argument("--snapshots", action="store_true", help="Show per-snapshot summary table")
    parser.add_argument("--snap", type=int, metavar="N", help="Show full detail for snapshot N")
    args = parser.parse_args()

    data = load(args.path)

    # Top-level session info
    if not args.survey and not args.snapshots and args.snap is None:
        print(f"Session ID:    {data.get('sessionId')}")
        print(f"Game ID:       {data.get('crucibleGameId')}")
        print(f"Players:       {data.get('player1')} vs {data.get('player2')}")
        print(f"Winner:        {data.get('winner')}")
        print(f"Snapshots:     {len(data.get('gamestateSnapshots', []))}")
        print(f"Events:        {len(data.get('events', []))}")
        print(f"Turn timing:   {len(data.get('turnTiming', []))}")
        print(f"Key events:    {len(data.get('keyEvents', []))}")
        print(f"Turn snapshots:{len(data.get('turnSnapshots', []))}")
        print()
        print("Use --survey, --snapshots, or --snap N for detailed analysis.")
        return

    snaps = data.get("gamestateSnapshots", [])

    if args.survey:
        survey_snaps(snaps)
    elif args.snapshots:
        show_snapshots_summary(snaps)
    elif args.snap is not None:
        show_snap(snaps, args.snap)


if __name__ == "__main__":
    main()
