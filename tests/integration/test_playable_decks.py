"""The formats that name a deck per game say which decks may be named."""
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
    CardInDeck, Deck, DokDeck, ExchangeBorrow, KeyforgeHouse, KeyforgeSet,
    League, LeagueAdmin, LeagueStatus, LeagueWeek, PlatonicCard,
    PlayerDeckSelection, PlayerMatchup, PodStats, Team, TeamMember, User,
    WeekMatchup, WeekStatus, db,
)

FAIL = []
CotA = 341
PV = 886


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
    for number, name in ((CotA, "Call of the Archons"), (PV, "Prophetic Visions")):
        db.session.add(KeyforgeSet(number=number, name=name,
                                   shortname=name[:3], dokname=name[:3]))
    hid = {}
    for name in ("Mars", "Logos", "Untamed"):
        h = KeyforgeHouse(name=name)
        db.session.add(h)
        db.session.flush()
        hid[name] = h.id
    admin = User(email="admin@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="Exchange", team_size=1, num_teams=2,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))
    users, teams = {}, []
    for i, name in enumerate(("Ann", "Bob")):
        team = Team(league_id=league.id, name=f"Team {name}", order_number=i + 1)
        db.session.add(team)
        db.session.flush()
        teams.append(team.id)
        u = User(email=f"{name}@e.com", name=name)
        db.session.add(u)
        db.session.flush()
        db.session.add(TeamMember(team_id=team.id, user_id=u.id, is_captain=True))
        users[name] = u.id

    week = LeagueWeek(
        league_id=league.id, week_number=1, name="Exchange",
        format_type="exchange", best_of_n=3,
        status=WeekStatus.PUBLISHED.value, allowed_sets=json.dumps([CotA, PV]),
    )
    db.session.add(week)
    db.session.flush()
    now = datetime.datetime.utcnow()
    sels, decks = {}, {}
    for name in ("Ann", "Bob"):
        sels[name], decks[name] = [], []
        for slot, expansion in ((1, PV), (2, CotA)):
            kf = str(uuid.uuid4())
            deck = Deck(name=f"{name} {slot}", kf_id=kf, expansion=expansion)
            db.session.add(deck)
            db.session.flush()
            db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0, last_refresh=now))
            for h in hid.values():
                db.session.add(PodStats(deck_id=deck.id, kf_house_id=h))
            card = PlatonicCard(card_title=f"Filler {name}{slot}")
            db.session.add(card)
            db.session.flush()
            db.session.add(CardInDeck(deck_id=deck.id, platonic_card_id=card.id))
            sel = PlayerDeckSelection(week_id=week.id, user_id=users[name],
                                      deck_id=deck.id, slot_number=slot)
            db.session.add(sel)
            db.session.flush()
            sels[name].append(sel.id)
            decks[name].append(deck.id)
    wm = WeekMatchup(week_id=week.id, team1_id=teams[0], team2_id=teams[1])
    db.session.add(wm)
    db.session.flush()
    pm = PlayerMatchup(week_matchup_id=wm.id, player1_id=users["Ann"],
                       player2_id=users["Bob"])
    db.session.add(pm)
    db.session.commit()
    league_id, pm_id, week_id = league.id, pm.id, week.id

c = app.test_client()
base = f"/api/v2/leagues/{league_id}/matches/{pm_id}"


def act_as(uid):
    with c.session_transaction() as s:
        s["_user_id"] = str(uid)
        s["_fresh"] = True


def playable():
    act_as(users["Ann"])
    d = body(c.get(f"/api/v2/leagues/{league_id}/my-info"))
    for w in d.get("weeks") or []:
        for m in w.get("matchups") or []:
            for p in m.get("player_matchups") or []:
                if p["id"] == pm_id:
                    return p.get("playable_deck_ids")
    return "matchup not found"


for name in ("Ann", "Bob"):
    act_as(users[name])
    c.post(f"{base}/start")

check("before the borrows, there is nothing to offer", playable() is None,
      playable())

# Each secretly names one of the opponent's decks to borrow -- through the
# endpoint, since until now the only way in was the standalone match page.
act_as(users["Ann"])
r = c.post(f"{base}/exchange-borrow",
           json={"borrowed_deck_selection_id": sels["Bob"][0]})
