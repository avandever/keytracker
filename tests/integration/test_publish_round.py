"""Opening a round, publishing its pairings, and only then reporting."""
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


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + str(detail)) if detail else ''}")
    if not ok:
        FAIL.append(label)


def body(r):
    try:
        return json.loads(r.data)
    except Exception:
        return {"raw": r.data[:300].decode("utf-8", "replace")}


DM = 928
TEAMS = 4

with app.app_context():
    db.drop_all()
    db.create_all()
    db.session.add(KeyforgeSet(number=DM, name="Draconian Measures",
                               shortname="DM", dokname="DM"))
    hid = {}
    for name in ("Mars", "Logos", "Untamed"):
        h = KeyforgeHouse(name=name)
        db.session.add(h)
        db.session.flush()
        hid[name] = h.id
    admin = User(email="a@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="Pub", team_size=1, num_teams=TEAMS,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))
    teams, players = [], {}
    for t in range(TEAMS):
        team = Team(league_id=league.id, name=f"T{t+1}", order_number=t + 1)
        db.session.add(team)
        db.session.flush()
        u = User(email=f"p{t}@e.com", name=f"P{t+1}")
        db.session.add(u)
        db.session.flush()
        db.session.add(TeamMember(team_id=team.id, user_id=u.id, is_captain=True))
        teams.append(team.id)
        players[team.id] = u.id
    now = datetime.datetime.utcnow()
    deck_urls = {}
    for t in teams:
        kf = str(uuid.uuid4())
        deck = Deck(name=f"deck {t}", kf_id=kf, expansion=DM)
        db.session.add(deck)
        db.session.flush()
        db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0, last_refresh=now))
        for h in hid.values():
            db.session.add(PodStats(deck_id=deck.id, kf_house_id=h))
        card = PlatonicCard(card_title=f"Filler {t}")
        db.session.add(card)
        db.session.flush()
        db.session.add(CardInDeck(deck_id=deck.id, platonic_card_id=card.id))
        deck_urls[t] = f"https://decksofkeyforge.com/decks/{kf}"
    db.session.commit()
    league_id, admin_id = league.id, admin.id

c = app.test_client()
base = f"/api/v2/leagues/{league_id}/playoffs"


def act_as(uid):
    with c.session_transaction() as s:
        s["_user_id"] = str(uid)
        s["_fresh"] = True


act_as(admin_id)
c.put(f"{base}/config", json={"teams_advancing": TEAMS, "points_per_round": [1, 2]})
r = c.put(f"{base}/brackets", json={"brackets": [
    {"name": "One", "format_type": "archon_standard", "allowed_sets": [DM]},
]})
bracket_id = body(r)["brackets"][0]["id"]
c.put(f"{base}/qualifiers", json={"team_ids": teams})
c.post(f"{base}/publish", json={"published": True})
for t in teams:
    act_as(players[t])
    c.put(f"{base}/assignments", json={"team_id": t, "assignments": [
        {"bracket_id": bracket_id, "user_id": players[t]},
    ]})
act_as(admin_id)
c.post(f"{base}/assignments/publish", json={"published": True})
c.post(f"{base}/draw", json={"seed": 1})
r = c.post(f"{base}/rounds/1/start", json={})
check("the round opens with its matchups", body(r).get("matches_created") == 2,
      body(r).get("matches_created"))

with app.app_context():
    week = LeagueWeek.query.filter_by(league_id=league_id, playoff_round=1).first()
    week_id = week.id
    check("and the week starts in deck selection",
          week.status == WeekStatus.DECK_SELECTION.value, week.status)

# --- reporting is refused before the pairings are published ---------------
with app.app_context():
    week = db.session.get(LeagueWeek, week_id)
    pm = week.matchups[0].player_matchups[0]
    pm_id, p1 = pm.id, pm.player1_id
act_as(admin_id)
r = c.post(f"/api/v2/leagues/{league_id}/matches/{pm_id}/games",
           json={"winner_id": p1, "player1_keys": 3, "player2_keys": 0})
check("a result cannot be reported yet",
      r.status_code == 400 and "not published" in str(body(r).get("error")),
      body(r).get("error"))

# --- it waits for the decks ------------------------------------------------
r = c.post(f"{base}/rounds/1/publish", json={})
check("publishing waits on the missing decks", r.status_code == 400,
      str(body(r).get("error"))[:80])
check("and names who is short", len(body(r).get("missing_players") or []) == TEAMS,
      body(r).get("missing_players"))

# Everyone submits.
for t in teams:
    act_as(players[t])
    rr = c.post(f"/api/v2/leagues/{league_id}/weeks/{week_id}/deck-selection",
                json={"deck_url": deck_urls[t], "slot_number": 1})
    check(f"team {t} submits", rr.status_code in (200, 201), str(body(rr))[:70])

act_as(admin_id)
r = c.post(f"{base}/rounds/1/publish", json={})
check("now the pairings publish", r.status_code == 200, str(body(r))[:80])
check("for the one week in the round", body(r).get("weeks_published") == 1,
      body(r).get("weeks_published"))

with app.app_context():
    check("the week is published",
          db.session.get(LeagueWeek, week_id).status == WeekStatus.PUBLISHED.value)

# --- and now a result sticks ----------------------------------------------
r = c.post(f"/api/v2/leagues/{league_id}/matches/{pm_id}/games",
           json={"game_number": 1, "winner_id": p1,
                 "player1_keys": 3, "player2_keys": 0})
check("a result can be reported", r.status_code in (200, 201), str(body(r))[:90])

# --- and it cannot be put back once played --------------------------------
r = c.post(f"{base}/rounds/1/publish", json={"published": False})
check("the round cannot be unpublished after a game",
      r.status_code == 400 and "already been reported" in str(body(r).get("error")),
      body(r).get("error"))

# --- force, on a round nobody has filled ----------------------------------
r = c.post(f"{base}/rounds/2/publish", json={})
check("an unopened round says so", r.status_code == 400, body(r).get("error"))

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
