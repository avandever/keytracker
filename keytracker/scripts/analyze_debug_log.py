#!/usr/bin/env python3
"""
Analyze a keytracker extension debug log JSON (kt_debug_log_*.json from ~/kt_debug/).

Usage:
    python keytracker/scripts/analyze_debug_log.py ~/kt_debug/kt_debug_log_1773546767372.json
    python keytracker/scripts/analyze_debug_log.py ~/kt_debug/kt_debug_log_*.json --type SNAPSHOT_DEBUG
    python keytracker/scripts/analyze_debug_log.py ~/kt_debug/kt_debug_log_*.json --summary
"""

import argparse
import json
import sys
from collections import Counter


def load(path):
    with open(path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Analyze extension debug log JSON")
    parser.add_argument("path", help="Path to debug log JSON file")
    parser.add_argument("--type", "-t", help="Filter to entries of this type (e.g. SNAPSHOT_DEBUG)")
    parser.add_argument("--summary", action="store_true", help="Show count of each event type")
    parser.add_argument("--blocked", action="store_true", help="Show only guard-blocked entries")
    args = parser.parse_args()

    log = load(args.path)
    print(f"Total entries: {len(log)}")

    if args.summary:
        counts = Counter(e.get("type") for e in log)
        print("\nEvent type counts:")
        for t, n in counts.most_common():
            print(f"  {n:4d}  {t}")
        return

    entries = log
    if args.blocked:
        entries = [e for e in entries if e.get("guardBlocked")]
    if args.type:
        entries = [e for e in entries if e.get("type") == args.type]

    print(f"Showing {len(entries)} entries:\n")
    for e in entries:
        detail = e.get("detail", "")
        # Try to pretty-print JSON detail
        try:
            detail_obj = json.loads(detail)
            detail_str = json.dumps(detail_obj, indent=2)
        except (json.JSONDecodeError, TypeError):
            detail_str = detail
        blocked = " [BLOCKED]" if e.get("guardBlocked") else ""
        print(f"[{e.get('type')}{blocked}]")
        print(detail_str)
        print()


if __name__ == "__main__":
    main()
