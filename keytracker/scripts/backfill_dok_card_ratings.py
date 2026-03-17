"""
Backfill extra_card_info and syn_trait_value in the local DoK Postgres with current
ratings from the DoK public API (/public-api/v1/cards).

Usage (from project root):
    python keytracker/scripts/backfill_dok_card_ratings.py

Reads DOK_API_KEY from the tracker .env file.
Connects to the local DoK Postgres on port 5433 (docker-compose default).

Each card's extraCardInfo has two separate trait arrays:
  - "traits"    → characteristics the card HAS  → stored with trait_info_id = eci_id
  - "synergies" → what the card NEEDS/benefits from → stored with synergy_info_id = eci_id
"""

import os
import uuid
from datetime import datetime, timezone

import psycopg2
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DOK_CARDS_URL = "https://decksofkeyforge.com/public-api/v1/cards"
DOK_PG_DSN = "host=localhost port=5433 dbname=keyswap user=postgres password=postgres"
PUBLISHED_TS = datetime(2025, 3, 3, 22, 55, 0, tzinfo=timezone.utc)

# Version number to stamp on all inserted/updated records.
CURRENT_VERSION = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_api_key() -> str:
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    with open(env_path) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("DOK_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("DOK_API_KEY not found in .env")


def fetch_cards(api_key: str) -> list:
    print("Fetching current card ratings from DoK API…")
    resp = requests.get(DOK_CARDS_URL, headers={"Api-Key": api_key}, timeout=60)
    resp.raise_for_status()
    cards = resp.json()
    print(f"  Got {len(cards)} cards")
    return cards


def _pg_enum_array(values: list | None, cast: str) -> str | None:
    """Return a Postgres array literal string for an enum[] column, or None."""
    if not values:
        return None
    escaped = ",".join(v for v in values)
    return f"{{{escaped}}}"


def upsert_extra_card_info(cur, dok_card_id: int, eci: dict, now: datetime) -> str:
    """Deactivate old rows, then insert-or-update the extra_card_info row.

    Returns the eci UUID that was written.
    """
    # Deactivate any currently active rows for this card.
    cur.execute(
        "UPDATE extra_card_info SET active = false WHERE dok_card_id = %s AND active = true",
        (dok_card_id,),
    )

    eci_id = eci.get("id") or str(uuid.uuid4())
    cur.execute("SELECT id FROM extra_card_info WHERE id = %s", (eci_id,))
    exists = cur.fetchone() is not None

    params = (
        eci["expectedAmber"],
        eci.get("expectedAmberMax"),
        eci["amberControl"],
        eci.get("amberControlMax"),
        eci["creatureControl"],
        eci.get("creatureControlMax"),
        eci["artifactControl"],
        eci.get("artifactControlMax"),
        eci["efficiency"],
        eci.get("efficiencyMax"),
        eci["recursion"],
        eci.get("recursionMax"),
        eci["effectivePower"],
        eci.get("effectivePowerMax"),
        eci["disruption"],
        eci.get("disruptionMax"),
        eci["creatureProtection"],
        eci.get("creatureProtectionMax"),
        eci["other"],
        eci.get("otherMax"),
        eci["enhancementAmber"],
        eci["enhancementCapture"],
        eci["enhancementDraw"],
        eci["enhancementDamage"],
        eci["enhancementDiscard"],
        eci.get("baseSynPercent"),
        CURRENT_VERSION,
        PUBLISHED_TS,
        now,
    )

    if exists:
        cur.execute(
            """
            UPDATE extra_card_info SET
                expected_amber          = %s,
                expected_amber_max      = %s,
                amber_control           = %s,
                amber_control_max       = %s,
                creature_control        = %s,
                creature_control_max    = %s,
                artifact_control        = %s,
                artifact_control_max    = %s,
                efficiency              = %s,
                efficiency_max          = %s,
                recursion               = %s,
                recursion_max           = %s,
                effective_power         = %s,
                effective_power_max     = %s,
                disruption              = %s,
                disruption_max          = %s,
                creature_protection     = %s,
                creature_protection_max = %s,
                other                   = %s,
                other_max               = %s,
                enhancement_amber       = %s,
                enhancement_capture     = %s,
                enhancement_draw        = %s,
                enhancement_damage      = %s,
                enhancement_discard     = %s,
                base_syn_percent        = %s,
                version                 = %s,
                active                  = true,
                published               = %s,
                updated                 = %s
            WHERE id = %s
            """,
            params + (eci_id,),
        )
    else:
        cur.execute(
            """
            INSERT INTO extra_card_info (
                id, dok_card_id, card_name, card_name_url,
                expected_amber, expected_amber_max,
                amber_control, amber_control_max,
                creature_control, creature_control_max,
                artifact_control, artifact_control_max,
                efficiency, efficiency_max,
                recursion, recursion_max,
                effective_power, effective_power_max,
                disruption, disruption_max,
                creature_protection, creature_protection_max,
                other, other_max,
                enhancement_amber, enhancement_capture,
                enhancement_draw, enhancement_damage, enhancement_discard,
                base_syn_percent,
                version, active, published, created, updated
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s,
                %s, true, %s, %s, %s
            )
            """,
            (eci_id, dok_card_id, eci["cardName"], eci["cardNameUrl"]) + params + (now,),
        )

    return eci_id, exists


def _insert_trait_row(cur, row_id: str, trait_info_id, synergy_info_id, t: dict) -> None:
    """Insert or update a single syn_trait_value row."""
    card_types = _pg_enum_array(t.get("cardTypes"), "card_type")
    from_zones = _pg_enum_array(t.get("fromZones"), "play_zone")
    card_traits = t.get("cardTraits") or []

    cur.execute(
        """
        INSERT INTO syn_trait_value (
            id, trait_info_id, synergy_info_id,
            trait, rating, house, player,
            card_name, card_types_string, powers_string, card_traits_string,
            synergy_group, synergy_group_max,
            not_card_traits, primary_group,
            card_types, card_traits, from_zones
        ) VALUES (
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s,
            %s::card_type[], %s, %s::play_zone[]
        )
        ON CONFLICT (id) DO UPDATE SET
            trait_info_id      = EXCLUDED.trait_info_id,
            synergy_info_id    = EXCLUDED.synergy_info_id,
            trait              = EXCLUDED.trait,
            rating             = EXCLUDED.rating,
            house              = EXCLUDED.house,
            player             = EXCLUDED.player,
            card_name          = EXCLUDED.card_name,
            card_types_string  = EXCLUDED.card_types_string,
            powers_string      = EXCLUDED.powers_string,
            card_traits_string = EXCLUDED.card_traits_string,
            synergy_group      = EXCLUDED.synergy_group,
            synergy_group_max  = EXCLUDED.synergy_group_max,
            not_card_traits    = EXCLUDED.not_card_traits,
            primary_group      = EXCLUDED.primary_group,
            card_types         = EXCLUDED.card_types,
            card_traits        = EXCLUDED.card_traits,
            from_zones         = EXCLUDED.from_zones
        """,
        (
            row_id,
            trait_info_id,
            synergy_info_id,
            t.get("trait"),
            t["rating"],
            t.get("house"),
            t.get("player", "ANY"),
            t.get("cardName"),
            t.get("cardTypesString", ""),
            t.get("powersString", ""),
            t.get("cardTraitsString", ""),
            t.get("synergyGroup"),
            t.get("synergyGroupMax"),
            bool(t.get("notCardTraits", False)),
            bool(t.get("primaryGroup", False)),
            card_types,
            card_traits if card_traits else None,
            from_zones,
        ),
    )


def upsert_traits_and_synergies(cur, eci_id: str, traits: list, synergies: list) -> int:
    """Replace all syn_trait_value rows for this extra_card_info with fresh data.

    - traits    → items the card HAS  → stored with trait_info_id = eci_id
    - synergies → items the card NEEDS → stored with synergy_info_id = eci_id

    Returns the total number of rows written.
    """
    # Remove all stale rows for this eci (both as provider and as needer).
    cur.execute("DELETE FROM syn_trait_value WHERE trait_info_id = %s", (eci_id,))
    cur.execute("DELETE FROM syn_trait_value WHERE synergy_info_id = %s", (eci_id,))

    count = 0

    for t in traits:
        row_id = t.get("id") or str(uuid.uuid4())
        _insert_trait_row(cur, row_id, trait_info_id=eci_id, synergy_info_id=None, t=t)
        count += 1

    for s in synergies:
        row_id = s.get("id") or str(uuid.uuid4())
        _insert_trait_row(cur, row_id, trait_info_id=None, synergy_info_id=eci_id, t=s)
        count += 1

    return count


def _card_slug(card: dict) -> str:
    """Derive the card_title_url slug from an API card object.

    The API stores slugs in the nested expansion card's 'cardTitleUrl' field.
    Fall back to stripping the filename from the top-level image URL.
    """
    expansions = card.get("expansions") or []
    if expansions:
        slug = expansions[0]["card"].get("cardTitleUrl")
        if slug:
            return slug
    url = card.get("cardTitleUrl", "")
    return url.rstrip("/").split("/")[-1].replace(".png", "")


def backfill(cards: list) -> None:
    conn = psycopg2.connect(DOK_PG_DSN)
    conn.autocommit = False
    cur = conn.cursor()
    now = datetime.now(timezone.utc)

    # Build slug → local dok_card.id mapping (the DB dump may use different
    # numeric IDs than the API, so we match by slug, not by API id).
    cur.execute("SELECT id, card_title_url FROM dok_card")
    slug_to_local_id = {row[1]: row[0] for row in cur.fetchall()}

    eci_inserted = 0
    eci_updated = 0
    trait_rows = 0
    skipped_no_dok_card = 0
    skipped_no_eci = 0

    for card in cards:
        eci = card.get("extraCardInfo")
        if not eci:
            skipped_no_eci += 1
            continue

        slug = _card_slug(card)
        local_id = slug_to_local_id.get(slug)
        if local_id is None:
            skipped_no_dok_card += 1
            continue

        eci_id, existed = upsert_extra_card_info(cur, local_id, eci, now)
        if existed:
            eci_updated += 1
        else:
            eci_inserted += 1

        trait_rows += upsert_traits_and_synergies(
            cur, eci_id,
            traits=eci.get("traits") or [],
            synergies=eci.get("synergies") or [],
        )

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nDone.")
    print(f"  extra_card_info inserted:  {eci_inserted}")
    print(f"  extra_card_info updated:   {eci_updated}")
    print(f"  syn_trait_value rows:      {trait_rows}")
    print(f"  Skipped (no dok_card):     {skipped_no_dok_card}")
    print(f"  Skipped (no extraCardInfo): {skipped_no_eci}")


if __name__ == "__main__":
    api_key = load_api_key()
    cards = fetch_cards(api_key)
    backfill(cards)
