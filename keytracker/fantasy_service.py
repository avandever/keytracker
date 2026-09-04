"""Bridge between the tracker's league data and the pure scoring in fantasy.py.

Everything that touches the database lives here; keytracker/fantasy.py stays
free of it so the same scoring code can be replayed against past seasons.
"""

import json
import math
from typing import Dict, List, Optional, Set, Tuple

from keytracker.fantasy import (
    RosterEntry,
    ScoringConfig,
    TeamScore,
    rank_teams,
    score_teams,
)
from keytracker.schema import FantasyLeague, FantasyPlayerCost, League, User, db


def scoring_config(fl: FantasyLeague) -> ScoringConfig:
    bands = None
    if fl.scarcity_bands:
        try:
            # Stored as [[max_teams_or_null, points], ...].
            bands = [(row[0], row[1]) for row in json.loads(fl.scarcity_bands)]
        except (ValueError, TypeError, IndexError):
            bands = None
    return ScoringConfig(
        points_per_match_win=fl.points_per_match_win,
        weekly_threshold=fl.weekly_threshold,
        weekly_threshold_bonus=fl.weekly_threshold_bonus,
        captain_bonus=fl.captain_bonus_enabled,
        feature_win_bonus=fl.feature_win_bonus,
        scarcity_bands=bands,
    )


def confirmed_match_winners(
    league: League,
) -> Tuple[List[int], Dict[int, Set[int]], Dict[int, Set[int]]]:
    """Who won a match in each week, counting only confirmed results.

    An unconfirmed result scores nothing until a captain verifies it, which
    keeps fantasy standings from moving ahead of the real ones and stops them
    leaking a result the league page is still hiding. A double loss produces no
    winner, and so does a match nobody has played.

    Returns (week_numbers, winners_by_week, feature_winners_by_week).
    """
    weeks = sorted(league.weeks or [], key=lambda w: w.week_number)
    week_numbers: List[int] = []
    winners: Dict[int, Set[int]] = {}
    feature_winners: Dict[int, Set[int]] = {}

    for week in weeks:
        week_numbers.append(week.week_number)
        won: Set[int] = set()
        featured: Set[int] = set()
        wins_needed = math.ceil((week.best_of_n or 1) / 2)
        for wm in week.matchups:
            for pm in wm.player_matchups:
                if pm.is_double_loss or not pm.result_confirmed_at:
                    continue
                p1 = sum(1 for g in pm.games if g.winner_id == pm.player1_id)
                p2 = sum(1 for g in pm.games if g.winner_id == pm.player2_id)
                if p1 >= wins_needed:
                    winner_id = pm.player1_id
                elif p2 >= wins_needed:
                    winner_id = pm.player2_id
                else:
                    continue
                won.add(winner_id)
                if pm.is_feature:
                    featured.add(winner_id)
        winners[week.week_number] = won
        feature_winners[week.week_number] = featured

    return week_numbers, winners, feature_winners


def season_win_counts(league: League) -> Dict[int, int]:
    """Confirmed match wins per player across a whole season."""
    _weeks, winners, _feature = confirmed_match_winners(league)
    counts: Dict[int, int] = {}
    for won in winners.values():
        for user_id in won:
            counts[user_id] = counts.get(user_id, 0) + 1
    return counts


def generate_player_costs(
    fl: FantasyLeague, replace: bool = True
) -> List[FantasyPlayerCost]:
    """Price every player in the fantasy league's real league.

    Cost is what the player won in the source season, clamped to the
    commissioner's floor and cap. Anyone who did not play the source season is a
    newcomer: they cost the floor and are the ones the scarcity bonus applies
    to.

    Nothing is committed here -- the commissioner is expected to review and
    adjust before entries open.
    """
    league = fl.league
    if league is None:
        return []

    source_wins: Dict[int, int] = {}
    # Who is a newcomer has to come from who was ON a team last season, not from
    # who won: a returning player who lost every match has no wins, and pricing
    # them as a newcomer would hand the scarcity bonus to whoever drafted them.
    source_participants: Set[int] = set()
    if fl.cost_source_league:
        source_wins = season_win_counts(fl.cost_source_league)
        for team in fl.cost_source_league.teams:
            for member in team.members:
                source_participants.add(member.user_id)

    if replace:
        FantasyPlayerCost.query.filter_by(fantasy_league_id=fl.id).delete()

    costs: List[FantasyPlayerCost] = []
    for team in league.teams:
        for member in team.members:
            is_new = member.user_id not in source_participants
            wins = None if is_new else source_wins.get(member.user_id, 0)
            raw = fl.cost_min if is_new else wins
            cost = max(fl.cost_min, min(fl.cost_max, raw))
            row = FantasyPlayerCost(
                fantasy_league_id=fl.id,
                player_user_id=member.user_id,
                cost=cost,
                is_new_player=is_new,
                source_wins=wins,
            )
            db.session.add(row)
            costs.append(row)
    return costs


def score_fantasy_league(fl: FantasyLeague) -> List[Tuple[object, TeamScore]]:
    """Current standings, best first."""
    league = fl.league
    if league is None:
        return []

    week_numbers, winners, feature_winners = confirmed_match_winners(league)

    rosters: Dict[int, List[RosterEntry]] = {}
    for team in fl.teams:
        rosters[team.id] = [
            RosterEntry(
                player=slot.player_user_id,
                cost=slot.cost_at_draft,
                is_captain=slot.is_captain,
                # A team only earns the scarcity bonus if the commissioner has
                # it switched on.
                is_new=slot.is_new_at_draft and fl.scarcity_bonus_enabled,
            )
            for slot in team.roster
        ]

    # Late entrants are scored from week one like everyone else: they pay
    # week-one prices for players who have since proven themselves, and the cap
    # does the balancing. joined_week_number is recorded for display, so
    # standings can mark who came in late, and is available to score_teams via
    # scoring_weeks_by_team should that policy ever change.
    scores = score_teams(
        scoring_config(fl),
        rosters,
        week_numbers,
        winners,
        feature_winners_by_week=feature_winners,
    )
    return rank_teams(scores)


def roster_validation_error(
    fl: FantasyLeague, player_ids: List[int], captain_id: Optional[int]
) -> Optional[str]:
    """Why this roster is not legal, or None if it is.

    Checked server-side because the cap is the whole game: a client that skips
    it would otherwise be able to field an unbeatable team.
    """
    if len(player_ids) != fl.roster_size:
        return f"A team must have exactly {fl.roster_size} players"
    if len(set(player_ids)) != len(player_ids):
        return "A team cannot draft the same player twice"
    if captain_id is not None and captain_id not in player_ids:
        return "The captain must be one of the drafted players"

    costs = {
        row.player_user_id: row
        for row in FantasyPlayerCost.query.filter_by(fantasy_league_id=fl.id).all()
    }
    missing = [pid for pid in player_ids if pid not in costs]
    if missing:
        names = [
            (db.session.get(User, pid).name if db.session.get(User, pid) else str(pid))
            for pid in missing
        ]
        return f"Not available in this fantasy league: {', '.join(names)}"

    total = sum(costs[pid].cost for pid in player_ids)
    if total > fl.salary_cap:
        return f"Roster costs {total}, over the cap of {fl.salary_cap}"
    return None
