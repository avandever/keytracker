"""Double Oubliette is won one game per legal set, not one per deck.

So a set is finished once any of its decks has won, and a combined SAS cap
applies wherever it is declared rather than only in Triad.
"""
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
    LeagueStatus, LeagueWeek, OublietteBan, PlatonicCard, PlayerDeckSelection,
    PlayerMatchup, PodStats, Team, TeamMember, User, WeekMatchup, WeekStatus, db,
)

FAIL = []
WoE = 886
ToC = 341


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
    for number, name in ((WoE, "Winds of Exchange"), (ToC, "Call of the Archons")):
        db.session.add(KeyforgeSet(number=number, name=name,
                                   shortname=name[:3], dokname=name[:3]))
    houses = {}
    for name in ("Mars", "Logos", "Untamed", "Shadows"):
        h = KeyforgeHouse(name=name)
        db.session.add(h)
        db.session.flush()
        houses[name] = h.id
    admin = User(email="admin@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="Oubs", team_size=1, num_teams=2,
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
        league_id=league.id, week_number=1, name="Doubliette",
        format_type="double_oubliette", best_of_n=5,
        status=WeekStatus.PUBLISHED.value,
        allowed_sets=json.dumps([WoE, ToC]),
    )
    db.session.add(week)
    db.session.flush()
    now = datetime.datetime.utcnow()
    decks = {}
    # Two per set each, none sharing the house the opponent will ban.
    for name in ("Ann", "Bob"):
        decks[name] = {}
        for expansion in (WoE, ToC):
            decks[name][expansion] = []
            for n in range(2):
                kf = str(uuid.uuid4())
                deck = Deck(name=f"{name} {expansion} {n}", kf_id=kf,
                            expansion=expansion)
                db.session.add(deck)
                db.session.flush()
                db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0,
                                       last_refresh=now))
                for h in ("Mars", "Logos", "Untamed"):
                    db.session.add(PodStats(deck_id=deck.id, kf_house_id=houses[h]))
                card = PlatonicCard(card_title=f"F{name}{expansion}{n}")
                db.session.add(card)
                db.session.flush()
                db.session.add(CardInDeck(deck_id=deck.id, platonic_card_id=card.id))
                sel = PlayerDeckSelection(
                    week_id=week.id, user_id=users[name], deck_id=deck.id,
                    slot_number=len(decks[name][WoE]) + len(decks[name].get(ToC, []))
                    + 1 + (2 if expansion == ToC else 0),
                )
                db.session.add(sel)
                db.session.flush()
                decks[name][expansion].append(deck.id)

    # Bans that kill nothing: Shadows is in no deck here.
    for name in ("Ann", "Bob"):
        for expansion in (WoE, ToC):
            db.session.add(OublietteBan(
                week_id=week.id, user_id=users[name], expansion=expansion,
                banned_house="Shadows",
            ))
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

act_as(users["Ann"])
r = c.post(f"{base}/games", json={
    "winner_id": users["Ann"], "game_number": 1,
    "player1_keys": 3, "player2_keys": 0,
    "player1_deck_id": decks["Ann"][WoE][0],
    "player2_deck_id": decks["Bob"][WoE][0],
})
check("Ann wins a game with her first WoE deck", r.status_code in (200, 201),
      str(body(r))[:80])

# --- the set is finished, not just that deck -----------------------------
r = c.post(f"{base}/games", json={
    "winner_id": users["Ann"], "game_number": 2,
    "player1_keys": 3, "player2_keys": 0,
    "player1_deck_id": decks["Ann"][WoE][1],
    "player2_deck_id": decks["Bob"][ToC][0],
})
check("her other WoE deck cannot win the next, that set being done",
      r.status_code == 400 and "set" in str(body(r).get("error", "")),
      (r.status_code, body(r).get("error")))

# --- the other set still has to be won -----------------------------------
r = c.post(f"{base}/games", json={
    "winner_id": users["Ann"], "game_number": 2,
    "player1_keys": 3, "player2_keys": 0,
    "player1_deck_id": decks["Ann"][ToC][0],
    "player2_deck_id": decks["Bob"][ToC][0],
})
check("her deck from the other set can", r.status_code in (200, 201),
      str(body(r))[:80])

# --- and what is offered matches what is accepted ------------------------
with app.app_context():
    from keytracker.match_helpers import playable_deck_ids
    from keytracker.schema import WeekFormat
    pm = db.session.get(PlayerMatchup, pm_id)
    playable = playable_deck_ids(pm, WeekFormat.DOUBLE_OUBLIETTE, pm.games, 3)
    check("neither of Ann's sets is still on offer, both being won",
          playable is not None and playable["p1"] == [], playable)
    check("and Bob, who has won nothing, keeps all four",
          playable is not None and len(playable["p2"]) == 4, playable)

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
