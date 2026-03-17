"""
Insert dok_card and dok_card_expansion rows for cards that exist in the DoK
public API but are missing from the local Postgres dump.

Run this before backfill_dok_card_ratings.py so all cards have a dok_card row
and can receive AERC/synergy data.

Usage (from project root):
    python keytracker/scripts/backfill_dok_missing_cards.py

Reads DOK_API_KEY from the tracker .env file.
Connects to the local DoK Postgres on port 5433 (docker-compose default).
"""

import os
from datetime import datetime, timezone

import psycopg2
import requests

DOK_CARDS_URL = "https://decksofkeyforge.com/public-api/v1/cards"
DOK_PG_DSN = "host=localhost port=5433 dbname=keyswap user=postgres password=postgres"


def load_api_key() -> str:
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    with open(env_path) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("DOK_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("DOK_API_KEY not found in .env")


def fetch_cards(api_key: str) -> list:
    print("Fetching cards from DoK API…")
    resp = requests.get(DOK_CARDS_URL, headers={"Api-Key": api_key}, timeout=60)
    resp.raise_for_status()
    cards = resp.json()
    print(f"  Got {len(cards)} cards")
    return cards


def _pg_house_array(houses: list) -> str:
    """Return a Postgres house[] literal, e.g. '{Brobnar,Logos}'."""
    return "{" + ",".join(houses) + "}"


def _pg_text_array(values: list) -> str:
    """Return a Postgres text[] literal, escaping values with double-quotes."""
    escaped = ",".join(f'"{v}"' for v in values)
    return "{" + escaped + "}"


def run(cards: list) -> None:
    conn = psycopg2.connect(DOK_PG_DSN)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute("SELECT id, card_title_url FROM dok_card")
    rows = cur.fetchall()
    existing_card_ids = {row[0] for row in rows}
    # slug → canonical card_id (for dedup when API assigns multiple IDs to same card)
    slug_to_card_id = {row[1]: row[0] for row in rows}

    cur.execute("SELECT id FROM dok_card_expansion")
    existing_exp_ids = {row[0] for row in cur.fetchall()}

    cards_inserted = 0
    expansions_inserted = 0
    expansions_skipped = 0

    for card in cards:
        card_id = card["id"]
        expansions = card.get("expansions") or []

        # Use the slug from the first expansion's nested card object; fall back
        # to deriving it from the image URL.
        slug = None
        first_card_obj = expansions[0]["card"] if expansions else None
        if first_card_obj:
            slug = first_card_obj.get("cardTitleUrl")
        if not slug:
            url = card.get("cardTitleUrl", "")
            slug = url.rstrip("/").split("/")[-1].replace(".png", "")

        evil_twin = first_card_obj.get("evilTwin", False) if first_card_obj else False
        houses = card.get("houses") or []
        traits = card.get("traits") or []

        # If this slug already exists under a different ID, use the canonical ID.
        canonical_card_id = slug_to_card_id.get(slug, card_id)
        if canonical_card_id != card_id:
            card_id = canonical_card_id
        elif card_id not in existing_card_ids:
            cur.execute(
                """
                INSERT INTO dok_card (
                    id, card_title, card_title_url,
                    houses, card_type, amber, power, armor,
                    big, token, evil_twin, traits,
                    card_text, flavor_text
                ) VALUES (
                    %s, %s, %s,
                    %s::house[], %s, %s, %s, %s,
                    %s, %s, %s, %s::text[],
                    %s, %s
                )
                ON CONFLICT DO NOTHING
                """,
                (
                    card_id,
                    card["cardTitle"],
                    slug,
                    _pg_house_array(houses),
                    card.get("cardType", ""),
                    card.get("amber", 0),
                    card.get("power", 0),
                    card.get("armor", 0),
                    bool(card.get("big", False)),
                    bool(card.get("token", False)),
                    bool(evil_twin),
                    _pg_text_array(traits),
                    card.get("cardText"),
                    card.get("flavorText"),
                ),
            )
            existing_card_ids.add(card_id)
            slug_to_card_id[slug] = card_id
            cards_inserted += 1

        for exp in expansions:
            exp_id = exp["id"]
            if exp_id in existing_exp_ids:
                expansions_skipped += 1
                continue
            cur.execute(
                """
                INSERT INTO dok_card_expansion (
                    id, card_number, expansion, wins, losses, card_id, rarity
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (card_number, expansion) DO NOTHING
                """,
                (
                    exp_id,
                    exp["cardNumber"],
                    exp["expansion"],
                    exp.get("wins", 0),
                    exp.get("losses", 0),
                    card_id,
                    exp.get("rarity", "Common"),
                ),
            )
            existing_exp_ids.add(exp_id)
            expansions_inserted += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nDone.")
    print(f"  dok_card rows inserted:           {cards_inserted}")
    print(f"  dok_card_expansion rows inserted: {expansions_inserted}")
    print(f"  dok_card_expansion rows skipped:  {expansions_skipped}")


if __name__ == "__main__":
    api_key = load_api_key()
    cards = fetch_cards(api_key)
    run(cards)