check("a player can submit their borrow", r.status_code == 200,
      str(body(r))[:80])
check("and is told their own is in, while the other stays secret",
      body(r).get("my_exchange_borrow") == sels["Bob"][0]
      and body(r).get("exchange_borrows") is None,
      (body(r).get("my_exchange_borrow"), body(r).get("exchange_borrows")))

# Bob has gone quiet, so his captain enters it for him. Bob is the only
# member of his team here, so the captain is his opponent's -- give Bob a
# captain of his own to stand in.
with app.app_context():
    cap = User(email="cap@e.com", name="BobsCap")
    db.session.add(cap)
    db.session.flush()
    db.session.add(TeamMember(team_id=teams[1], user_id=cap.id, is_captain=True))
    db.session.commit()
    cap_id = cap.id

act_as(cap_id)
r = c.post(f"{base}/exchange-borrow",
           json={"borrowed_deck_selection_id": sels["Ann"][1]})
check("a captain can enter it for their own player", r.status_code == 200,
      str(body(r))[:80])
check("and the answer credits the player, not the captain",
      body(r).get("my_exchange_borrow") == sels["Ann"][1],
      body(r).get("my_exchange_borrow"))

# --- and the other team's captain may record it too ---------------------
with app.app_context():
    from keytracker.schema import ExchangeBorrow as EB
    EB.query.filter_by(player_matchup_id=pm_id,
                       borrowing_user_id=users["Bob"]).delete()
    db.session.commit()

act_as(users["Ann"])  # Ann captains the other team
r = c.post(f"{base}/exchange-borrow",
           json={"borrowed_deck_selection_id": sels["Ann"][1],
                 "for_user_id": users["Bob"]})
check("the opposing captain can record it when named",
      r.status_code == 200, str(body(r))[:80])
with app.app_context():
    from keytracker.schema import ExchangeBorrow as EB, LeagueAdminLog
    owner = EB.query.filter_by(player_matchup_id=pm_id).filter(
        EB.borrowing_user_id == users["Bob"]).first()
    check("recorded against the player it belongs to", owner is not None)
    logged = LeagueAdminLog.query.filter_by(
        action_type="exchange_borrow_entered_for_player"
    ).count()
    check("and logged, so who entered it is on the record", logged >= 1, logged)

r = c.post(f"{base}/exchange-borrow",
           json={"borrowed_deck_selection_id": sels["Ann"][0],
                 "for_user_id": 99999})
check("a player outside the match cannot be named",
      r.status_code == 400, body(r).get("error"))

got = playable()
check("once both have borrowed, each side has two decks",
      isinstance(got, dict) and len(got.get("p1", [])) == 2
      and len(got.get("p2", [])) == 2, got)

# Ann plays her own slot-1 deck and the one she borrowed from Bob.
expected_p1 = {decks["Ann"][0], decks["Bob"][0]}
check("and they are the player's own plus the borrowed one",
      set(got["p1"]) == expected_p1, (got.get("p1"), sorted(expected_p1)))

# --- and what is offered is what the endpoint accepts -------------------
act_as(users["Ann"])
r = c.post(f"{base}/games", json={
    "winner_id": users["Ann"], "game_number": 1,
    "player1_keys": 3, "player2_keys": 0,
    "player1_deck_id": got["p1"][0], "player2_deck_id": got["p2"][0],
})
check("a game reports with a deck from the offered list",
      r.status_code in (200, 201), str(body(r))[:90])

after = playable()
check("the deck that just won drops out, both having to win",
      got["p1"][0] not in (after or {}).get("p1", []), after)

# --- a deck outside the pool is still refused ---------------------------
r = c.post(f"{base}/games", json={
    "winner_id": users["Ann"], "game_number": 2,
    "player1_keys": 3, "player2_keys": 0,
    "player1_deck_id": decks["Ann"][1], "player2_deck_id": got["p2"][0],
})
check("a deck outside the exchange pool is refused",
      r.status_code == 400 and "pool" in str(body(r).get("error")),
      body(r).get("error"))

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
