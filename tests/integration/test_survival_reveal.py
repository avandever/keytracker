"""Sealed Survival shows the opponent's keeps, but only once both have kept."""
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
    LeagueStatus, LeagueWeek, PlatonicCard, PlayerMatchup, PodStats,
    SealedPoolDeck, Team, TeamMember, User, WeekMatchup, WeekStatus, db,
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
POOL = 5

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
    league = League(name="Survival", team_size=1, num_teams=2,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))
    teams, players = [], {}
    for i, label in enumerate("AB"):
        team = Team(league_id=league.id, name=f"Team {label}", order_number=i + 1)
        db.session.add(team)
        db.session.flush()
        u = User(email=f"{label}@e.com", name=f"Player {label}")
        db.session.add(u)
        db.session.flush()
        db.session.add(TeamMember(team_id=team.id, user_id=u.id, is_captain=True))
        teams.append(team.id)
        players[team.id] = u.id

    week = LeagueWeek(
        league_id=league.id, week_number=1, name="Survival",
        format_type="sealed_survival", best_of_n=3,
        status=WeekStatus.PUBLISHED.value, decks_per_player=POOL,
        allowed_sets=json.dumps([DM]), sealed_pools_generated=True,
    )
    db.session.add(week)
    db.session.flush()
    now = datetime.datetime.utcnow()
    pools = {}
    for t in teams:
        pools[t] = []
        for n in range(POOL):
            kf = str(uuid.uuid4())
            deck = Deck(name=f"deck {t}-{n}", kf_id=kf, expansion=DM)
            db.session.add(deck)
            db.session.flush()
            db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0, last_refresh=now))
            for h in hid.values():
                db.session.add(PodStats(deck_id=deck.id, kf_house_id=h))
            card = PlatonicCard(card_title=f"Filler {t}-{n}")
            db.session.add(card)
            db.session.flush()
            db.session.add(CardInDeck(deck_id=deck.id, platonic_card_id=card.id))
            db.session.add(SealedPoolDeck(week_id=week.id, user_id=players[t],
                                          deck_id=deck.id))
            pools[t].append(deck.id)
    wm = WeekMatchup(week_id=week.id, team1_id=teams[0], team2_id=teams[1])
    db.session.add(wm)
    db.session.flush()
    pm = PlayerMatchup(week_matchup_id=wm.id, player1_id=players[teams[0]],
                       player2_id=players[teams[1]])
    db.session.add(pm)
    db.session.commit()
    league_id, week_id, pm_id = league.id, week.id, pm.id
    p1, p2 = players[teams[0]], players[teams[1]]
    p1_pool, p2_pool = pools[teams[0]], pools[teams[1]]

c = app.test_client()


def act_as(uid):
    with c.session_transaction() as s:
        s["_user_id"] = str(uid)
        s["_fresh"] = True


def their_visible_decks(viewer, other):
    act_as(viewer)
    d = body(c.get(f"/api/v2/leagues/{league_id}"))
    wk = next(w for w in d["weeks"] if w["id"] == week_id)
    return [
        ds["deck"] and ds["deck"]["db_id"]
        for ds in wk["deck_selections"]
        if ds["user_id"] == other
    ]


def keep(uid, deck_ids):
    act_as(uid)
    out = []
    for slot, deck_id in enumerate(deck_ids, start=1):
        r = c.post(
            f"/api/v2/leagues/{league_id}/weeks/{week_id}/deck-selection",
            json={"deck_id": deck_id, "slot_number": slot},
        )
        out.append(r.status_code)
    return out


print("  player A keeps two, player B has not yet")
print("   ", keep(p1, p1_pool[:2]))
check("B cannot see A's keeps while B is still choosing",
      their_visible_decks(p2, p1) == [None, None],
      their_visible_decks(p2, p1))
check("and A cannot see B's, there being none", their_visible_decks(p1, p2) == [],
      their_visible_decks(p1, p2))

print("  player B keeps two")
print("   ", keep(p2, p2_pool[:2]))
check("now A sees B's two", their_visible_decks(p1, p2) == p2_pool[:2],
      their_visible_decks(p1, p2))
check("and B sees A's two", their_visible_decks(p2, p1) == p1_pool[:2],
      their_visible_decks(p2, p1))

# --- which is what makes the game reportable ----------------------------
act_as(p1)
r = c.post(
    f"/api/v2/leagues/{league_id}/matches/{pm_id}/games",
    json={"winner_id": p1, "game_number": 1, "player1_keys": 3, "player2_keys": 1,
          "player1_deck_id": p1_pool[0], "player2_deck_id": p2_pool[0]},
)
check("a game naming both decks reports", r.status_code in (200, 201),
      str(body(r))[:110])

check("and the losing deck is out of the match",
      their_visible_decks(p1, p2) == p2_pool[:2], their_visible_decks(p1, p2))

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
