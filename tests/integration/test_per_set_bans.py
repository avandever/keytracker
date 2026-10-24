"""A ban must be a house the set it is aimed at actually holds."""
import datetime
import json
import os
import sys

os.environ["TRACKER_CONFIG_PATH"] = "ENV"
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.pop("ENABLE_COLLECTOR", None)

from keytracker.server import app
from keytracker.serializers import _houses_by_set
from keytracker.schema import (
    CardInDeck, Deck, DokDeck, KeyforgeHouse, KeyforgeSet, League, LeagueAdmin,
    LeagueStatus, LeagueWeek, PlatonicCard, PlatonicCardInSet, PlayerDeckSelection,
    PodStats, Team, TeamMember, User, WeekStatus, db,
)

FAIL = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + str(detail)) if detail else ''}")
    if not ok:
        FAIL.append(label)


def body(r):
    try:
        return json.loads(r.data)
    except Exception:
        return {"raw": r.data[:300].decode("utf-8", "replace")}


BIG, SMALL = 600, 855
# The real shape: one set far wider than the other.
BIG_HOUSES = ["Brobnar", "Dis", "Ekwidon", "Logos", "Mars", "Sanctum"]
SMALL_HOUSES = ["Dis", "Geistoid", "Logos"]

with app.app_context():
    db.drop_all()
    db.create_all()
    db.session.add(KeyforgeSet(number=BIG, name="Big Set", shortname="BIG", dokname="BIG"))
    db.session.add(KeyforgeSet(number=SMALL, name="Small Set", shortname="SML", dokname="SML"))
    hid = {}
    for name in sorted(set(BIG_HOUSES) | set(SMALL_HOUSES)):
        h = KeyforgeHouse(name=name)
        db.session.add(h)
        db.session.flush()
        hid[name] = h.id

    # Card data is what says which houses a set holds.
    for expansion, houses in ((BIG, BIG_HOUSES), (SMALL, SMALL_HOUSES)):
        for house in houses:
            card = PlatonicCard(card_title=f"{house} card {expansion}")
            db.session.add(card)
            db.session.flush()
            db.session.add(
                PlatonicCardInSet(card_id=card.id, expansion=expansion,
                                  kf_house_id=hid[house], is_maverick=False,
                                  is_anomaly=False)
            )

    admin = User(email="a@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="PS", team_size=1, num_teams=2,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))
    team = Team(league_id=league.id, name="T1", order_number=1)
    db.session.add(team)
    db.session.flush()
    me = User(email="me@e.com", name="Me")
    db.session.add(me)
    db.session.flush()
    db.session.add(TeamMember(team_id=team.id, user_id=me.id, is_captain=True))

    now = datetime.datetime.utcnow()

    def make_deck(name, expansion, houses):
        deck = Deck(name=name, kf_id=name.ljust(32, "x")[:32], expansion=expansion)
        db.session.add(deck)
        db.session.flush()
        db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0, last_refresh=now))
        for h in houses:
            db.session.add(PodStats(deck_id=deck.id, kf_house_id=hid[h]))
        db.session.flush()
        return deck

    week = LeagueWeek(league_id=league.id, week_number=1, name="Double",
                      format_type="double_oubliette", best_of_n=3,
                      status=WeekStatus.DECK_SELECTION.value,
                      allowed_sets=json.dumps([BIG, SMALL]))
    db.session.add(week)
    db.session.flush()

    # My own decks: the ban must dodge these houses too.
    big_deck = make_deck("big", BIG, ["Brobnar", "Dis", "Ekwidon"])
    small_deck = make_deck("small", SMALL, ["Dis", "Geistoid", "Logos"])
    db.session.add(PlayerDeckSelection(week_id=week.id, user_id=me.id,
                                       deck_id=big_deck.id, slot_number=1))
    db.session.add(PlayerDeckSelection(week_id=week.id, user_id=me.id,
                                       deck_id=small_deck.id, slot_number=3))
    db.session.commit()

    by_set = _houses_by_set(week, [BIG, SMALL])
    check("the big set reports its own houses",
          sorted(by_set.get(BIG, [])) == sorted(BIG_HOUSES), by_set.get(BIG))
    check("and the small set only its three",
          sorted(by_set.get(SMALL, [])) == sorted(SMALL_HOUSES), by_set.get(SMALL))
    check("a non-banning format gets nothing",
          _houses_by_set(
              LeagueWeek(league_id=league.id, week_number=9, format_type="archon_standard"),
              [BIG, SMALL],
          ) == {}, "should be empty")

    league_id, week_id, me_id = league.id, week.id, me.id

c = app.test_client()
with c.session_transaction() as s:
    s["_user_id"] = str(me_id)
    s["_fresh"] = True
ban_url = f"/api/v2/leagues/{league_id}/weeks/{week_id}/oubliette-ban"

# Mars is in the big set but not the small one.
r = c.post(ban_url, json={"banned_house": "Mars", "expansion": BIG})
check("a house the set holds is accepted", r.status_code == 200, body(r))

r = c.post(ban_url, json={"banned_house": "Mars", "expansion": SMALL})
check("the same house is refused for a set without it",
      r.status_code == 400 and "not a house in that set" in str(body(r).get("error")),
      body(r).get("error"))

# And the own-deck rule still bites inside the set.
r = c.post(ban_url, json={"banned_house": "Dis", "expansion": SMALL})
check("a house in my own deck from that set is still refused",
      r.status_code == 400, body(r).get("error"))

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
