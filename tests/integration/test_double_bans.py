"""Double Oubliette bans: one per set, set and cleared independently."""
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
    LeagueStatus, LeagueWeek, OublietteBan, PlatonicCard, PlayerDeckSelection,
    PodStats, Team, TeamMember, User, WeekStatus, db,
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


WOE, TOC = 886, 907

with app.app_context():
    db.drop_all()
    db.create_all()
    db.session.add(KeyforgeSet(number=WOE, name="Winds of Exchange",
                               shortname="WoE", dokname="WoE"))
    db.session.add(KeyforgeSet(number=TOC, name="Tokens of Change",
                               shortname="ToC", dokname="ToC"))
    house_ids = {}
    for name in ("Brobnar", "Dis", "Logos", "Mars", "Shadows", "Untamed"):
        h = KeyforgeHouse(name=name)
        db.session.add(h)
        db.session.flush()
        house_ids[name] = h.id

    admin = User(email="a@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="DO", team_size=2, num_teams=2,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))
    team = Team(league_id=league.id, name="T1", order_number=1)
    db.session.add(team)
    db.session.flush()
    captain = User(email="c@e.com", name="Cap")
    mate = User(email="m@e.com", name="Mate")
    db.session.add_all([captain, mate])
    db.session.flush()
    db.session.add(TeamMember(team_id=team.id, user_id=captain.id, is_captain=True))
    db.session.add(TeamMember(team_id=team.id, user_id=mate.id))

    now = datetime.datetime.utcnow()

    def make_deck(name, expansion, houses):
        deck = Deck(name=name, kf_id=name.ljust(32, "x")[:32], expansion=expansion)
        db.session.add(deck)
        db.session.flush()
        db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0, last_refresh=now))
        for h in houses:
            db.session.add(PodStats(deck_id=deck.id, kf_house_id=house_ids[h]))
        card = PlatonicCard(card_title=f"Filler {name}")
        db.session.add(card)
        db.session.flush()
        db.session.add(CardInDeck(deck_id=deck.id, platonic_card_id=card.id))
        db.session.flush()
        return deck

    woe_deck = make_deck("woe", WOE, ["Brobnar", "Dis", "Logos"])
    toc_deck = make_deck("toc", TOC, ["Mars", "Shadows", "Untamed"])

    week = LeagueWeek(league_id=league.id, week_number=1, name="Double",
                      format_type="double_oubliette", best_of_n=3,
                      status=WeekStatus.DECK_SELECTION.value,
                      allowed_sets=json.dumps([WOE, TOC]))
    db.session.add(week)
    db.session.flush()
    db.session.add(PlayerDeckSelection(week_id=week.id, user_id=captain.id,
                                       deck_id=woe_deck.id, slot_number=1))
    db.session.add(PlayerDeckSelection(week_id=week.id, user_id=captain.id,
                                       deck_id=toc_deck.id, slot_number=2))
    db.session.commit()
    league_id, week_id = league.id, week.id
    captain_id, mate_id = captain.id, mate.id

c = app.test_client()
ban_url = f"/api/v2/leagues/{league_id}/weeks/{week_id}/oubliette-ban"


def act_as(user_id):
    with c.session_transaction() as s:
        s["_user_id"] = str(user_id)
        s["_fresh"] = True


act_as(captain_id)

# --- the window is open during deck selection -----------------------------
r = c.post(ban_url, json={"banned_house": "Mars", "expansion": WOE})
check("a ban can be set during deck selection", r.status_code == 200, body(r))

r = c.post(ban_url, json={"banned_house": "Brobnar", "expansion": TOC})
check("and one for the other set", r.status_code == 200, body(r))

with app.app_context():
    bans = {b.expansion: b.banned_house
            for b in OublietteBan.query.filter_by(week_id=week_id, user_id=captain_id)}
    check("both are stored, one per set",
          bans == {WOE: "Mars", TOC: "Brobnar"}, bans)

# --- the rule about your own decks still holds, per set -------------------
r = c.post(ban_url, json={"banned_house": "Dis", "expansion": WOE})
check("a house in your own deck from that set is refused",
      r.status_code == 400, body(r))
# A ban is committed once made, so changing one means clearing it first --
# which is exactly what the Change button does.
r = c.post(ban_url, json={"banned_house": "Logos", "expansion": TOC})
check("an existing ban is not silently overwritten",
      r.status_code == 400 and "already banned" in str(body(r)), body(r))
c.delete(f"{ban_url}?expansion={TOC}")
r = c.post(ban_url, json={"banned_house": "Dis", "expansion": TOC})
check("but the same house is fine for the other set",
      r.status_code == 200, body(r))

r = c.post(ban_url, json={"banned_house": "Mars", "expansion": 999})
check("a set the week is not played across is refused",
      r.status_code == 400, body(r))

# --- clearing names the set -----------------------------------------------
r = c.delete(ban_url)
check("clearing without a set is refused", r.status_code == 400, body(r))
with app.app_context():
    check("so nothing was cleared",
          OublietteBan.query.filter_by(week_id=week_id, user_id=captain_id).count() == 2)

r = c.delete(f"{ban_url}?expansion={WOE}")
check("clearing one set works", r.status_code == 200, body(r))
with app.app_context():
    left = {b.expansion: b.banned_house
            for b in OublietteBan.query.filter_by(week_id=week_id, user_id=captain_id)}
    check("and leaves the other set alone", left == {TOC: "Dis"}, left)

# --- a captain may do it for a teammate -----------------------------------
r = c.post(ban_url, json={"banned_house": "Logos", "expansion": WOE,
                          "user_id": mate_id})
check("a captain can ban for a teammate", r.status_code == 200, body(r))
with app.app_context():
    check("filed against the teammate",
          OublietteBan.query.filter_by(week_id=week_id, user_id=mate_id).count() == 1)

# --- and the window stays open once pairings publish ----------------------
with app.app_context():
    w = db.session.get(LeagueWeek, week_id)
    w.status = WeekStatus.PUBLISHED.value
    db.session.commit()

r = c.post(ban_url, json={"banned_house": "Shadows", "expansion": WOE})
check("a ban can still be set while published", r.status_code == 200, body(r))
r = c.delete(f"{ban_url}?expansion={WOE}")
check("and still cleared while published", r.status_code == 200, body(r))

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
