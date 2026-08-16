"""Give Evil Twin printings their own PlatonicCard.

An Evil Twin is a substantively different card, but Master Vault reports it
under the same card_title as its base card, so the tracker attached both to
one PlatonicCard row and whichever printing was ingested last overwrote the
other's text and stats.

The v2 collector already renames new evil twins to "Evil <Title>", but that
only fires when the printing is new, so existing rows were never split.

This re-points those printings (and the deck cards using them) at the
"Evil <Title>" card, creating it when missing, and refreshes the twin's own
stats and text from production DoK.

Set ET_APPLY=1 to write; otherwise it reports what it would do.
"""
import os

import requests
from flask import Flask
from sqlalchemy import func, text

from keytracker.schema import (
    db, PlatonicCard, PlatonicCardInSet, CardInDeck,
)

EVIL_TWIN_RARITY_ID = 8
DOK_SUFFIX = " – Evil Twin"
APPLY = os.environ.get("ET_APPLY") == "1"

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
db.init_app(app)

prod_cards = requests.get(
    "https://decksofkeyforge.com/public-api/v1/cards",
    headers={"Api-Key": os.environ["DOK_API_KEY"]},
    timeout=300,
).json()
prod_by_name = {c["cardTitle"]: c for c in prod_cards}
print(f"production cards: {len(prod_cards)}  "
      f"(evil twins: {sum(1 for n in prod_by_name if DOK_SUFFIX in n)})")
print(f"mode: {'APPLY' if APPLY else 'DRY RUN'}\n")

with app.app_context():
    printings = PlatonicCardInSet.query.filter_by(
        kf_rarity_id=EVIL_TWIN_RARITY_ID
    ).all()

    to_move = []
    already = 0
    for p in printings:
        title = p.card_title or ""
        if title.startswith("Evil "):
            already += 1
            continue
        to_move.append(p)

    print(f"evil twin printings: {len(printings)}  "
          f"already split: {already}  to re-point: {len(to_move)}")

    if APPLY:
        # Targeted rollback data: the mappings this migration overwrites.
        db.session.execute(text(
            "CREATE TABLE IF NOT EXISTS et_migrate_backup_pcis "
            "(id INT PRIMARY KEY, card_id INT)"
        ))
        db.session.execute(text(
            "CREATE TABLE IF NOT EXISTS et_migrate_backup_cid "
            "(id INT PRIMARY KEY, platonic_card_id INT)"
        ))
        db.session.commit()

    created = repointed = cards_updated = stats_fixed = 0

    for p in to_move:
        base_title = p.card_title
        evil_title = "Evil " + base_title
        evil_card = PlatonicCard.query.filter_by(card_title=evil_title).first()

        if evil_card is None:
            created += 1
            if APPLY:
                base = p.card
                evil_card = PlatonicCard(
                    card_title=evil_title,
                    kf_card_type_id=base.kf_card_type_id,
                    front_image=p.front_image or base.front_image,
                    card_text=base.card_text,
                    amber=base.amber,
                    power=base.power,
                    armor=base.armor,
                    flavor_text=base.flavor_text,
                    kf_house_id=base.kf_house_id,
                    is_non_deck=base.is_non_deck,
                )
                db.session.add(evil_card)
                db.session.flush()

        if not APPLY:
            repointed += 1
            continue

        affected = CardInDeck.query.filter_by(card_in_set_id=p.id).all()
        db.session.execute(
            text("INSERT IGNORE INTO et_migrate_backup_pcis (id, card_id) "
                 "VALUES (:i, :c)"),
            {"i": p.id, "c": p.card_id},
        )
        for cid in affected:
            db.session.execute(
                text("INSERT IGNORE INTO et_migrate_backup_cid "
                     "(id, platonic_card_id) VALUES (:i, :c)"),
                {"i": cid.id, "c": cid.platonic_card_id},
            )
            cid.platonic_card_id = evil_card.id
            cards_updated += 1

        p.card_id = evil_card.id
        repointed += 1
        db.session.commit()

    # Refresh every twin's own stats/text from production.
    for evil_card in PlatonicCard.query.filter(
        PlatonicCard.card_title.like("Evil %")
    ).all():
        base_title = evil_card.card_title[len("Evil "):]
        prod = prod_by_name.get(base_title + DOK_SUFFIX)
        if prod is None:
            continue
        changes = {}
        for field, key in (("amber", "amber"), ("power", "power"),
                           ("armor", "armor"), ("card_text", "cardText")):
            new = prod.get(key)
            if new is not None and getattr(evil_card, field) != new:
                changes[field] = new
        if changes:
            stats_fixed += 1
            if APPLY:
                for field, value in changes.items():
                    setattr(evil_card, field, value)
    if APPLY:
        db.session.commit()

    print(f"\ncards created:        {created}")
    print(f"printings re-pointed: {repointed}")
    print(f"card_in_deck updated: {cards_updated}")
    print(f"twins with corrected stats/text: {stats_fixed}")
    if not APPLY:
        print("\n(dry run - nothing written; set ET_APPLY=1 to apply)")
