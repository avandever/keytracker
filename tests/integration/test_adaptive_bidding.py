"""Adaptive bidding can be done in a league, or declared done elsewhere."""
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
    LeagueStatus, LeagueWeek, PlatonicCard, PlayerDeckSelection, PlayerMatchup,
    PodStats, Team, TeamMember, User, WeekMatchup, WeekStatus, db,
)

FAIL = []
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
    db.session.add(KeyforgeSet(number=DM, name="Draconian Measures",
                               shortname="DM", dokname="DM"))
    houses = {}
    for name in ("Mars", "Logos", "Untamed"):
        h = KeyforgeHouse(name=name)
        db.session.add(h)
        db.session.flush()
        houses[name] = h.id
    admin = User(email="admin@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="Adaptive", team_size=2, num_teams=2,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))
    users, teams = {}, []
    for i, names in enumerate((("Cap1", "Ann"), ("Cap2", "Bob"))):
        team = Team(league_id=league.id, name=f"Team {i + 1}", order_number=i + 1)
        db.session.add(team)
        db.session.flush()
        teams.append(team.id)
        for j, name in enumerate(names):
            u = User(email=f"{name}@e.com", name=name)
            db.session.add(u)
            db.session.flush()
            db.session.add(
                TeamMember(team_id=team.id, user_id=u.id, is_captain=(j == 0))
            )
            users[name] = u.id

    week = LeagueWeek(
        league_id=league.id, week_number=1, name="Adaptive",
        format_type="adaptive", best_of_n=3,
        status=WeekStatus.PUBLISHED.value, allowed_sets=json.dumps([DM]),
    )
    db.session.add(week)
    db.session.flush()
    now = datetime.datetime.utcnow()
    decks = {}
    for name in ("Ann", "Bob"):
        kf = str(uuid.uuid4())
        deck = Deck(name=f"{name} deck", kf_id=kf, expansion=DM)
        db.session.add(deck)
        db.session.flush()
        db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0, last_refresh=now))
        for h in houses.values():
            db.session.add(PodStats(deck_id=deck.id, kf_house_id=h))
        card = PlatonicCard(card_title=f"Filler {name}")
        db.session.add(card)
        db.session.flush()
        db.session.add(CardInDeck(deck_id=deck.id, platonic_card_id=card.id))
        db.session.add(PlayerDeckSelection(week_id=week.id, user_id=users[name],
                                           deck_id=deck.id, slot_number=1))
        decks[name] = deck.id
    wm = WeekMatchup(week_id=week.id, team1_id=teams[0], team2_id=teams[1])
    db.session.add(wm)
    db.session.flush()
    pm = PlayerMatchup(week_matchup_id=wm.id, player1_id=users["Ann"],
                       player2_id=users["Bob"])
    db.session.add(pm)
    db.session.commit()
    league_id, pm_id = league.id, pm.id

c = app.test_client()
base = f"/api/v2/leagues/{league_id}/matches/{pm_id}"


def act_as(uid):
    with c.session_transaction() as s:
        s["_user_id"] = str(uid)
        s["_fresh"] = True


for name in ("Ann", "Bob"):
    act_as(users[name])
    c.post(f"{base}/start")

# One win each, which is what starts the bidding.
act_as(users["Ann"])
for n, winner in ((1, "Ann"), (2, "Bob")):
    r = c.post(f"{base}/games", json={
        "winner_id": users[winner], "game_number": n,
        "player1_keys": 3 if winner == "Ann" else 0,
        "player2_keys": 0 if winner == "Ann" else 3,
    })
    if r.status_code not in (200, 201):
        print("      game", n, "error:", body(r).get("error"))

with app.app_context():
    pm = db.session.get(PlayerMatchup, pm_id)
    check("a 1-1 tie opens the bidding", pm.adaptive_bid_chains is not None,
          (pm.adaptive_bid_chains, pm.adaptive_bidder_id))
    holder = pm.adaptive_bidder_id
    other = pm.player2_id if holder == pm.player1_id else pm.player1_id

# --- game 3 is refused until it settles ----------------------------------
act_as(users["Ann"])
r = c.post(f"{base}/games", json={
    "winner_id": users["Ann"], "game_number": 3,
    "player1_keys": 3, "player2_keys": 0,
})
check("game 3 is refused while bidding is open",
      r.status_code == 400 and "bidding" in str(body(r).get("error", "")),
      body(r).get("error"))

# --- the holder cannot answer their own bid ------------------------------
act_as(holder)
r = c.post(f"{base}/adaptive-bid", json={"chains": 3})
check("the holder cannot bid against themselves", r.status_code == 400,
      body(r).get("error"))

# --- the other player raises, then the first accepts ---------------------
act_as(other)
r = c.post(f"{base}/adaptive-bid", json={"chains": 2})
check("the other player can raise", r.status_code == 200, str(body(r))[:70])

act_as(holder)
r = c.post(f"{base}/adaptive-bid", json={"concede": True})
check("and the first can accept, settling it", r.status_code == 200,
      str(body(r))[:70])

act_as(users["Ann"])
r = c.post(f"{base}/games", json={
    "winner_id": users["Ann"], "game_number": 3,
    "player1_keys": 3, "player2_keys": 0,
})
check("game 3 reports once bidding is settled", r.status_code in (200, 201),
      str(body(r))[:70])

# --- and the waiver, for a match bid across a table ----------------------
with app.app_context():
    pm = db.session.get(PlayerMatchup, pm_id)
    pm.adaptive_bidding_complete = False
    for g in list(pm.games):
        if g.game_number == 3:
            db.session.delete(g)
    # Reporting game 3 decided the match, which closed the week behind it.
    week_row = db.session.get(LeagueWeek, pm.week_matchup.week_id)
    week_row.status = WeekStatus.PUBLISHED.value
    db.session.commit()

act_as(users["Bob"])
r = c.post(f"{base}/adaptive-bid-not-recorded")
check("a player cannot waive it", r.status_code == 403, body(r).get("error"))

act_as(users["Cap1"])
r = c.post(f"{base}/adaptive-bid-not-recorded")
check("a captain can", r.status_code == 200, str(body(r))[:70])
check("and the matchup says so",
      body(r).get("adaptive_bid_not_recorded") is True,
      body(r).get("adaptive_bid_not_recorded"))

act_as(users["Ann"])
r = c.post(f"{base}/games", json={
    "winner_id": users["Ann"], "game_number": 3,
    "player1_keys": 3, "player2_keys": 0,
})
check("which lets game 3 be reported", r.status_code in (200, 201),
      str(body(r))[:70])

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
