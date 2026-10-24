"""A playoff sealed bracket deals one pool per team, before anyone is assigned."""
import datetime
import json
import os
import sys

os.environ["TRACKER_CONFIG_PATH"] = "ENV"
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.pop("ENABLE_COLLECTOR", None)

from keytracker.server import app
from keytracker.schema import (
    CardInDeck, Deck, DokDeck, KeyforgeHouse, KeyforgeSet, League, LeagueAdmin,
    LeagueStatus, LeagueWeek, PlatonicCard, PodStats, SealedPoolDeck, Team,
    TeamMember, User, db,
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
TEAMS = 5          # one more than qualifies, to prove it is not dealt to
ADVANCING = 4
SIZE = 2
POOL = 5

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
    league = League(name="TeamPools", team_size=SIZE, num_teams=TEAMS,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))
    teams, players = [], {}
    for t in range(TEAMS):
        team = Team(league_id=league.id, name=f"T{t+1}", order_number=t + 1)
        db.session.add(team)
        db.session.flush()
        roster = []
        for p in range(SIZE):
            u = User(email=f"t{t}p{p}@e.com", name=f"T{t+1}P{p+1}")
            db.session.add(u)
            db.session.flush()
            db.session.add(TeamMember(team_id=team.id, user_id=u.id, is_captain=(p == 0)))
            roster.append(u.id)
        teams.append(team.id)
        players[team.id] = roster
    now = datetime.datetime.utcnow()
    for n in range(40):
        deck = Deck(name=f"deck {n}", kf_id=str(n).ljust(32, "a"), expansion=DM)
        db.session.add(deck)
        db.session.flush()
        db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0, last_refresh=now))
        for h in houses.values():
            db.session.add(PodStats(deck_id=deck.id, kf_house_id=h))
        card = PlatonicCard(card_title=f"Filler {n}")
        db.session.add(card)
        db.session.flush()
        db.session.add(CardInDeck(deck_id=deck.id, platonic_card_id=card.id))
    db.session.commit()
    league_id, admin_id = league.id, admin.id

c = app.test_client()
base = f"/api/v2/leagues/{league_id}/playoffs"
weeks = f"/api/v2/leagues/{league_id}/weeks"


def act_as(user_id):
    with c.session_transaction() as s:
        s["_user_id"] = str(user_id)
        s["_fresh"] = True


act_as(admin_id)
c.put(f"{base}/config", json={"teams_advancing": ADVANCING, "points_per_round": [1, 2]})
r = c.put(f"{base}/brackets", json={"brackets": [
    {"name": "DM Survival", "format_type": "sealed_survival",
     "decks_per_player": POOL, "allowed_sets": [DM]},
    {"name": "Archon", "format_type": "archon_standard"},
]})
b1, b2 = [b["id"] for b in body(r)["brackets"]]
qualifying = teams[:ADVANCING]
left_out = teams[ADVANCING]
c.put(f"{base}/qualifiers", json={"team_ids": qualifying})
c.post(f"{base}/publish", json={"published": True})

# --- draw and open the sealed bracket with nobody assigned -----------------
r = c.post(f"{base}/draw", json={"seed": 11})
check("the brackets draw unassigned", r.status_code == 200, str(body(r))[:80])
r = c.post(f"{base}/rounds/1/start", json={"bracket_id": b1})
check("the sealed bracket's week opens", body(r).get("weeks_created") == 1,
      body(r).get("weeks_created"))

with app.app_context():
    week = LeagueWeek.query.filter_by(playoff_bracket_id=b1, playoff_round=1).first()
    check("the week took the pool size from the bracket",
          week.decks_per_player == POOL, week.decks_per_player)
    week_id = week.id

r = c.post(f"{weeks}/{week_id}/generate-sealed-pools", json={})
check("pools deal with nobody assigned", r.status_code in (200, 201), str(body(r))[:120])

with app.app_context():
    rows = SealedPoolDeck.query.filter_by(week_id=week_id).all()
    check("one pool per qualifying team, and no more",
          len(rows) == ADVANCING * POOL, len(rows))
    check("each row belongs to a team, not a player",
          all(r_.team_id is not None and r_.user_id is None for r_ in rows))
    by_team = {}
    for r_ in rows:
        by_team.setdefault(r_.team_id, []).append(r_.deck_id)
    check("every qualifying team got five",
          sorted(by_team) == sorted(qualifying)
          and all(len(v) == POOL for v in by_team.values()),
          {k: len(v) for k, v in by_team.items()})
    check("the team that did not qualify got none", left_out not in by_team)
    dealt = [d for v in by_team.values() for d in v]
    check("and no deck went to two teams", len(set(dealt)) == len(dealt))
    first_pool = by_team[qualifying[0]]

# --- anyone on the team can see the team's pool ----------------------------
pool_url = f"{weeks}/{week_id}/sealed-pool"
act_as(players[qualifying[0]][0])
r = c.get(pool_url)
check("a player sees their team's pool", len(body(r)) == POOL, str(body(r))[:80])
act_as(players[qualifying[0]][1])
r = c.get(pool_url)
check("so does the teammate who might be assigned instead",
      len(body(r)) == POOL, str(body(r))[:80])
act_as(players[left_out][0])
r = c.get(pool_url)
check("a player on the team that did not qualify sees nothing",
      len(body(r)) == 0, str(body(r))[:80])

# --- assign, publish, and play out of the team pool ------------------------
for team_id in qualifying:
    act_as(players[team_id][0])
    r = c.put(f"{base}/assignments", json={"team_id": team_id, "assignments": [
        {"bracket_id": b1, "user_id": players[team_id][0]},
        {"bracket_id": b2, "user_id": players[team_id][1]},
    ]})
    check(f"team {team_id} assigns", r.status_code == 200, body(r).get("error"))

act_as(admin_id)
r = c.post(f"{base}/assignments/publish", json={"published": True})
check("the assignments publish", r.status_code == 200, str(body(r))[:80])
r = c.post(f"{base}/rounds/1/start", json={"bracket_id": b1})
check("and the matchups are made now", body(r).get("matches_created") == 2,
      body(r).get("matches_created"))

mine = players[qualifying[0]][0]
act_as(mine)
sel = f"{weeks}/{week_id}/deck-selection"
r = c.post(sel, json={"deck_id": first_pool[0], "slot_number": 1})
check("the assigned player keeps one from the team pool",
      r.status_code in (200, 201), str(body(r))[:100])
r = c.post(sel, json={"deck_id": first_pool[1], "slot_number": 2})
check("and a second", r.status_code in (200, 201), str(body(r))[:100])
# Survival keeps two of the five, and the cap is the slot count.
r = c.post(sel, json={"deck_id": first_pool[2], "slot_number": 3})
check("there is no third slot to keep one in", r.status_code == 400,
      str(body(r))[:100])
with app.app_context():
    from keytracker.schema import PlayerDeckSelection
    kept = PlayerDeckSelection.query.filter_by(week_id=week_id, user_id=mine).all()
    check("so exactly two of the five are kept", len(kept) == 2, len(kept))
    check("and both came out of the team pool",
          all(k.deck_id in first_pool for k in kept),
          [k.deck_id for k in kept])

with app.app_context():
    outside = (
        Deck.query.filter(~Deck.id.in_([d for d in first_pool])).first()
    )
    outside_id = outside.id
r = c.post(sel, json={"deck_id": outside_id, "slot_number": 2})
check("a deck from outside the pool is refused", r.status_code == 400,
      str(body(r))[:100])

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
