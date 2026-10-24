"""The restricted list counts the pods taken, not the decks they came from."""
import datetime
import os
import sys

os.environ["TRACKER_CONFIG_PATH"] = "ENV"
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.pop("ENABLE_COLLECTOR", None)

from keytracker.server import app
from keytracker.match_helpers import validate_alliance_open
from keytracker.schema import (
    AllianceRestrictedEntry, AllianceRestrictedListVersion, CardInDeck, Deck,
    DokDeck, KeyforgeHouse, KeyforgeSet, League, LeagueStatus, LeagueWeek,
    PlatonicCard,
    PlatonicCardInSet, PodStats, User, WeekStatus, db,
)

FAIL = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + str(detail)) if detail else ''}")
    if not ok:
        FAIL.append(label)


AOA = 341
HOUSES = ("Dis", "Unfathomable", "Mars")

with app.app_context():
    db.drop_all()
    db.create_all()
    db.session.add(KeyforgeSet(number=AOA, name="Age of Ascension",
                               shortname="AoA", dokname="AoA"))
    house_ids = {}
    for name in HOUSES:
        h = KeyforgeHouse(name=name)
        db.session.add(h)
        db.session.flush()
        house_ids[name] = h.id

    def make_card(title):
        card = PlatonicCard(card_title=title)
        db.session.add(card)
        db.session.flush()
        return card

    # Two restricted cards, in different houses, plus filler for each house.
    infurnace = make_card("Infurnace")       # Dis
    befuddle = make_card("Befuddle")         # Unfathomable
    abduction = make_card("Key Abduction")   # Mars
    filler = {h: make_card(f"Filler {h}") for h in HOUSES}

    def in_set(card, house):
        cis = PlatonicCardInSet(card_id=card.id, expansion=AOA,
                                kf_house_id=house_ids[house])
        db.session.add(cis)
        db.session.flush()
        return cis

    sets = {
        ("Infurnace", "Dis"): in_set(infurnace, "Dis"),
        ("Befuddle", "Unfathomable"): in_set(befuddle, "Unfathomable"),
        ("Key Abduction", "Mars"): in_set(abduction, "Mars"),
    }
    for h in HOUSES:
        sets[(f"Filler {h}", h)] = in_set(filler[h], h)

    now = datetime.datetime.utcnow()

    def make_deck(name, contents):
        """contents: {house: [(card, card_in_set, count), ...]}"""
        deck = Deck(name=name, kf_id=name.ljust(32, "x")[:32], expansion=AOA)
        db.session.add(deck)
        db.session.flush()
        db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0, last_refresh=now))
        for house, cards in contents.items():
            db.session.add(PodStats(deck_id=deck.id, kf_house_id=house_ids[house]))
            for card, cis, count in cards:
                for _ in range(count):
                    db.session.add(
                        CardInDeck(deck_id=deck.id, platonic_card_id=card.id,
                                   card_in_set_id=cis.id)
                    )
        db.session.flush()
        return deck

    def house_contents(house, extra=()):
        return [(filler[house], sets[(f"Filler {house}", house)], 12), *extra]

    # Deck A: Infurnace in Dis, Befuddle in Unfathomable -- two restricted
    # entries in one deck, in different houses. This is the real shape that
    # was refusing legal alliances.
    deck_a = make_deck("A", {
        "Dis": house_contents("Dis", [(infurnace, sets[("Infurnace", "Dis")], 1)]),
        "Unfathomable": house_contents(
            "Unfathomable", [(befuddle, sets[("Befuddle", "Unfathomable")], 1)]
        ),
        "Mars": house_contents("Mars"),
    })
    # Deck B and C: nothing restricted anywhere.
    deck_b = make_deck("B", {h: house_contents(h) for h in HOUSES})
    deck_c = make_deck("C", {h: house_contents(h) for h in HOUSES})
    # Deck D: Key Abduction twice in Mars, which has a cap of one.
    deck_d = make_deck("D", {
        "Dis": house_contents("Dis"),
        "Unfathomable": house_contents("Unfathomable"),
        "Mars": house_contents(
            "Mars", [(abduction, sets[("Key Abduction", "Mars")], 2)]
        ),
    })
    # Deck E: Befuddle in Unfathomable, for pairing against deck A's Dis.
    deck_e = make_deck("E", {
        "Dis": house_contents("Dis"),
        "Unfathomable": house_contents(
            "Unfathomable", [(befuddle, sets[("Befuddle", "Unfathomable")], 1)]
        ),
        "Mars": house_contents("Mars"),
    })

    version = AllianceRestrictedListVersion(version=2.7)
    db.session.add(version)
    db.session.flush()
    db.session.add(AllianceRestrictedEntry(list_version_id=version.id,
                                           platonic_card_id=infurnace.id))
    db.session.add(AllianceRestrictedEntry(list_version_id=version.id,
                                           platonic_card_id=befuddle.id))
    db.session.add(AllianceRestrictedEntry(list_version_id=version.id,
                                           platonic_card_id=abduction.id,
                                           max_copies_per_alliance=1))

    owner = User(email="o@e.com", name="Owner")
    db.session.add(owner)
    db.session.flush()
    league = League(name="RL", team_size=1, num_teams=2,
                    status=LeagueStatus.ACTIVE.value, created_by_id=owner.id)
    db.session.add(league)
    db.session.flush()
    week = LeagueWeek(league_id=league.id, week_number=1, name="Alliance",
                      format_type="sealed_alliance", best_of_n=3,
                      status=WeekStatus.DECK_SELECTION.value,
                      alliance_restricted_list_version_id=version.id)
    db.session.add(week)
    db.session.commit()

    def pods(*spec):
        return [{"deck_id": d.id, "house": h} for d, h in spec]

    # --- the reported bug -------------------------------------------------
    errs = validate_alliance_open(
        week, 1, pods((deck_a, "Dis"), (deck_b, "Unfathomable"), (deck_c, "Mars")),
        None, None,
    )
    check("one restricted card in the pods taken is fine", errs == [], errs)

    # Deck A also holds Befuddle, but in a house nobody took.
    errs = validate_alliance_open(
        week, 1, pods((deck_a, "Dis"), (deck_e, "Unfathomable"), (deck_c, "Mars")),
        None, None,
    )
    check("two restricted cards in the pods taken is refused",
          errs and "at most" in errs[0], errs)

    # The same two decks, taking the houses that hold nothing restricted.
    errs = validate_alliance_open(
        week, 1, pods((deck_a, "Mars"), (deck_e, "Dis"), (deck_c, "Unfathomable")),
        None, None,
    )
    check("the untaken houses do not count against the alliance", errs == [], errs)

    # --- the per-card cap still applies, within a pod ---------------------
    errs = validate_alliance_open(
        week, 1, pods((deck_d, "Mars"), (deck_b, "Dis"), (deck_c, "Unfathomable")),
        None, None,
    )
    check("two copies of a card capped at one is refused",
          errs and "max 1" in errs[0], errs)

    # Taking a different house of that deck leaves the pair behind.
    errs = validate_alliance_open(
        week, 1, pods((deck_d, "Dis"), (deck_b, "Unfathomable"), (deck_c, "Mars")),
        None, None,
    )
    check("but not when that house was not taken", errs == [], errs)

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
