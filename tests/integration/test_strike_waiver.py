"""A Triad match can be reported when the opponent never strikes."""
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


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + str(detail)) if detail else ''}")
    if not ok:
        FAIL.append(label)


def body(r):
    try:
        return json.loads(r.data)
    except Exception:
        return {"raw": r.data[:200].decode("utf-8", "replace")}


DM = 928

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
    league = League(name="Waiver", team_size=2, num_teams=2,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))
    users, teams = {}, []
    for i, (label, names) in enumerate(
        (("A", ("CapA", "Quiet")), ("B", ("CapB", "Waiting")))
    ):
        team = Team(league_id=league.id, name=f"Team {label}", order_number=i + 1)
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
        league_id=league.id, week_number=1, name="Triad", format_type="triad",
        best_of_n=3, status=WeekStatus.PUBLISHED.value,
        allowed_sets=json.dumps([DM]),
    )
    db.session.add(week)
    db.session.flush()
    import datetime
    now = datetime.datetime.utcnow()
    sels, decks = {}, {}
    for name in ("Quiet", "Waiting"):
        sels[name], decks[name] = [], []
        for n in range(3):
            kf = str(uuid.uuid4())
            deck = Deck(name=f"{name} deck {n}", kf_id=kf, expansion=DM)
            db.session.add(deck)
            db.session.flush()
            db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0, last_refresh=now))
            for h in hid.values():
                db.session.add(PodStats(deck_id=deck.id, kf_house_id=h))
            card = PlatonicCard(card_title=f"Filler {name}{n}")
            db.session.add(card)
            db.session.flush()
            db.session.add(CardInDeck(deck_id=deck.id, platonic_card_id=card.id))
            sel = PlayerDeckSelection(week_id=week.id, user_id=users[name],
                                      deck_id=deck.id, slot_number=n + 1)
            db.session.add(sel)
            db.session.flush()
            sels[name].append(sel.id)
            decks[name].append(deck.id)
    wm = WeekMatchup(week_id=week.id, team1_id=teams[0], team2_id=teams[1])
    db.session.add(wm)
    db.session.flush()
    pm = PlayerMatchup(week_matchup_id=wm.id, player1_id=users["Quiet"],
                       player2_id=users["Waiting"])
    db.session.add(pm)
    db.session.commit()
    league_id, pm_id = league.id, pm.id

c = app.test_client()
base = f"/api/v2/leagues/{league_id}/matches/{pm_id}"


def act_as(uid):
    with c.session_transaction() as s:
        s["_user_id"] = str(uid)
        s["_fresh"] = True


for name in ("Quiet", "Waiting"):
    act_as(users[name])
    c.post(f"{base}/start")

# --- you cannot waive before doing your own part ------------------------
act_as(users["Waiting"])
r = c.post(f"{base}/strike-not-recorded")
check("you cannot waive before making your own strike",
      r.status_code == 400 and "your own strike" in str(body(r).get("error")),
      body(r).get("error"))

r = c.post(f"{base}/strike", json={"struck_deck_selection_id": sels["Quiet"][0]})
check("Waiting strikes", r.status_code == 200, str(body(r))[:60])

# --- somebody outside the match cannot waive ----------------------------
act_as(users["CapB"])
act_as(admin.id if False else users["CapB"])
r = c.post(f"{base}/strike-not-recorded")
check("their own captain can, being a captain", r.status_code == 200,
      str(body(r))[:60])

with app.app_context():
    pm = db.session.get(PlayerMatchup, pm_id)
    pm.strike_not_recorded = False
    db.session.commit()

act_as(users["Waiting"])
r = c.post(f"{base}/strike-not-recorded")
check("and so can the player left waiting", r.status_code == 200,
      str(body(r))[:60])
check("the matchup says so", body(r).get("strike_not_recorded") is True,
      body(r).get("strike_not_recorded"))

# --- the waiver does not un-strike anything -----------------------------
# Checked before the match is decided: the second win completes the week, and
# after that a game is refused for being late rather than for being illegal.
act_as(users["Waiting"])
r = c.post(f"{base}/games", json={
    "winner_id": users["Waiting"], "game_number": 1,
    "player1_keys": 1, "player2_keys": 3,
    "player1_deck_id": decks["Quiet"][0],
    "player2_deck_id": decks["Waiting"][0],
})
check("the deck that was struck is still unplayable",
      r.status_code == 400 and "stricken" in str(body(r).get("error")),
      body(r).get("error"))

# --- which is what makes the match reportable ---------------------------
act_as(users["Waiting"])
wins = 0
for n in range(2):
    r = c.post(f"{base}/games", json={
        "winner_id": users["Waiting"], "game_number": n + 1,
        "player1_keys": 1, "player2_keys": 3,
        "player1_deck_id": decks["Quiet"][n + 1],
        "player2_deck_id": decks["Waiting"][n],
    })
    if r.status_code in (200, 201):
        wins += 1
    else:
        print("      report error:", body(r).get("error"))
check("both games report with only one strike in", wins == 2, wins)

act_as(users["CapB"])
r = c.post(f"{base}/confirm-result")
check("and the captain can verify the result", r.status_code == 200,
      str(body(r))[:60])

# --- it cannot be used once both strikes are in -------------------------
with app.app_context():
    from keytracker.schema import StrikeSelection
    pm = db.session.get(PlayerMatchup, pm_id)
    db.session.add(StrikeSelection(
        player_matchup_id=pm.id, striking_user_id=users["Quiet"],
        struck_deck_selection_id=sels["Waiting"][2],
    ))
    pm.strike_not_recorded = False
    db.session.commit()
act_as(users["Waiting"])
r = c.post(f"{base}/strike-not-recorded")
check("with both strikes in there is nothing to waive",
      r.status_code == 400 and "already in" in str(body(r).get("error")),
      body(r).get("error"))

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
