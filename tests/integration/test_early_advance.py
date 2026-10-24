"""B beats A and starts round two while C against D is still being played."""
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
    LeagueStatus, LeagueWeek, MatchGame, PlatonicCard, PlayerDeckSelection,
    PlayoffBracket, PodStats, Team, TeamMember, User, WeekStatus, db,
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
    admin = User(email="admin@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="Early", team_size=1, num_teams=TEAMS,
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
    urls = {}
    for n in range(12):
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
        urls[n] = f"https://decksofkeyforge.com/decks/{kf}"
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
c.post(f"{base}/draw", json={"seed": 4})
c.post(f"{base}/rounds/1/start", json={})

with app.app_context():
    week1 = LeagueWeek.query.filter_by(league_id=league_id, playoff_round=1).first()
    week1_id = week1.id
    bracket = db.session.get(PlayoffBracket, bracket_id)
    r1 = sorted(
        [m for m in bracket.matches if m.round_number == 1 and not m.is_bye],
        key=lambda m: m.slot_index,
    )
    first, second = r1[0], r1[1]
    first_pair = (first.team1_id, first.team2_id)
    second_pair = (second.team1_id, second.team2_id)
    first_pm = first.player_matchup_id
print(f"  round 1: {names[first_pair[0]]} v {names[first_pair[1]]}   and   "
      f"{names[second_pair[0]]} v {names[second_pair[1]]}")

# Everyone submits round 1 and the pairings publish so results can be taken.
for i, t in enumerate(teams):
    act_as(players[t])
    c.post(f"/api/v2/leagues/{league_id}/weeks/{week1_id}/deck-selection",
           json={"deck_url": urls[i], "slot_number": 1})
act_as(admin_id)
c.post(f"{base}/rounds/1/publish", json={})

# --- only the first match is played and verified -------------------------
winner_team = first_pair[1]          # the second team in that match wins
loser_team = first_pair[0]
with app.app_context():
    from keytracker.schema import PlayerMatchup
    pm = db.session.get(PlayerMatchup, first_pm)
    week = db.session.get(LeagueWeek, week1_id)
    wins_needed = -(-week.best_of_n // 2)
    winner_user = players[winner_team]
    for n in range(wins_needed):
        db.session.add(MatchGame(player_matchup_id=pm.id, game_number=n + 1,
                                 winner_id=winner_user, player1_keys=3,
                                 player2_keys=0))
    db.session.commit()
act_as(admin_id)
r = c.post(f"/api/v2/leagues/{league_id}/matches/{first_pm}/confirm-result")
check("the first result verifies", r.status_code == 200, str(body(r))[:80])

with app.app_context():
    bracket = db.session.get(PlayoffBracket, bracket_id)
    r2 = [m for m in bracket.matches if m.round_number == 2]
    slots = [(m.team1_id, m.team2_id) for m in r2]
    advanced = {t for pair in slots for t in pair if t}
    check(f"{names[winner_team]} is already in round 2 without the other match",
          winner_team in advanced, [names.get(t) for t in advanced])
    check("and the loser is not", loser_team not in advanced)
    check("the other half of the bracket is still empty",
          len(advanced) == 1, [names.get(t) for t in advanced])

# --- round 2 opens on what has resolved ----------------------------------
r = c.post(f"{base}/rounds/2/start", json={})
check("round 2 opens with one match still outstanding",
      r.status_code == 200, str(body(r).get("error"))[:90])
with app.app_context():
    week2 = LeagueWeek.query.filter_by(league_id=league_id, playoff_round=2).first()
    check("its week exists", week2 is not None)
    week2_id = week2.id if week2 else None
    check("and nobody is paired in it yet",
          week2 is not None and len(week2.matchups) == 0,
          len(week2.matchups) if week2 else None)

# --- the winner can prepare; the loser cannot ----------------------------
act_as(players[winner_team])
r = c.post(f"/api/v2/leagues/{league_id}/weeks/{week2_id}/deck-selection",
           json={"deck_url": urls[4], "slot_number": 1})
check(f"{names[winner_team]} can enter a deck for round 2 already",
      r.status_code in (200, 201), str(body(r))[:100])

act_as(players[loser_team])
r = c.post(f"/api/v2/leagues/{league_id}/weeks/{week2_id}/deck-selection",
           json={"deck_url": urls[5], "slot_number": 1})
check(f"{names[loser_team]}, knocked out, cannot",
      r.status_code == 400 and "not in that round" in str(body(r).get("error")),
      body(r).get("error"))

still_playing = second_pair[0]
act_as(players[still_playing])
r = c.post(f"/api/v2/leagues/{league_id}/weeks/{week2_id}/deck-selection",
           json={"deck_url": urls[6], "slot_number": 1})
check(f"{names[still_playing]}, still in round 1, cannot either",
      r.status_code == 400, body(r).get("error"))

# --- and the round 2 week is only visible to the team in it --------------
def playoff_rounds_for(uid):
    act_as(uid)
    d = body(c.get(f"/api/v2/leagues/{league_id}"))
    return sorted({w["playoff_round"] for w in (d.get("playoff_weeks") or [])})


check(f"{names[winner_team]} sees rounds 1 and 2",
      playoff_rounds_for(players[winner_team]) == [1, 2],
      playoff_rounds_for(players[winner_team]))
check(f"{names[loser_team]} sees only round 1 -- round 2 is simply not there",
      playoff_rounds_for(players[loser_team]) == [1],
      playoff_rounds_for(players[loser_team]))
check(f"{names[still_playing]} likewise, until their match resolves",
      playoff_rounds_for(players[still_playing]) == [1],
      playoff_rounds_for(players[still_playing]))

# --- the other match finishes and the final pairs itself ------------------
with app.app_context():
    from keytracker.schema import PlayerMatchup
    bracket = db.session.get(PlayoffBracket, bracket_id)
    other = next(
        m for m in bracket.matches
        if m.round_number == 1 and m.player_matchup_id != first_pm and not m.is_bye
    )
    other_pm_id = other.player_matchup_id
    second_winner = other.team2_id
    pm = db.session.get(PlayerMatchup, other_pm_id)
    for n in range(wins_needed):
        db.session.add(MatchGame(player_matchup_id=pm.id, game_number=n + 1,
                                 winner_id=players[second_winner], player1_keys=3,
                                 player2_keys=0))
    db.session.commit()
act_as(admin_id)
r = c.post(f"/api/v2/leagues/{league_id}/matches/{other_pm_id}/confirm-result")
check("the second result verifies", r.status_code == 200, str(body(r))[:80])

with app.app_context():
    week2 = db.session.get(LeagueWeek, week2_id)
    pms = [p for wm in week2.matchups for p in wm.player_matchups]
    check("the round 2 match now exists, with no admin opening the round again",
          len(pms) == 1, len(pms))
    if pms:
        both = {pms[0].player1_id, pms[0].player2_id}
        check("and it is the two winners",
              both == {players[winner_team], players[second_winner]},
              [names[t] for t in (winner_team, second_winner)])

check(f"{names[second_winner]} now sees round 2 as well",
      playoff_rounds_for(players[second_winner]) == [1, 2],
      playoff_rounds_for(players[second_winner]))
check(f"{names[loser_team]} still does not",
      playoff_rounds_for(players[loser_team]) == [1],
      playoff_rounds_for(players[loser_team]))

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
