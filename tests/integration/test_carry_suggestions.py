"""A bracket's deck suggestions follow it into the next round."""
import datetime
import json
import os
import sys

os.environ["TRACKER_CONFIG_PATH"] = "ENV"
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.pop("ENABLE_COLLECTOR", None)

from keytracker.server import app
from keytracker.schema import (
    CardInDeck, Deck, DeckSuggestion, DokDeck, KeyforgeHouse, KeyforgeSet, League,
    LeagueAdmin, LeagueStatus, LeagueWeek, MatchGame, PlatonicCard, PlayoffBracket,
    PodStats, Team, TeamMember, User, db,
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
TEAMS, SIZE = 4, 2

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
    league = League(name="Carry", team_size=SIZE, num_teams=TEAMS,
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
    deck_ids = []
    for n in range(30):
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
        deck_ids.append(deck.id)
    db.session.commit()
    league_id, admin_id = league.id, admin.id

c = app.test_client()
base = f"/api/v2/leagues/{league_id}/playoffs"
weeks_url = f"/api/v2/leagues/{league_id}/weeks"


def act_as(user_id):
    with c.session_transaction() as s:
        s["_user_id"] = str(user_id)
        s["_fresh"] = True


act_as(admin_id)
c.put(f"{base}/config", json={"teams_advancing": TEAMS, "points_per_round": [1, 2]})
r = c.put(f"{base}/brackets", json={"brackets": [
    {"name": "Archon", "format_type": "archon_standard"},
    {"name": "DM Sealed", "format_type": "sealed_survival",
     "decks_per_player": 5, "allowed_sets": [DM]},
]})
b_archon, b_sealed = [b["id"] for b in body(r)["brackets"]]
c.put(f"{base}/qualifiers", json={"team_ids": teams})
c.post(f"{base}/publish", json={"published": True})
for team_id in teams:
    act_as(players[team_id][0])
    c.put(f"{base}/assignments", json={"team_id": team_id, "assignments": [
        {"bracket_id": b_archon, "user_id": players[team_id][0]},
        {"bracket_id": b_sealed, "user_id": players[team_id][1]},
    ]})
act_as(admin_id)
c.post(f"{base}/assignments/publish", json={"published": True})
c.post(f"{base}/draw", json={"seed": 2})
r = c.post(f"{base}/rounds/1/start", json={})
check("round one opens both brackets", body(r).get("weeks_created") == 2,
      body(r).get("weeks_created"))
check("and carries nothing, there being no round before it",
      body(r).get("suggestions_carried") == 0, body(r).get("suggestions_carried"))

with app.app_context():
    r1 = {
        w.playoff_bracket_id: w.id
        for w in LeagueWeek.query.filter_by(league_id=league_id, playoff_round=1).all()
    }

# --- two teams shortlist decks in round one -------------------------------
# Written straight in: the add endpoint resolves a deck URL through Master
# Vault, which is not what this is testing.
with app.app_context():
    for deck_id in deck_ids[:3]:
        db.session.add(DeckSuggestion(week_id=r1[b_archon], team_id=teams[0],
                                      suggesting_user_id=players[teams[0]][0],
                                      deck_id=deck_id))
    db.session.add(DeckSuggestion(week_id=r1[b_archon], team_id=teams[1],
                                  suggesting_user_id=players[teams[1]][0],
                                  deck_id=deck_ids[5]))
    # One on the sealed bracket, which must not travel.
    db.session.add(DeckSuggestion(week_id=r1[b_sealed], team_id=teams[0],
                                  suggesting_user_id=players[teams[0]][0],
                                  deck_id=deck_ids[7]))
    db.session.commit()
    check("round one has five suggestions to start from",
          DeckSuggestion.query.count() == 5, DeckSuggestion.query.count())

# --- play round one out ---------------------------------------------------
with app.app_context():
    for bracket_id in (b_archon, b_sealed):
        bracket = db.session.get(PlayoffBracket, bracket_id)
        for m in bracket.matches:
            if m.round_number != 1 or m.is_bye or m.player_matchup_id is None:
                continue
            pm = m.player_matchup
            db.session.add(MatchGame(player_matchup_id=pm.id, game_number=1,
                                     winner_id=pm.player1_id, player1_keys=3,
                                     player2_keys=0))
            pm.result_confirmed_at = datetime.datetime.utcnow()
            pm.result_confirmed_by_id = admin_id
    db.session.commit()

act_as(admin_id)
r = c.post(f"{base}/rounds/2/start", json={})
out = body(r)
check("round two opens", out.get("weeks_created") == 2, str(out)[:90])
check("carrying the four non-sealed suggestions",
      out.get("suggestions_carried") == 4, out.get("suggestions_carried"))

with app.app_context():
    r2 = {
        w.playoff_bracket_id: w.id
        for w in LeagueWeek.query.filter_by(league_id=league_id, playoff_round=2).all()
    }
    carried = DeckSuggestion.query.filter_by(week_id=r2[b_archon]).all()
    check("the archon bracket has all four", len(carried) == 4, len(carried))
    check("team 1 keeps its three",
          len([s for s in carried if s.team_id == teams[0]]) == 3,
          [s.team_id for s in carried])
    check("and the decks are the same ones",
          sorted(s.deck_id for s in carried if s.team_id == teams[0]) == sorted(deck_ids[:3]))
    suggesters = {s.suggesting_user_id for s in carried}
    check("the original suggesters are still credited",
          suggesters == {players[teams[0]][0], players[teams[1]][0]}, suggesters)
    sealed_carried = DeckSuggestion.query.filter_by(week_id=r2[b_sealed]).all()
    check("the sealed bracket carries none, its pool being dealt afresh",
          len(sealed_carried) == 0, len(sealed_carried))
    # Round one keeps its own.
    check("round one still has its suggestions",
          DeckSuggestion.query.filter_by(week_id=r1[b_archon]).count() == 4)

# --- a team may drop one, and reopening must not bring it back ------------
act_as(players[teams[0]][0])
data = body(c.get(f"{weeks_url}/{r2[b_archon]}"))
mine = [s for s in data["deck_suggestions"] if s["team_id"] == teams[0]]
check("the captain sees the carried list on the new week", len(mine) == 3, len(mine))
r = c.delete(f"{weeks_url}/{r2[b_archon]}/deck-suggestions/{mine[0]['id']}")
check("and can drop one", r.status_code in (200, 204), str(body(r))[:80])

act_as(admin_id)
r = c.post(f"{base}/rounds/2/start", json={})
check("reopening the round carries nothing again",
      body(r).get("suggestions_carried") == 0, body(r).get("suggestions_carried"))
with app.app_context():
    check("so the dropped suggestion stays dropped",
          DeckSuggestion.query.filter_by(week_id=r2[b_archon]).count() == 3,
          DeckSuggestion.query.filter_by(week_id=r2[b_archon]).count())

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
