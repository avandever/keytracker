"""A sealed bracket's round-two pool is dealt to a team when it wins in."""
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
    LeagueStatus, LeagueWeek, MatchGame, PlatonicCard, PlayerMatchup,
    PlayoffBracket, PodStats, SealedPoolDeck, Team, TeamMember, User, db,
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
PER = 4

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
    admin = User(email="admin@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="Pools", team_size=1, num_teams=TEAMS,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))
    teams, players, names = [], {}, {}
    for i, label in enumerate("ABCD"):
        team = Team(league_id=league.id, name=f"Team {label}", order_number=i + 1)
        db.session.add(team)
        db.session.flush()
        u = User(email=f"{label}@e.com", name=f"Player {label}")
        db.session.add(u)
        db.session.flush()
        db.session.add(TeamMember(team_id=team.id, user_id=u.id, is_captain=True))
        teams.append(team.id)
        players[team.id] = u.id
        names[team.id] = label
    now = datetime.datetime.utcnow()
    # Enough for four teams in round one and two in round two, and no more,
    # so a pool dealt to a team that is out would starve the round.
    for n in range(PER * (TEAMS + 2)):
        kf = str(uuid.uuid4())
        deck = Deck(name=f"deck {n}", kf_id=kf, expansion=DM)
        db.session.add(deck)
        db.session.flush()
        db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0, last_refresh=now))
        for h in hid.values():
            db.session.add(PodStats(deck_id=deck.id, kf_house_id=h))
        card = PlatonicCard(card_title=f"Filler {n}")
        db.session.add(card)
        db.session.flush()
        db.session.add(CardInDeck(deck_id=deck.id, platonic_card_id=card.id))
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
    {"name": "Sealed", "format_type": "sealed_archon", "allowed_sets": [DM],
     "decks_per_player": PER},
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
c.post(f"{base}/draw", json={"seed": 4})
c.post(f"{base}/rounds/1/start", json={})

with app.app_context():
    week1 = LeagueWeek.query.filter_by(league_id=league_id, playoff_round=1).first()
    week1_id = week1.id
    wins_needed = -(-week1.best_of_n // 2)
    bracket = db.session.get(PlayoffBracket, bracket_id)
    r1 = sorted(
        [m for m in bracket.matches if m.round_number == 1 and not m.is_bye],
        key=lambda m: m.slot_index,
    )
    pairs = [(m.team1_id, m.team2_id, m.player_matchup_id) for m in r1]
print(f"  round 1: {names[pairs[0][0]]} v {names[pairs[0][1]]}   and   "
      f"{names[pairs[1][0]]} v {names[pairs[1][1]]}")


def pool_teams(week_id):
    with app.app_context():
        rows = SealedPoolDeck.query.filter_by(week_id=week_id).all()
        out = {}
        for row in rows:
            out.setdefault(row.team_id, set()).add(row.deck_id)
        return out


r = c.post(f"/api/v2/leagues/{league_id}/weeks/{week1_id}/generate-sealed-pools")
check("round 1 pools deal", r.status_code == 200, str(body(r))[:90])
p1 = pool_teams(week1_id)
check("all four teams have a round 1 pool", sorted(p1) == sorted(teams),
      [names.get(t) for t in p1])
check("four decks each", all(len(v) == PER for v in p1.values()),
      {names.get(k): len(v) for k, v in p1.items()})

# --- one match resolves -------------------------------------------------
winner, loser, first_pm = pairs[0][1], pairs[0][0], pairs[0][2]
with app.app_context():
    pm = db.session.get(PlayerMatchup, first_pm)
    for n in range(wins_needed):
        db.session.add(MatchGame(player_matchup_id=pm.id, game_number=n + 1,
                                 winner_id=players[winner], player1_keys=3,
                                 player2_keys=0))
    db.session.commit()
act_as(admin_id)
r = c.post(f"/api/v2/leagues/{league_id}/matches/{first_pm}/confirm-result")
check("the result verifies", r.status_code == 200, str(body(r))[:70])

r = c.post(f"{base}/rounds/2/start", json={})
check("round 2 opens", r.status_code == 200, str(body(r).get("error"))[:80])
with app.app_context():
    week2_id = LeagueWeek.query.filter_by(
        league_id=league_id, playoff_round=2
    ).first().id

# --- the admin deals round 2: only the team that is in it gets a pool ----
r = c.post(f"/api/v2/leagues/{league_id}/weeks/{week2_id}/generate-sealed-pools")
check("round 2 pools deal", r.status_code == 200, str(body(r))[:90])
p2 = pool_teams(week2_id)
check(f"only {names[winner]} has a round 2 pool, not all four",
      list(p2) == [winner], [names.get(t) for t in p2])
check("and it is four decks", all(len(v) == PER for v in p2.values()),
      {names.get(k): len(v) for k, v in p2.items()})

r = c.post(f"/api/v2/leagues/{league_id}/weeks/{week2_id}/generate-sealed-pools")
check("dealing again now says there is nobody to deal to",
      r.status_code == 400 and "already has a pool" in str(body(r).get("error")),
      body(r).get("error"))

# --- the other match resolves and that team is dealt in, unprompted ------
other_winner, other_pm = pairs[1][1], pairs[1][2]
with app.app_context():
    pm = db.session.get(PlayerMatchup, other_pm)
    for n in range(wins_needed):
        db.session.add(MatchGame(player_matchup_id=pm.id, game_number=n + 1,
                                 winner_id=players[other_winner], player1_keys=3,
                                 player2_keys=0))
    db.session.commit()
act_as(admin_id)
r = c.post(f"/api/v2/leagues/{league_id}/matches/{other_pm}/confirm-result")
check("the second result verifies", r.status_code == 200, str(body(r))[:70])

p2 = pool_teams(week2_id)
check(f"{names[other_winner]} was dealt a pool on winning, with no admin action",
      sorted(p2) == sorted([winner, other_winner]), [names.get(t) for t in p2])
check("four decks each", all(len(v) == PER for v in p2.values()),
      {names.get(k): len(v) for k, v in p2.items()})
overlap = p2.get(winner, set()) & p2.get(other_winner, set())
check("and not a deck the other team already holds", not overlap, overlap)

# A pool deck is exempt from the one-deck-per-week rule in either direction,
# so round two may hand out a deck round one used. What it must not do is
# hand a team the same pool over again.
check("a team's round 2 pool is a new deal, not its round 1 pool",
      p2[winner] != p1[winner], "identical pool")

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
