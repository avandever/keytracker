"""Set diversity is checked wherever it is asked for, except where it cannot be."""
import datetime
import json
import os
import sys
import uuid

os.environ["TRACKER_CONFIG_PATH"] = "ENV"
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.pop("ENABLE_COLLECTOR", None)

from keytracker.server import app
from keytracker.schema import (
    CardInDeck, Deck, DokDeck, KeyforgeHouse, KeyforgeSet, League, LeagueAdmin,
    LeagueStatus, LeagueWeek, PlatonicCard, PodStats, Team, TeamMember, User,
    WeekStatus, db,
)

FAIL = []

CotA = 341
PV = 886
DM = 928


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + str(detail)) if detail else ''}")
    if not ok:
        FAIL.append(label)


def body(r):
    try:
        return json.loads(r.data)
    except Exception:
        return {"raw": r.data[:200].decode("utf-8", "replace")}


with app.app_context():
    db.drop_all()
    db.create_all()
    for number, name in ((CotA, "Call of the Archons"), (PV, "Prophetic Visions"),
                         (DM, "Draconian Measures")):
        db.session.add(KeyforgeSet(number=number, name=name,
                                   shortname=name[:3], dokname=name[:3]))
    hid = {}
    for name in ("Mars", "Logos", "Untamed"):
        h = KeyforgeHouse(name=name)
        db.session.add(h)
        db.session.flush()
        hid[name] = h.id
    admin = User(email="admin@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="Diversity", team_size=1, num_teams=1,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))
    team = Team(league_id=league.id, name="Team", order_number=1)
    db.session.add(team)
    db.session.flush()
    player = User(email="p@e.com", name="Player")
    db.session.add(player)
    db.session.flush()
    db.session.add(TeamMember(team_id=team.id, user_id=player.id, is_captain=True))

    now = datetime.datetime.utcnow()
    urls = {}
    for label, expansion in (("cota1", CotA), ("cota2", CotA), ("pv1", PV),
                             ("dm1", DM), ("dm2", DM), ("pv2", PV),
                             ("pv3", PV)):
        kf = str(uuid.uuid4())
        deck = Deck(name=f"deck {label}", kf_id=kf, expansion=expansion)
        db.session.add(deck)
        db.session.flush()
        db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0, last_refresh=now))
        for h in hid.values():
            db.session.add(PodStats(deck_id=deck.id, kf_house_id=h))
        card = PlatonicCard(card_title=f"Filler {label}")
        db.session.add(card)
        db.session.flush()
        db.session.add(CardInDeck(deck_id=deck.id, platonic_card_id=card.id))
        urls[label] = f"https://decksofkeyforge.com/decks/{kf}"

    weeks = {}
    for name, fmt, sets, slots in (
        ("exchange", "exchange", [CotA, PV], 2),
        ("double", "double_oubliette", [PV, DM], 4),
    ):
        week = LeagueWeek(
            league_id=league.id, week_number=len(weeks) + 1, name=name,
            format_type=fmt, best_of_n=3,
            status=WeekStatus.DECK_SELECTION.value,
            allowed_sets=json.dumps(sets), set_diversity=True,
        )
        db.session.add(week)
        db.session.flush()
        weeks[name] = week.id
    db.session.commit()
    league_id, player_id = league.id, player.id

c = app.test_client()
with c.session_transaction() as s:
    s["_user_id"] = str(player_id)
    s["_fresh"] = True


def submit(week_id, label, slot):
    return c.post(
        f"/api/v2/leagues/{league_id}/weeks/{week_id}/deck-selection",
        json={"deck_url": urls[label], "slot_number": slot},
    )


# --- Exchange: one from each set, which is what the rule is for ----------
ex = weeks["exchange"]
r = submit(ex, "cota1", 1)
check("the first deck goes in", r.status_code in (200, 201), str(body(r))[:70])

r = submit(ex, "cota2", 2)
check("a second deck from the same set is refused",
      r.status_code == 400 and "Set diversity" in str(body(r).get("error")),
      body(r).get("error"))

r = submit(ex, "pv1", 2)
check("one from the other set is accepted",
      r.status_code in (200, 201), str(body(r))[:70])

# --- Double Oubliette: two per set, so the rule cannot apply -------------
do = weeks["double"]
ok = True
# Decks of their own: one already played in the Exchange week is barred
# by the reuse rule, which is a different rule and not what is under test.
for label, slot in (("pv2", 1), ("pv3", 2), ("dm1", 3), ("dm2", 4)):
    r = submit(do, label, slot)
    if r.status_code not in (200, 201):
        ok = False
        print(f"      slot {slot} ({label}) rejected: {body(r).get('error')}")
check("all four Double Oubliette decks go in, two per set", ok)

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
