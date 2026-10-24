"""A deck played in the season is not spent for the playoffs."""
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
    LeagueStatus, LeagueWeek, PlatonicCard, PlayerDeckSelection, PlayoffBracket,
    PodStats, Team,
    TeamMember, User, WeekStatus, db, deck_reuse_scope,
)
from keytracker.routes.leagues import _check_deck_cross_week_conflicts

FAIL = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + str(detail)) if detail else ''}")
    if not ok:
        FAIL.append(label)


DM = 928
TEAMS, SIZE = 4, 2

with app.app_context():
    db.drop_all()
    db.create_all()
    db.session.add(KeyforgeSet(number=DM, name="Draconian Measures",
                               shortname="DM", dokname="DM"))
    for name in ("Mars", "Logos", "Untamed"):
        db.session.add(KeyforgeHouse(name=name))
    db.session.flush()
    houses = [h.id for h in KeyforgeHouse.query.all()]
    admin = User(email="admin@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="Reuse", team_size=SIZE, num_teams=TEAMS,
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
    decks = []
    for n in range(6):
        deck = Deck(name=f"deck {n}", kf_id=str(n).ljust(32, "a"), expansion=DM)
        db.session.add(deck)
        db.session.flush()
        db.session.add(DokDeck(deck_id=deck.id, sas_rating=50.0, raw_amber=5,
                               last_refresh=now))
        for h in houses:
            db.session.add(PodStats(deck_id=deck.id, kf_house_id=h))
        card = PlatonicCard(card_title=f"Filler {n}")
        db.session.add(card)
        db.session.flush()
        db.session.add(CardInDeck(deck_id=deck.id, platonic_card_id=card.id))
        decks.append(deck.id)

    bracket = PlayoffBracket(league_id=league.id, bracket_number=1, name="A",
                             format_type="archon_standard", best_of_n=1)
    db.session.add(bracket)
    db.session.flush()

    # Two season weeks, and the two rounds of one bracket.
    season1 = LeagueWeek(league_id=league.id, week_number=1, name="Season 1",
                         format_type="archon_standard", best_of_n=1,
                         status=WeekStatus.DECK_SELECTION.value)
    season2 = LeagueWeek(league_id=league.id, week_number=2, name="Season 2",
                         format_type="archon_standard", best_of_n=1,
                         status=WeekStatus.DECK_SELECTION.value)
    po1 = LeagueWeek(league_id=league.id, week_number=8, name="Bracket A r1",
                     format_type="archon_standard", best_of_n=1,
                     status=WeekStatus.DECK_SELECTION.value,
                     playoff_bracket_id=bracket.id, playoff_round=1)
    po2 = LeagueWeek(league_id=league.id, week_number=19, name="Bracket A r2",
                     format_type="archon_standard", best_of_n=1,
                     status=WeekStatus.DECK_SELECTION.value,
                     playoff_bracket_id=bracket.id, playoff_round=2)
    for w in (season1, season2, po1, po2):
        db.session.add(w)
    db.session.flush()

    me = players[teams[0]][0]
    # The deck that started the complaint: played in season week one.
    db.session.add(PlayerDeckSelection(week_id=season1.id, user_id=me,
                                       deck_id=decks[0], slot_number=1))
    db.session.commit()

    team = db.session.get(Team, teams[0])
    played = db.session.get(Deck, decks[0])
    fresh = db.session.get(Deck, decks[1])

    # --- the reported bug ------------------------------------------------
    errs = _check_deck_cross_week_conflicts(league, po1, played, team)
    check("a season deck is accepted in the playoffs", errs == [], errs)

    # --- but the season rule itself still holds ---------------------------
    # Two messages, not one: used-by-anyone and claimed-by-a-teammate both
    # fire, since a player is their own teammate. That is how it has always
    # read for the season, and is not what this change is about.
    errs = _check_deck_cross_week_conflicts(league, season2, played, team)
    check("and is still spent for a later season week",
          errs and all("Season 1" in e for e in errs), errs)

    # --- and the playoffs police themselves -------------------------------
    db.session.add(PlayerDeckSelection(week_id=po1.id, user_id=me,
                                       deck_id=decks[2], slot_number=1))
    db.session.commit()
    spent_in_playoffs = db.session.get(Deck, decks[2])
    errs = _check_deck_cross_week_conflicts(league, po2, spent_in_playoffs, team)
    check("a deck played in round one is spent for round two",
          errs and all("Bracket A r1" in e for e in errs), errs)
    errs = _check_deck_cross_week_conflicts(league, season2, spent_in_playoffs, team)
    check("but a playoff deck is not spent for the season",
          errs == [], errs)

    # --- an untouched deck is fine everywhere -----------------------------
    for week, label in ((po1, "a playoff week"), (season2, "a season week")):
        errs = _check_deck_cross_week_conflicts(league, week, fresh, team)
        check(f"an unplayed deck is accepted in {label}", errs == [], errs)

    # --- the scope helper says what it means ------------------------------
    season_scope = db.session.query(LeagueWeek.id).filter(
        LeagueWeek.league_id == league.id, deck_reuse_scope(season1)
    ).all()
    playoff_scope = db.session.query(LeagueWeek.id).filter(
        LeagueWeek.league_id == league.id, deck_reuse_scope(po1)
    ).all()
    check("a season week is judged against the two season weeks",
          {r[0] for r in season_scope} == {season1.id, season2.id},
          {r[0] for r in season_scope})
    check("a playoff week against the two playoff weeks",
          {r[0] for r in playoff_scope} == {po1.id, po2.id},
          {r[0] for r in playoff_scope})

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
