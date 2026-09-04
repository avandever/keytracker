"""Fantasy league scoring.

Deliberately free of SQLAlchemy: everything here operates on plain data, so the
same functions that score a live league can be replayed against the exported
ABR 12 spreadsheets as a regression test. See
keytracker/scripts/validate_fantasy_abr12.py.

The rules come from jtrussell's ABR 12 form, with two corrections established by
back-testing that season's published standings:

  * The scarcity band for a newcomer keys on the total number of teams holding
    that player INCLUDING your own, not "other teams" as the form's wording
    says. Fitting the three team totals lqdsquash worked out by hand only
    succeeds under this reading.
  * The form's bands leave 7-9 undefined. It behaves as zero, so that is the
    default band list here rather than a gap.

The scarcity bonus was never actually applied in ABR 12; the published standings
reconcile exactly without it.
"""

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

# (max_teams_holding_the_player, points). None means "no upper bound".
# Defaults reproduce the ABR 12 form once the 7-9 gap is closed at zero.
DEFAULT_SCARCITY_BANDS: List[Tuple[Optional[int], int]] = [
    (3, 3),
    (6, 2),
    (9, 0),
    (None, -2),
]


@dataclass
class ScoringConfig:
    """Everything a commissioner can tune about how a season scores."""

    points_per_match_win: int = 1
    # A week where a team's players won at least this many matches earns
    # weekly_threshold_bonus. None disables the weekly bonus entirely.
    weekly_threshold: Optional[int] = 4
    weekly_threshold_bonus: int = 1
    # Captain earns their wins above their cost. Never negative: three ABR 12
    # captains came in under cost and were charged nothing.
    captain_bonus: bool = True
    # Feature wins counted as ordinary wins in ABR 12, so weighting them is a
    # new decision rather than a restoration. Off by default.
    feature_win_bonus: int = 0
    scarcity_bands: Optional[List[Tuple[Optional[int], int]]] = None

    def bands(self) -> List[Tuple[Optional[int], int]]:
        return (
            self.scarcity_bands
            if self.scarcity_bands is not None
            else DEFAULT_SCARCITY_BANDS
        )


@dataclass
class RosterEntry:
    """One drafted player on one fantasy team.

    `player` is an opaque key -- a user id in production, a username when
    replaying a spreadsheet. `cost` is the price paid at draft time, snapshotted
    so a later change to the cost table cannot rewrite a completed draft.
    """

    player: object
    cost: int = 0
    is_captain: bool = False
    is_new: bool = False


@dataclass
class TeamScore:
    match_wins: int = 0
    weekly_bonus: int = 0
    captain_bonus: int = 0
    scarcity_bonus: int = 0
    feature_bonus: int = 0
    total: int = 0
    roster_cost: int = 0
    # Match wins per week, in the order weeks were supplied.
    weekly: List[int] = field(default_factory=list)


def scarcity_points(
    teams_holding: int, bands: Sequence[Tuple[Optional[int], int]]
) -> int:
    """Points for a newcomer held by `teams_holding` teams (including yours)."""
    for max_teams, points in bands:
        if max_teams is None or teams_holding <= max_teams:
            return points
    return 0


def score_teams(
    config: ScoringConfig,
    rosters: Dict[object, List[RosterEntry]],
    weeks: Sequence[object],
    winners_by_week: Dict[object, Set[object]],
    feature_winners_by_week: Optional[Dict[object, Set[object]]] = None,
    scoring_weeks_by_team: Optional[Dict[object, Set[object]]] = None,
) -> Dict[object, TeamScore]:
    """Score every fantasy team.

    `winners_by_team` should hold only results that are settled -- confirmed in
    the tracker's sense. A player appears at most once per week: a double loss
    and an unplayed match both simply produce no win, so neither scores.

    `scoring_weeks_by_team` limits a team to a subset of weeks, for managers who
    joined late. Omitted means every team scores every week.
    """
    feature_winners_by_week = feature_winners_by_week or {}

    # A newcomer's scarcity band depends on the whole field, so this is counted
    # across every roster before any team is scored.
    teams_holding: Dict[object, int] = {}
    for entries in rosters.values():
        for entry in {e.player for e in entries}:
            teams_holding[entry] = teams_holding.get(entry, 0) + 1

    bands = config.bands()
    results: Dict[object, TeamScore] = {}

    for team_key, entries in rosters.items():
        score = TeamScore()
        score.roster_cost = sum(e.cost for e in entries)
        players = [e.player for e in entries]
        eligible = (
            scoring_weeks_by_team.get(team_key)
            if scoring_weeks_by_team is not None
            else None
        )

        for week in weeks:
            if eligible is not None and week not in eligible:
                score.weekly.append(0)
                continue
            winners = winners_by_week.get(week, ())
            wins = sum(1 for p in players if p in winners)
            score.weekly.append(wins)
            score.match_wins += wins * config.points_per_match_win
            if config.feature_win_bonus:
                feature = feature_winners_by_week.get(week, ())
                score.feature_bonus += (
                    sum(1 for p in players if p in feature) * config.feature_win_bonus
                )

        if config.weekly_threshold is not None:
            qualifying = sum(1 for w in score.weekly if w >= config.weekly_threshold)
            score.weekly_bonus = qualifying * config.weekly_threshold_bonus

        if config.captain_bonus:
            for entry in entries:
                if not entry.is_captain:
                    continue
                season_wins = _season_wins(
                    entry.player, weeks, winners_by_week, eligible
                )
                score.captain_bonus += max(0, season_wins - entry.cost)

        for entry in entries:
            if entry.is_new:
                score.scarcity_bonus += scarcity_points(
                    teams_holding.get(entry.player, 0), bands
                )

        score.total = (
            score.match_wins
            + score.weekly_bonus
            + score.captain_bonus
            + score.scarcity_bonus
            + score.feature_bonus
        )
        results[team_key] = score

    return results


def _season_wins(
    player: object,
    weeks: Iterable[object],
    winners_by_week: Dict[object, Set[object]],
    eligible: Optional[Set[object]],
) -> int:
    return sum(
        1
        for week in weeks
        if (eligible is None or week in eligible)
        and player in winners_by_week.get(week, ())
    )


def rank_teams(scores: Dict[object, TeamScore]) -> List[Tuple[object, TeamScore]]:
    """Standings order: most points, then the cheaper roster, per the ABR rules.

    The published rules break a remaining tie on whose team name the
    commissioner likes best, which is not something code should decide -- teams
    still tied here are simply tied.
    """
    return sorted(scores.items(), key=lambda kv: (-kv[1].total, kv[1].roster_cost))
