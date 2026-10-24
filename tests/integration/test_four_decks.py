"""Double Oubliette: four decks, two per set, and what a ban now decides."""
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


WOE, TOC = 600, 855

with app.app_context():
    db.drop_all()
    db.create_all()
    db.session.add(KeyforgeSet(number=WOE, name="Winds of Exchange",
                               shortname="WoE", dokname="WoE"))
    db.session.add(KeyforgeSet(number=TOC, name="Tokens of Change",
                               shortname="ToC", dokname="ToC"))
    hid = {}
    for name in ("Brobnar", "Dis", "Logos", "Mars", "Shadows", "Sanctum", "Untamed"):
        h = KeyforgeHouse(name=name)
        db.session.add(h)
        db.session.flush()
        hid[name] = h.id

    admin = User(email="a@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="DO4", team_size=1, num_teams=2,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))
    team = Team(league_id=league.id, name="T1", order_number=1)
    db.session.add(team)
    db.session.flush()
    me = User(email="me@e.com", name="Me")
    foe = User(email="foe@e.com", name="Foe")
    db.session.add_all([me, foe])
    db.session.flush()
    db.session.add(TeamMember(team_id=team.id, user_id=me.id, is_captain=True))

    now = datetime.datetime.utcnow()
    made = {}

    kf_ids = {}

    def make_deck(name, expansion, houses):
        kf_ids[name] = str(uuid.uuid4())
        deck = Deck(name=name, kf_id=kf_ids[name], expansion=expansion)
        db.session.add(deck)
        db.session.flush()
        db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0, last_refresh=now))
        for h in houses:
            db.session.add(PodStats(deck_id=deck.id, kf_house_id=hid[h]))
        card = PlatonicCard(card_title=f"Filler {name}")
        db.session.add(card)
        db.session.flush()
        db.session.add(CardInDeck(deck_id=deck.id, platonic_card_id=card.id))
        db.session.flush()
        made[name] = deck
        return deck

    # Two WoE decks sharing Brobnar, two ToC decks sharing nothing.
    make_deck("woeA", WOE, ["Brobnar", "Dis", "Logos"])
    make_deck("woeB", WOE, ["Brobnar", "Mars", "Shadows"])
    make_deck("tocA", TOC, ["Untamed", "Dis", "Logos"])
    make_deck("tocB", TOC, ["Mars", "Shadows", "Sanctum"])

    week = LeagueWeek(league_id=league.id, week_number=1, name="Double",
                      format_type="double_oubliette", best_of_n=3,
                      status=WeekStatus.DECK_SELECTION.value,
                      allowed_sets=json.dumps([WOE, TOC]))
    db.session.add(week)
    db.session.commit()
    league_id, week_id, me_id, foe_id = league.id, week.id, me.id, foe.id
    deck_ids = {k: v.id for k, v in made.items()}
    deck_urls = {k: f"https://decksofkeyforge.com/decks/{v}" for k, v in kf_ids.items()}

c = app.test_client()
with c.session_transaction() as s:
    s["_user_id"] = str(me_id)
    s["_fresh"] = True
url = f"/api/v2/leagues/{league_id}/weeks/{week_id}/deck-selection"


def submit(slot, deck_key):
    # Non-sealed weeks take a deck URL; the id is resolved from it.
    return c.post(url, json={"deck_url": deck_urls[deck_key], "slot_number": slot})


# --- four slots, split between the sets -----------------------------------
r = submit(1, "woeA")
check("slot 1 takes a WoE deck", r.status_code in (200, 201), str(body(r))[:90])
r = submit(2, "woeB")
check("slot 2 takes a second WoE deck", r.status_code in (200, 201), str(body(r))[:90])
r = submit(3, "tocA")
check("slot 3 takes a ToC deck", r.status_code in (200, 201), str(body(r))[:90])
r = submit(4, "tocB")
check("slot 4 takes a second ToC deck", r.status_code in (200, 201), str(body(r))[:90])

with app.app_context():
    n = PlayerDeckSelection.query.filter_by(week_id=week_id, user_id=me_id).count()
    check("all four are recorded", n == 4, n)

r = c.post(url, json={"deck_url": deck_urls["woeA"], "slot_number": 5})
check("there is no fifth slot", r.status_code == 400, body(r).get("error"))

# --- the slot fixes the set ------------------------------------------------
r = submit(1, "tocA")
check("a ToC deck is refused by a WoE slot",
      r.status_code == 400 and "WoE" in str(body(r).get("error")),
      body(r).get("error"))
r = submit(4, "woeA")
check("and a WoE deck by a ToC slot",
      r.status_code == 400 and "ToC" in str(body(r).get("error")),
      body(r).get("error"))

with app.app_context():
    still = PlayerDeckSelection.query.filter_by(week_id=week_id, user_id=me_id).count()
    check("a refused swap leaves the four alone", still == 4, still)

# --- what a ban now decides ------------------------------------------------
from keytracker.routes.leagues import (  # noqa: E402
    _double_oubliette_eliminated,
    _double_oubliette_wiped_sets,
)

with app.app_context():
    # The opponent bans Brobnar for WoE -- both WoE decks hold it -- and Mars
    # for ToC, which only one ToC deck holds.
    db.session.add(OublietteBan(week_id=week_id, user_id=foe_id,
                                banned_house="Brobnar", expansion=WOE))
    db.session.add(OublietteBan(week_id=week_id, user_id=foe_id,
                                banned_house="Mars", expansion=TOC))
    db.session.commit()

    out = set(_double_oubliette_eliminated(week_id and db.session.get(LeagueWeek, week_id),
                                           me_id, foe_id))
    check("the ban takes both WoE decks and one ToC deck",
          out == {deck_ids["woeA"], deck_ids["woeB"], deck_ids["tocB"]},
          sorted(out))

    wiped = _double_oubliette_wiped_sets(
        db.session.get(LeagueWeek, week_id), me_id, foe_id
    )
    check("WoE is wiped out, since nothing of it survives", wiped == [WOE], wiped)
    check("ToC is not, one deck having survived", TOC not in wiped, wiped)

    # Losing just one deck of a set must not decide anything: drop the ban
    # that caught both WoE decks and aim it at a house only one holds.
    OublietteBan.query.filter_by(week_id=week_id, user_id=foe_id,
                                 expansion=WOE).delete()
    db.session.add(OublietteBan(week_id=week_id, user_id=foe_id,
                                banned_house="Dis", expansion=WOE))
    db.session.commit()
    wiped = _double_oubliette_wiped_sets(
        db.session.get(LeagueWeek, week_id), me_id, foe_id
    )
    check("one deck of a set going is survivable", wiped == [], wiped)

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
