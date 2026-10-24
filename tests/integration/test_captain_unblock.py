"""A captain can make a stalled player's strike, and Triad decks are visible."""
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
    league = League(name="Triad", team_size=2, num_teams=2,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))

    # Team A: a captain and a player who will go quiet. Team B: the opponent.
    users = {}
    teams = []
    for i, (label, names) in enumerate(
        (("A", ("Captain", "Quiet")), ("B", ("Opponent", "Spare")))
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
    now = datetime.datetime.utcnow()
    sels = {}
    for name in ("Quiet", "Opponent"):
        sels[name] = []
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
            sel = PlayerDeckSelection(
                week_id=week.id, user_id=users[name], deck_id=deck.id,
                slot_number=n + 1,
            )
            db.session.add(sel)
            db.session.flush()
            sels[name].append(sel.id)
    wm = WeekMatchup(week_id=week.id, team1_id=teams[0], team2_id=teams[1])
    db.session.add(wm)
    db.session.flush()
    pm = PlayerMatchup(week_matchup_id=wm.id, player1_id=users["Quiet"],
                       player2_id=users["Opponent"])
    db.session.add(pm)
    db.session.commit()
    league_id, week_id, pm_id = league.id, week.id, pm.id

c = app.test_client()


def act_as(uid):
    with c.session_transaction() as s:
        s["_user_id"] = str(uid)
        s["_fresh"] = True


def their_decks(viewer, other):
    act_as(users[viewer])
    d = body(c.get(f"/api/v2/leagues/{league_id}"))
    wk = next(w for w in d["weeks"] if w["id"] == week_id)
    return [
        (ds["deck"] or {}).get("name")
        for ds in wk["deck_selections"]
        if ds["user_id"] == users[other]
    ]


check("before either starts, the opponent's three are hidden",
      their_decks("Quiet", "Opponent") == [None, None, None],
      their_decks("Quiet", "Opponent"))

for name in ("Quiet", "Opponent"):
    act_as(users[name])
    c.post(f"/api/v2/leagues/{league_id}/matches/{pm_id}/start")

check("once both have started, Quiet can read the opponent's decks",
      all(their_decks("Quiet", "Opponent")), their_decks("Quiet", "Opponent"))
check("and the opponent can read Quiet's",
      all(their_decks("Opponent", "Quiet")), their_decks("Opponent", "Quiet"))

# --- the opponent strikes, and then Quiet stops answering ----------------
act_as(users["Opponent"])
r = c.post(f"/api/v2/leagues/{league_id}/matches/{pm_id}/strike",
           json={"struck_deck_selection_id": sels["Quiet"][0]})
check("the opponent strikes", r.status_code == 200, str(body(r))[:70])

act_as(users["Spare"])
r = c.post(f"/api/v2/leagues/{league_id}/matches/{pm_id}/strike",
           json={"struck_deck_selection_id": sels["Opponent"][0]})
check("a teammate who is not captain still cannot step in",
      r.status_code == 403, body(r).get("error"))

act_as(users["Captain"])
r = c.post(f"/api/v2/leagues/{league_id}/matches/{pm_id}/strike",
           json={"struck_deck_selection_id": sels["Opponent"][2]})
check("the captain can make the strike their player owes",
      r.status_code == 200, str(body(r))[:70])

with app.app_context():
    pm = db.session.get(PlayerMatchup, pm_id)
    by = {s.striking_user_id: s.struck_deck_selection_id for s in pm.strikes}
    check("and it is recorded as the player's, not the captain's",
          users["Quiet"] in by and users["Captain"] not in by, list(by))
    check("against the deck the captain chose",
          by.get(users["Quiet"]) == sels["Opponent"][2], by)

# --- and the captain of the other team cannot strike for our player ------
act_as(users["Opponent"])
r = c.post(f"/api/v2/leagues/{league_id}/matches/{pm_id}/strike",
           json={"struck_deck_selection_id": sels["Quiet"][1]})
check("the other side's captain gets no second strike",
      r.status_code == 400 and "already" in str(body(r).get("error")),
      body(r).get("error"))

# --- the captain finishes the report -------------------------------------
with app.app_context():
    alive = {}
    for name, struck in (("Quiet", sels["Quiet"][0]), ("Opponent", sels["Opponent"][2])):
        alive[name] = [
            db.session.get(PlayerDeckSelection, sid).deck_id
            for sid in sels[name]
            if sid != struck
        ]

act_as(users["Captain"])
for n in range(2):
    r = c.post(f"/api/v2/leagues/{league_id}/matches/{pm_id}/games",
               json={"winner_id": users["Quiet"], "game_number": n + 1,
                     "player1_keys": 3, "player2_keys": 1,
                     "player1_deck_id": alive["Quiet"][n],
                     "player2_deck_id": alive["Opponent"][n]})
    check(f"the captain reports game {n + 1}", r.status_code in (200, 201),
          str(body(r))[:70])
r = c.post(f"/api/v2/leagues/{league_id}/matches/{pm_id}/confirm-result")
check("and verifies the result", r.status_code == 200, str(body(r))[:70])

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
