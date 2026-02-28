"""
Script to populate the Alliance Restricted List database tables.

Usage:
    python keytracker/scripts/add_alliance_restricted_card.py --version 2.5 --card-name "Reiteration"
    python keytracker/scripts/add_alliance_restricted_card.py --version 2.5 --card-name "Key Abduction" --max-copies 1
    python keytracker/scripts/add_alliance_restricted_card.py --version 2.5 --card-name "Strategic Feint"

This script reads DATABASE_URL from .env (or the environment) and connects directly via SQLAlchemy.
Run it from the project root.  A new version is created automatically if it does not yet exist.
"""

import argparse
import os
import sys


def load_dotenv(path=".env"):
    """Minimal .env loader — no third-party dependency required."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def main():
    parser = argparse.ArgumentParser(description="Add a card to the Alliance Restricted List")
    parser.add_argument("--version", type=float, required=True, help="Restricted list version (e.g. 2.5)")
    parser.add_argument("--card-name", required=True, help="Exact card title from PlatonicCard")
    parser.add_argument("--max-copies", type=int, default=None, help="Max copies allowed per alliance (omit = unlimited)")
    args = parser.parse_args()

    load_dotenv()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set in environment or .env", file=sys.stderr)
        sys.exit(1)

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Import models via raw SQL to avoid Flask app context dependency
        # Find or create the version
        row = session.execute(
            text("SELECT id FROM alliance_restricted_list_version WHERE version = :v"),
            {"v": args.version},
        ).fetchone()
        if row:
            version_id = row[0]
            print(f"Using existing restricted list version {args.version} (id={version_id})")
        else:
            result = session.execute(
                text("INSERT INTO alliance_restricted_list_version (version) VALUES (:v)"),
                {"v": args.version},
            )
            version_id = result.lastrowid
            session.commit()
            print(f"Created new restricted list version {args.version} (id={version_id})")

        # Look up the PlatonicCard
        card_row = session.execute(
            text("SELECT id FROM tracker_platonic_card WHERE card_title = :name LIMIT 1"),
            {"name": args.card_name},
        ).fetchone()
        if not card_row:
            print(f"ERROR: Card '{args.card_name}' not found in tracker_platonic_card", file=sys.stderr)
            sys.exit(1)
        platonic_card_id = card_row[0]

        # Check for duplicate
        existing = session.execute(
            text(
                "SELECT id FROM alliance_restricted_entry "
                "WHERE list_version_id = :vid AND platonic_card_id = :cid"
            ),
            {"vid": version_id, "cid": platonic_card_id},
        ).fetchone()
        if existing:
            print(f"Entry for '{args.card_name}' already exists in version {args.version} (entry id={existing[0]})")
            sys.exit(0)

        # Insert the entry
        session.execute(
            text(
                "INSERT INTO alliance_restricted_entry "
                "(list_version_id, platonic_card_id, max_copies_per_alliance) "
                "VALUES (:vid, :cid, :max)"
            ),
            {"vid": version_id, "cid": platonic_card_id, "max": args.max_copies},
        )
        session.commit()
        max_str = str(args.max_copies) if args.max_copies is not None else "unlimited"
        print(f"Added '{args.card_name}' to restricted list v{args.version} (max_copies={max_str})")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
