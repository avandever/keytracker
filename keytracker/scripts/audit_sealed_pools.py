"""Audit sealed pool decks for a league: card counts, pod stats, DoK data."""
import os
from collections import Counter

from flask import Flask
from sqlalchemy import func

from keytracker.schema import (
    db, League, LeagueWeek, SealedPoolDeck, Deck, CardInDeck, PodStats, DokDeck,
    EXPANSION_ID_TO_ABBR,
)
from keytracker.utils import _expected_card_count

LEAGUE_NAME = os.environ.get("LEAGUE_NAME", "abr15")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
db.init_app(app)

with app.app_context():
    league = League.query.filter(
        func.lower(func.replace(League.name, " ", "")) == LEAGUE_NAME.lower()
    ).first()
    if league is None:
        for lg in League.query.all():
            print(f"  league {lg.id}: {lg.name!r}")
        raise SystemExit(f"league {LEAGUE_NAME!r} not found")
    print(f"league {league.id}: {league.name!r}")

    weeks = [w for w in league.weeks]
    print(f"weeks: {[(w.id, w.format_type, w.status) for w in weeks]}")

    pool = (
        SealedPoolDeck.query.filter(
            SealedPoolDeck.week_id.in_([w.id for w in weeks])
        ).all()
    )
    print(f"\nsealed pool deck rows: {len(pool)}")
    by_week = Counter(p.week_id for p in pool)
    print(f"by week: {dict(by_week)}")

    deck_ids = {p.deck_id for p in pool}
    print(f"distinct decks: {len(deck_ids)}\n")

    bad_cards, no_pods, no_dok, ok = [], [], [], 0
    for deck_id in sorted(deck_ids):
        deck = db.session.get(Deck, deck_id)
        if deck is None:
            bad_cards.append((deck_id, "MISSING DECK ROW", None, None))
            continue
        n_cards = db.session.query(func.count(CardInDeck.id)).filter(
            CardInDeck.deck_id == deck_id
        ).scalar()
        n_pods = db.session.query(func.count(PodStats.deck_id)).filter(
            PodStats.deck_id == deck_id
        ).scalar()
        dok = DokDeck.query.filter_by(deck_id=deck_id).first()

        lo, hi = _expected_card_count(deck.expansion)
        problems = []
        if not (lo <= n_cards <= hi):
            problems.append(f"cards={n_cards} (expected {lo}-{hi})")
            bad_cards.append((deck.kf_id, deck.name, n_cards, f"{lo}-{hi}"))
        if n_pods == 0:
            problems.append("no pod stats")
            no_pods.append((deck.kf_id, deck.name))
        if dok is None or dok.sas_rating is None:
            problems.append("no DoK data")
            no_dok.append((deck.kf_id, deck.name))
        if not problems:
            ok += 1

    print(f"clean decks:            {ok}/{len(deck_ids)}")
    print(f"wrong card count:       {len(bad_cards)}")
    print(f"missing pod stats:      {len(no_pods)}")
    print(f"missing DoK data:       {len(no_dok)}")

    for label, rows in (("WRONG CARD COUNT", bad_cards),
                        ("NO POD STATS", no_pods),
                        ("NO DOK DATA", no_dok)):
        if rows:
            print(f"\n=== {label} ({len(rows)}) ===")
            for r in rows[:15]:
                print("  ", r)
            if len(rows) > 15:
                print(f"   ... and {len(rows) - 15} more")
