"""A deck played in a playoff round is spent for the rest of the playoffs.

Across brackets and across players, not merely within one bracket -- the
rounds are numbered weeks like any other, and a bracket is not a world of
its own. Sealed pools stay exempt, as they are everywhere.
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
    LeagueStatus, LeagueWeek, PlatonicCard, PlayoffBracket, PlayoffMatch,
    PodStats, SealedPoolDeck, Team, TeamMember, User, WeekStatus, db,
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
    hid = {}
    for name in ("Mars", "Logos", "Untamed"):
        h = KeyforgeHouse(name=name)
        db.session.add(h)
        db.session.flush()
        hid[name] = h.id
    admin = User(email="admin@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="Reuse", team_size=2, num_teams=2,
                    status=LeagueStatus.PLAYOFFS.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))

    users, teams = {}, []
    for i, names in enumerate((("Ann", "Abe"), ("Bea", "Ben"))):
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

    brackets = []
    for n, fmt in ((1, "archon_standard"), (2, "archon_standard")):
        b = PlayoffBracket(league_id=league.id, bracket_number=n,
                           name=f"Bracket {n}", format_type=fmt, best_of_n=3)
        db.session.add(b)
        db.session.flush()
        brackets.append(b.id)

    db.session.add(PlayoffMatch(bracket_id=brackets[0], round_number=1,
                                slot_index=0, team1_id=teams[0],
                                team2_id=teams[1]))
    db.session.add(PlayoffMatch(bracket_id=brackets[1], round_number=2,
                                slot_index=0, team1_id=teams[0],
                                team2_id=teams[1]))

    # Round 1 of bracket 1, round 2 of bracket 2, and a season week to show
    # the two competitions stay separate.
    weeks = {}
    specs = [
        ("season", None, None, 1, "archon_standard"),
        ("r1b1", brackets[0], 1, 2, "archon_standard"),
        ("r2b2", brackets[1], 2, 3, "archon_standard"),
        ("sealed_r1", brackets[0], 1, 4, "sealed_archon"),
    ]
    for key, bracket_id, rnd, number, fmt in specs:
        w = LeagueWeek(
            league_id=league.id, week_number=number, name=key, format_type=fmt,
            best_of_n=3, status=WeekStatus.DECK_SELECTION.value,
            allowed_sets=json.dumps([DM]), playoff_bracket_id=bracket_id,
            playoff_round=rnd, decks_per_player=4,
        )
        db.session.add(w)
        db.session.flush()
        weeks[key] = w.id

    now = datetime.datetime.utcnow()
    urls = {}
    for label in ("one", "two", "three"):
        kf = str(uuid.uuid4())
        deck = Deck(name=f"deck {label}", kf_id=kf, expansion=DM)
        db.session.add(deck)
        db.session.flush()
        db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0, last_refresh=now))
        for h in hid.values():
            db.session.add(PodStats(deck_id=deck.id, kf_house_id=h))
        card = PlatonicCard(card_title=f"Filler {label}")
        db.session.add(card)
        db.session.flush()
        db.session.add(CardInDeck(deck_id=deck.id, platonic_card_id=card.id))
        urls[label] = f"https://decksofkeyforge.com/decks/{kf}"
    db.session.commit()
    league_id = league.id

c = app.test_client()


def act_as(uid):
    with c.session_transaction() as s:
        s["_user_id"] = str(uid)
        s["_fresh"] = True


def submit(who, week_key, deck_label, slot=1):
    act_as(users[who])
    return c.post(
        f"/api/v2/leagues/{league_id}/weeks/{weeks[week_key]}/deck-selection",
        json={"deck_url": urls[deck_label], "slot_number": slot},
    )


# --- played in round 1 of bracket 1 --------------------------------------
r = submit("Ann", "r1b1", "one")
check("a deck goes into round 1", r.status_code in (200, 201), str(body(r))[:70])

# --- the same player, round 2, a different bracket ------------------------
r = submit("Ann", "r2b2", "one")
# 409 is what a cross-week conflict answers with, not 400.
check("the same player cannot bring it back in round 2 of another bracket",
      r.status_code == 409 and "already used" in str(body(r).get("error", "")),
      (r.status_code, body(r).get("error")))

# --- a teammate, round 2, a different bracket -----------------------------
r = submit("Abe", "r2b2", "one")
check("nor can a teammate",
      r.status_code == 409, (r.status_code, body(r).get("error")))

# --- someone on the other team entirely -----------------------------------
r = submit("Bea", "r2b2", "one")
check("nor can anyone on the other team",
      r.status_code == 409, (r.status_code, body(r).get("error")))

# --- a fresh deck is fine -------------------------------------------------
r = submit("Bea", "r2b2", "two")
check("a deck not yet played goes in", r.status_code in (200, 201),
      str(body(r))[:70])

# --- and the other way round, which week order used to let through --------
# Bea holds "two" in week 3. Abe now claims it for week 2, a LOWER number.
# He is on the other team from her, so the teammate rule has nothing to say
# and this is the new rule alone: whoever reached the lower-numbered week
# used to win the race regardless of who was there first.
r = submit("Abe", "r1b1", "two")
check("a deck held in a later-numbered week cannot be taken for an earlier one",
      r.status_code == 409 and "already selected for" in str(body(r).get("error", "")),
      (r.status_code, body(r).get("error")))

# --- the season stays a separate competition ------------------------------
r = submit("Ann", "season", "one")
check("a playoff deck is still free for a season week",
      r.status_code in (200, 201), str(body(r))[:70])

# --- sealed pools are exempt in both directions ---------------------------
with app.app_context():
    pool_deck = Deck.query.filter_by(name="deck three").first()
    db.session.add(SealedPoolDeck(week_id=weeks["sealed_r1"],
                                  user_id=users["Abe"], deck_id=pool_deck.id))
    db.session.commit()
    pool_deck_id = pool_deck.id

act_as(users["Abe"])
r = c.post(
    f"/api/v2/leagues/{league_id}/weeks/{weeks['sealed_r1']}/deck-selection",
    json={"deck_id": pool_deck_id, "slot_number": 1},
)
check("a deck goes into a sealed playoff week",
      r.status_code in (200, 201), str(body(r))[:70])
r = submit("Abe", "r2b2", "three")
check("and a sealed pool deck does not spend it for later rounds",
      r.status_code in (200, 201), str(body(r))[:70])

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
