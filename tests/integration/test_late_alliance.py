"""An alliance can still be entered once the pairings are out, and is logged."""
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
    AlliancePodSelection, CardInDeck, Deck, DokDeck, KeyforgeHouse, KeyforgeSet,
    League, LeagueAdmin, LeagueStatus, LeagueWeek, PlatonicCard, PodStats, Team,
    TeamDeckEntryLog, TeamMember, User, WeekStatus, db,
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


AOA = 435
HOUSES = ("Dis", "Logos", "Untamed")

with app.app_context():
    db.drop_all()
    db.create_all()
    db.session.add(KeyforgeSet(number=AOA, name="Age of Ascension",
                               shortname="AoA", dokname="AoA"))
    hid = {}
    for name in HOUSES:
        h = KeyforgeHouse(name=name)
        db.session.add(h)
        db.session.flush()
        hid[name] = h.id
    admin = User(email="a@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="LA", team_size=1, num_teams=2,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))
    team = Team(league_id=league.id, name="T1", order_number=1)
    db.session.add(team)
    db.session.flush()
    captain = User(email="c@e.com", name="Cap")
    player = User(email="p@e.com", name="Player")
    db.session.add_all([captain, player])
    db.session.flush()
    db.session.add(TeamMember(team_id=team.id, user_id=captain.id, is_captain=True))
    db.session.add(TeamMember(team_id=team.id, user_id=player.id))

    now = datetime.datetime.utcnow()
    decks = {}
    for house in HOUSES:
        deck = Deck(name=f"deck {house}", kf_id=str(uuid.uuid4()), expansion=AOA)
        db.session.add(deck)
        db.session.flush()
        db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0, last_refresh=now))
        for h in hid.values():
            db.session.add(PodStats(deck_id=deck.id, kf_house_id=h))
        card = PlatonicCard(card_title=f"Filler {house}")
        db.session.add(card)
        db.session.flush()
        db.session.add(CardInDeck(deck_id=deck.id, platonic_card_id=card.id))
        decks[house] = deck.id

    week = LeagueWeek(league_id=league.id, week_number=1, name="AoA Alliance",
                      format_type="alliance", best_of_n=3,
                      status=WeekStatus.PUBLISHED.value,
                      allowed_sets=json.dumps([AOA]))
    db.session.add(week)
    db.session.commit()
    league_id, week_id = league.id, week.id
    captain_id, player_id, admin_id = captain.id, player.id, admin.id
    team_id = team.id
    pods = [{"deck_id": decks[h], "house": h} for h in HOUSES]

c = app.test_client()
url = f"/api/v2/leagues/{league_id}/weeks/{week_id}/alliance-selection"


def act_as(uid):
    with c.session_transaction() as s:
        s["_user_id"] = str(uid)
        s["_fresh"] = True


# --- the captain can enter it late -----------------------------------------
act_as(captain_id)
r = c.post(url, json={"pods": pods, "user_id": player_id})
check("a captain can forge an alliance after pairings",
      r.status_code in (200, 201), str(body(r))[:100])

with app.app_context():
    stored = AlliancePodSelection.query.filter_by(
        week_id=week_id, user_id=player_id, slot_type="pod"
    ).count()
    check("all three pods are stored", stored == 3, stored)
    logged = TeamDeckEntryLog.query.filter_by(
        week_id=week_id, target_user_id=player_id
    ).all()
    check("and it is written to the deck entry log", len(logged) == 1, len(logged))
    if logged:
        check("naming who entered it",
              logged[0].changed_by_user_id == captain_id, logged[0].changed_by_user_id)
        check("and that it was an alliance",
              "Alliance" in (logged[0].deck_name or ""), logged[0].deck_name)

# --- a player cannot let themselves in late --------------------------------
act_as(player_id)
r = c.post(url, json={"pods": pods})
check("a player cannot enter their own late",
      r.status_code == 403 and "closed" in str(body(r).get("error")),
      body(r).get("error"))

# --- an admin can ----------------------------------------------------------
act_as(admin_id)
r = c.post(url, json={"pods": pods, "user_id": player_id})
check("an admin can", r.status_code in (200, 201), str(body(r))[:80])

# --- and the ordinary window still works -----------------------------------
with app.app_context():
    w = db.session.get(LeagueWeek, week_id)
    w.status = WeekStatus.DECK_SELECTION.value
    db.session.commit()
act_as(player_id)
r = c.post(url, json={"pods": pods})
check("a player can forge their own while selection is open",
      r.status_code in (200, 201), str(body(r))[:80])
with app.app_context():
    logged = TeamDeckEntryLog.query.filter_by(week_id=week_id).count()
    check("and that one is not logged as a late entry", logged == 2, logged)

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
