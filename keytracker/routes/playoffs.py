"""Playoff setup: configuration, qualifying teams, brackets and assignments.

The playoffs run several brackets at once -- one per player on a team, each in
its own format, each advancing on its own -- so they need their own setup
before any of the week machinery can be pointed at them. This module covers
that setup; drawing the brackets and playing the rounds come after.
"""

import datetime
import json
import random

from flask import Blueprint, jsonify, request
from flask_login import login_required

from keytracker.playoff_draw import (
    bracket_size,
    byes_needed,
    draw_all,
    round_one_pairs,
    rounds_needed,
)

from keytracker.routes.leagues import (
    _get_league_or_404,
    _is_league_admin,
    _log_admin_action,
    get_effective_user,
)
from keytracker.schema import (
    LeagueWeek,
    PlayerMatchup,
    PlayoffAssignment,
    PlayoffBracket,
    PlayoffByePolicy,
    PlayoffConfig,
    PlayoffMatch,
    PlayoffQualifier,
    Team,
    TeamMember,
    User,
    WeekFormat,
    WeekMatchup,
    WeekStatus,
    db,
)

blueprint = Blueprint("playoffs", __name__, url_prefix="/api/v2/leagues")

DEFAULT_POINTS_PER_ROUND = [1]


def _config_for(league, create=False):
    config = db.session.get(PlayoffConfig, league.id)
    if config is None and create:
        config = PlayoffConfig(league_id=league.id)
        db.session.add(config)
    return config


def _points_list(config):
    if not config or not config.points_per_round:
        return list(DEFAULT_POINTS_PER_ROUND)
    try:
        points = json.loads(config.points_per_round)
    except (json.JSONDecodeError, TypeError):
        return list(DEFAULT_POINTS_PER_ROUND)
    return [int(p) for p in points] if isinstance(points, list) else list(DEFAULT_POINTS_PER_ROUND)


def _serialize_config(league, config):
    return {
        "teams_advancing": config.teams_advancing if config else 4,
        "points_per_round": _points_list(config),
        "consolation_enabled": bool(config.consolation_enabled) if config else False,
        "consolation_points": config.consolation_points if config else 1,
        "bye_policy": config.bye_policy if config else PlayoffByePolicy.RANDOM_EVEN.value,
        "drawn_at": (
            config.drawn_at.isoformat() + "Z" if config and config.drawn_at else None
        ),
        # One bracket per player on a team, so this is how many there should be.
        "expected_brackets": league.team_size,
    }


def _serialize_bracket(bracket):
    return {
        "id": bracket.id,
        "bracket_number": bracket.bracket_number,
        "name": bracket.name,
        "format_type": bracket.format_type,
        "best_of_n": bracket.best_of_n,
        "assignments": [
            {
                "id": a.id,
                "team_id": a.team_id,
                "user_id": a.user_id,
                "user_name": a.user.name if a.user else None,
            }
            for a in sorted(bracket.assignments, key=lambda a: a.team_id)
        ],
    }


def _is_captain_of(team, user_id):
    return any(m.user_id == user_id and m.is_captain for m in team.members)


@blueprint.route("/<int:league_id>/playoffs", methods=["GET"])
def get_playoffs(league_id):
    """Everything the playoff setup screens need."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    config = _config_for(league)
    brackets = sorted(league.playoff_brackets, key=lambda b: b.bracket_number)
    qualifiers = sorted(league.playoff_qualifiers, key=lambda q: q.position)

    # Anyone may read the setup. get_effective_user hands back Flask-Login's
    # anonymous user rather than None, and that object is truthy but has no id,
    # so it has to be flattened before anything asks who it is.
    viewer = get_effective_user()
    if getattr(viewer, "id", None) is None:
        viewer = None
    my_team_id = None
    is_captain = False
    if viewer is not None:
        member = (
            TeamMember.query.join(Team)
            .filter(Team.league_id == league.id, TeamMember.user_id == viewer.id)
            .first()
        )
        if member:
            my_team_id = member.team_id
            is_captain = bool(member.is_captain)

    return jsonify(
        {
            "league_id": league.id,
            "config": _serialize_config(league, config),
            "brackets": [_serialize_bracket(b) for b in brackets],
            "qualifiers": [
                {
                    "team_id": q.team_id,
                    "team_name": q.team.name if q.team else None,
                    "position": q.position,
                }
                for q in qualifiers
            ],
            "is_admin": bool(viewer and _is_league_admin(league, viewer)),
            "my_team_id": my_team_id,
            "is_captain": is_captain,
        }
    )


def _locked(config):
    """Setup is fixed once the draw has been made."""
    return config is not None and config.drawn_at is not None


@blueprint.route("/<int:league_id>/playoffs/config", methods=["PUT"])
@login_required
def update_playoff_config(league_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    effective = get_effective_user()
    if not _is_league_admin(league, effective):
        return jsonify({"error": "Admin access required"}), 403
    config = _config_for(league, create=True)
    if _locked(config):
        return jsonify({"error": "The brackets are drawn; setup is fixed"}), 400

    data = request.get_json(silent=True) or {}
    if "teams_advancing" in data:
        value = data["teams_advancing"]
        if not isinstance(value, int) or value < 2:
            return jsonify({"error": "teams_advancing must be at least 2"}), 400
        if value > len(league.teams):
            return (
                jsonify({"error": f"Only {len(league.teams)} teams are in this league"}),
                400,
            )
        config.teams_advancing = value
    if "points_per_round" in data:
        points = data["points_per_round"]
        if (
            not isinstance(points, list)
            or not points
            or any(not isinstance(p, int) or p < 0 for p in points)
        ):
            return (
                jsonify({"error": "points_per_round must be a list of whole numbers"}),
                400,
            )
        config.points_per_round = json.dumps(points)
    if "consolation_enabled" in data:
        config.consolation_enabled = bool(data["consolation_enabled"])
    if "consolation_points" in data:
        value = data["consolation_points"]
        if not isinstance(value, int) or value < 0:
            return jsonify({"error": "consolation_points must be a whole number"}), 400
        config.consolation_points = value
    if "bye_policy" in data:
        valid = {p.value for p in PlayoffByePolicy}
        if data["bye_policy"] not in valid:
            return jsonify({"error": f"bye_policy must be one of {sorted(valid)}"}), 400
        config.bye_policy = data["bye_policy"]

    _log_admin_action(league.id, None, effective.id, "playoff_config_updated", None)
    db.session.commit()
    return jsonify(_serialize_config(league, config))


@blueprint.route("/<int:league_id>/playoffs/brackets", methods=["PUT"])
@login_required
def set_playoff_brackets(league_id):
    """Replace the bracket list: one bracket per player, each with a format."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    effective = get_effective_user()
    if not _is_league_admin(league, effective):
        return jsonify({"error": "Admin access required"}), 403
    config = _config_for(league, create=True)
    if _locked(config):
        return jsonify({"error": "The brackets are drawn; setup is fixed"}), 400

    data = request.get_json(silent=True) or {}
    wanted = data.get("brackets")
    if not isinstance(wanted, list):
        return jsonify({"error": "brackets must be a list"}), 400
    valid_formats = {f.value for f in WeekFormat}
    for entry in wanted:
        if not isinstance(entry, dict):
            return jsonify({"error": "each bracket must be an object"}), 400
        if entry.get("format_type") not in valid_formats:
            return (
                jsonify({"error": f"Unknown format: {entry.get('format_type')!r}"}),
                400,
            )
        best_of = entry.get("best_of_n", 1)
        if not isinstance(best_of, int) or best_of < 1 or best_of % 2 == 0:
            return jsonify({"error": "best_of_n must be an odd positive number"}), 400

    existing = {b.bracket_number: b for b in league.playoff_brackets}
    kept = set()
    for index, entry in enumerate(wanted, start=1):
        bracket = existing.get(index)
        if bracket is None:
            bracket = PlayoffBracket(league_id=league.id, bracket_number=index)
            db.session.add(bracket)
        bracket.name = (entry.get("name") or "").strip() or None
        bracket.format_type = entry["format_type"]
        bracket.best_of_n = entry.get("best_of_n", 1)
        kept.add(index)
    for number, bracket in existing.items():
        if number not in kept:
            PlayoffAssignment.query.filter_by(bracket_id=bracket.id).delete()
            db.session.delete(bracket)

    _log_admin_action(
        league.id, None, effective.id, "playoff_brackets_set", f"{len(wanted)} bracket(s)"
    )
    db.session.commit()
    db.session.refresh(league)
    brackets = sorted(league.playoff_brackets, key=lambda b: b.bracket_number)
    return jsonify({"brackets": [_serialize_bracket(b) for b in brackets]})


@blueprint.route("/<int:league_id>/playoffs/qualifiers", methods=["PUT"])
@login_required
def set_playoff_qualifiers(league_id):
    """Confirm which teams are through, in order.

    The order does not decide who plays whom -- that is drawn per bracket --
    but it settles ties by hand and feeds the bye policies that reward the
    regular season.
    """
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    effective = get_effective_user()
    if not _is_league_admin(league, effective):
        return jsonify({"error": "Admin access required"}), 403
    config = _config_for(league, create=True)
    if _locked(config):
        return jsonify({"error": "The brackets are drawn; setup is fixed"}), 400

    data = request.get_json(silent=True) or {}
    team_ids = data.get("team_ids")
    if not isinstance(team_ids, list) or not team_ids:
        return jsonify({"error": "team_ids must be a non-empty list"}), 400
    if len(set(team_ids)) != len(team_ids):
        return jsonify({"error": "A team can only qualify once"}), 400
    league_team_ids = {t.id for t in league.teams}
    for team_id in team_ids:
        if team_id not in league_team_ids:
            return jsonify({"error": f"Team {team_id} is not in this league"}), 400
    if len(team_ids) != config.teams_advancing:
        return (
            jsonify(
                {
                    "error": f"{config.teams_advancing} teams advance; "
                    f"{len(team_ids)} were given"
                }
            ),
            400,
        )

    PlayoffQualifier.query.filter_by(league_id=league.id).delete()
    db.session.flush()
    for position, team_id in enumerate(team_ids, start=1):
        db.session.add(
            PlayoffQualifier(league_id=league.id, team_id=team_id, position=position)
        )
    _log_admin_action(
        league.id, None, effective.id, "playoff_qualifiers_set",
        ", ".join(str(t) for t in team_ids),
    )
    db.session.commit()
    db.session.refresh(league)
    qualifiers = sorted(league.playoff_qualifiers, key=lambda q: q.position)
    return jsonify(
        {
            "qualifiers": [
                {
                    "team_id": q.team_id,
                    "team_name": q.team.name if q.team else None,
                    "position": q.position,
                }
                for q in qualifiers
            ]
        }
    )


@blueprint.route("/<int:league_id>/playoffs/assignments", methods=["PUT"])
@login_required
def set_playoff_assignments(league_id):
    """A captain puts one of their players in each bracket."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    effective = get_effective_user()
    config = _config_for(league)
    if _locked(config):
        return jsonify({"error": "The brackets are drawn; assignments are fixed"}), 400

    data = request.get_json(silent=True) or {}
    team_id = data.get("team_id")
    team = db.session.get(Team, team_id) if team_id else None
    if team is None or team.league_id != league.id:
        return jsonify({"error": "Team not found"}), 404
    is_admin = _is_league_admin(league, effective)
    if not is_admin and not _is_captain_of(team, effective.id):
        return jsonify({"error": "Captain or admin access required"}), 403

    entries = data.get("assignments")
    if not isinstance(entries, list):
        return jsonify({"error": "assignments must be a list"}), 400

    brackets = {b.id: b for b in league.playoff_brackets}
    member_ids = {m.user_id for m in team.members}
    seen_brackets, seen_users = set(), set()
    for entry in entries:
        if not isinstance(entry, dict):
            return jsonify({"error": "each assignment must be an object"}), 400
        bracket_id, user_id = entry.get("bracket_id"), entry.get("user_id")
        if bracket_id not in brackets:
            return jsonify({"error": f"Unknown bracket {bracket_id}"}), 400
        if user_id not in member_ids:
            user = db.session.get(User, user_id)
            name = user.name if user else user_id
            return jsonify({"error": f"{name} is not on this team"}), 400
        if bracket_id in seen_brackets:
            return jsonify({"error": "One player per bracket"}), 400
        if user_id in seen_users:
            return jsonify({"error": "A player can only be in one bracket"}), 400
        seen_brackets.add(bracket_id)
        seen_users.add(user_id)

    PlayoffAssignment.query.filter(
        PlayoffAssignment.team_id == team.id,
        PlayoffAssignment.bracket_id.in_(list(brackets)),
    ).delete(synchronize_session=False)
    db.session.flush()
    for entry in entries:
        db.session.add(
            PlayoffAssignment(
                bracket_id=entry["bracket_id"],
                team_id=team.id,
                user_id=entry["user_id"],
                assigned_by_id=effective.id,
            )
        )
    db.session.commit()
    db.session.refresh(league)
    ordered = sorted(league.playoff_brackets, key=lambda b: b.bracket_number)
    return jsonify({"brackets": [_serialize_bracket(b) for b in ordered]})


def _serialize_match(match):
    return {
        "id": match.id,
        "round_number": match.round_number,
        "slot_index": match.slot_index,
        "team1_id": match.team1_id,
        "team2_id": match.team2_id,
        "winner_team_id": match.winner_team_id,
        "is_bye": bool(match.is_bye),
        "is_consolation": bool(match.is_consolation),
        "player_matchup_id": match.player_matchup_id,
    }


def _bye_teams_by_policy(league, config, brackets, qualifier_ids, rng):
    """Which teams sit out round one, per the league's chosen policy.

    Returns a function of (bracket index, bye counts so far), which is what the
    draw wants; returning None leaves the draw to spread them evenly itself.
    """
    need = byes_needed(len(qualifier_ids))
    if not need:
        return None
    policy = config.bye_policy

    if policy == PlayoffByePolicy.TEAM_RECORD.value:
        # The confirmed order is the regular season's finish.
        chosen = list(qualifier_ids[:need])
        return lambda index, counts: chosen

    if policy == PlayoffByePolicy.PLAYER_RECORD.value:
        from keytracker.fantasy_service import season_win_counts

        wins = season_win_counts(league)

        def by_player(index, counts):
            bracket = brackets[index]
            ranked = []
            for team_id in qualifier_ids:
                assignment = next(
                    (a for a in bracket.assignments if a.team_id == team_id), None
                )
                ranked.append(
                    (wins.get(assignment.user_id, 0) if assignment else -1, team_id)
                )
            # Most wins first; ties fall back to the confirmed order.
            ranked.sort(key=lambda pair: (-pair[0], qualifier_ids.index(pair[1])))
            return [team_id for _score, team_id in ranked[:need]]

        return by_player

    if policy == PlayoffByePolicy.ADMIN.value:
        return "admin"
    return None


@blueprint.route("/<int:league_id>/playoffs/draw", methods=["POST"])
@login_required
def draw_playoffs(league_id):
    """Draw every bracket at once, fixing the whole tree.

    Placement is drawn rather than seeded, and balanced so that across the
    brackets no pair of teams meets in round one much more often than any
    other. Every round is created now, so a team can see who they would meet
    later; the later matches simply have no teams in them yet.
    """
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    effective = get_effective_user()
    if not _is_league_admin(league, effective):
        return jsonify({"error": "Admin access required"}), 403
    config = _config_for(league, create=True)
    if _locked(config):
        return jsonify({"error": "The brackets are already drawn"}), 400

    brackets = sorted(league.playoff_brackets, key=lambda b: b.bracket_number)
    qualifiers = sorted(league.playoff_qualifiers, key=lambda q: q.position)
    qualifier_ids = [q.team_id for q in qualifiers]

    if len(brackets) != league.team_size:
        return (
            jsonify(
                {
                    "error": f"{league.team_size} brackets are needed, one per player; "
                    f"{len(brackets)} are defined"
                }
            ),
            400,
        )
    if len(qualifier_ids) != config.teams_advancing:
        return (
            jsonify({"error": f"{config.teams_advancing} teams must be confirmed"}),
            400,
        )
    missing = []
    for bracket in brackets:
        assigned = {a.team_id for a in bracket.assignments}
        for team_id in qualifier_ids:
            if team_id not in assigned:
                team = db.session.get(Team, team_id)
                missing.append(f"{team.name if team else team_id} in bracket {bracket.bracket_number}")
    if missing:
        return (
            jsonify({"error": "Every team needs a player in every bracket. Missing: "
                              + ", ".join(missing[:8])
                              + ("..." if len(missing) > 8 else "")}),
            400,
        )

    data = request.get_json(silent=True) or {}
    rng = random.Random(data.get("seed"))
    byes_for = _bye_teams_by_policy(league, config, brackets, qualifier_ids, rng)
    if byes_for == "admin":
        supplied = data.get("byes")
        if not isinstance(supplied, dict):
            return (
                jsonify({"error": "This league assigns byes by hand: send byes as "
                                  "{bracket_number: [team_id, ...]}"}),
                400,
            )
        need = byes_needed(len(qualifier_ids))
        by_number = {}
        for key, team_ids in supplied.items():
            if not isinstance(team_ids, list) or len(team_ids) != need:
                return jsonify({"error": f"Each bracket needs {need} bye(s)"}), 400
            for team_id in team_ids:
                if team_id not in qualifier_ids:
                    return jsonify({"error": f"Team {team_id} is not in the playoffs"}), 400
            by_number[int(key)] = team_ids
        for bracket in brackets:
            if bracket.bracket_number not in by_number:
                return (
                    jsonify({"error": f"No byes given for bracket {bracket.bracket_number}"}),
                    400,
                )
        byes_for = lambda index, counts: by_number[brackets[index].bracket_number]

    drawn = draw_all(qualifier_ids, len(brackets), byes_for=byes_for, rng=rng)
    size = bracket_size(len(qualifier_ids))
    total_rounds = rounds_needed(len(qualifier_ids))

    PlayoffMatch.query.filter(
        PlayoffMatch.bracket_id.in_([b.id for b in brackets])
    ).delete(synchronize_session=False)
    db.session.flush()

    for bracket, slots in zip(brackets, drawn):
        first_round = []
        for index, (a, b) in enumerate(round_one_pairs(slots)):
            match = PlayoffMatch(
                bracket_id=bracket.id,
                round_number=1,
                slot_index=index,
                team1_id=a,
                team2_id=b,
                is_bye=(a is None or b is None),
                winner_team_id=(a or b) if (a is None or b is None) else None,
            )
            db.session.add(match)
            first_round.append(match)
        # Later rounds are empty until results arrive; a bye's winner is known
        # now, so it is written straight into the next round.
        previous = first_round
        for round_number in range(2, total_rounds + 1):
            slots_this_round = size // (2 ** round_number)
            current = []
            for index in range(slots_this_round):
                match = PlayoffMatch(
                    bracket_id=bracket.id, round_number=round_number, slot_index=index
                )
                db.session.add(match)
                current.append(match)
            for index, earlier in enumerate(previous):
                if earlier.winner_team_id:
                    target = current[index // 2]
                    if index % 2 == 0:
                        target.team1_id = earlier.winner_team_id
                    else:
                        target.team2_id = earlier.winner_team_id
            previous = current
        if config.consolation_enabled and total_rounds >= 2:
            db.session.add(
                PlayoffMatch(
                    bracket_id=bracket.id,
                    round_number=total_rounds,
                    slot_index=0,
                    is_consolation=True,
                )
            )

    config.drawn_at = datetime.datetime.utcnow()
    _log_admin_action(
        league.id, None, effective.id, "playoff_draw",
        f"{len(brackets)} bracket(s), {len(qualifier_ids)} teams, {total_rounds} round(s)",
    )
    db.session.commit()
    db.session.refresh(league)
    return jsonify(_bracket_tree(league))


def _bracket_tree(league):
    """The drawn brackets, round by round."""
    brackets = sorted(league.playoff_brackets, key=lambda b: b.bracket_number)
    teams = {t.id: t.name for t in league.teams}
    config = _config_for(league)
    qualifiers = sorted(league.playoff_qualifiers, key=lambda q: q.position)
    return {
        "rounds": rounds_needed(len(qualifiers)) if qualifiers else 0,
        "teams": teams,
        "drawn_at": (
            config.drawn_at.isoformat() + "Z" if config and config.drawn_at else None
        ),
        "brackets": [
            {
                **_serialize_bracket(bracket),
                "matches": [
                    _serialize_match(m)
                    for m in sorted(
                        bracket.matches,
                        key=lambda m: (m.round_number, m.is_consolation, m.slot_index),
                    )
                ],
            }
            for bracket in brackets
        ],
    }


@blueprint.route("/<int:league_id>/playoffs/brackets/tree", methods=["GET"])
def get_bracket_tree(league_id):
    """The drawn brackets, for display."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    return jsonify(_bracket_tree(league))


def _match_winner_team_id(match):
    """Which team won this playoff match, or None while it is undecided.

    A result has to be verified before it moves a team along: advancing on an
    unverified one would build the next round on something a captain has not
    agreed to yet.
    """
    if match.is_bye:
        return match.winner_team_id
    pm = match.player_matchup
    if pm is None or pm.is_double_loss or pm.result_confirmed_at is None:
        return None
    week = pm.week_matchup.week if pm.week_matchup else None
    best_of = week.best_of_n if week else 1
    wins_needed = (best_of // 2) + 1
    p1 = sum(1 for g in pm.games if g.winner_id == pm.player1_id)
    p2 = sum(1 for g in pm.games if g.winner_id == pm.player2_id)
    if p1 >= wins_needed:
        return match.team1_id
    if p2 >= wins_needed:
        return match.team2_id
    return None


def _resolve_round(bracket, round_number, total_rounds, consolation_enabled):
    """Write a finished round's winners into the next one.

    Returns the matches still waiting on a verified result.
    """
    matches = sorted(
        [
            m
            for m in bracket.matches
            if m.round_number == round_number and not m.is_consolation
        ],
        key=lambda m: m.slot_index,
    )
    next_round = {
        m.slot_index: m
        for m in bracket.matches
        if m.round_number == round_number + 1 and not m.is_consolation
    }
    consolation = next(
        (m for m in bracket.matches if m.is_consolation), None
    )
    pending = []
    for match in matches:
        winner = _match_winner_team_id(match)
        if winner is None:
            pending.append(match)
            continue
        match.winner_team_id = winner
        loser = match.team2_id if winner == match.team1_id else match.team1_id
        target = next_round.get(match.slot_index // 2)
        if target is not None:
            if match.slot_index % 2 == 0:
                target.team1_id = winner
            else:
                target.team2_id = winner
        # The consolation match is played by the losers of the round before the
        # final, which is this one when the final is next.
        if (
            consolation_enabled
            and consolation is not None
            and round_number + 1 == total_rounds
            and loser
        ):
            if match.slot_index == 0:
                consolation.team1_id = loser
            elif match.slot_index == 1:
                consolation.team2_id = loser
    return pending


def _player_for(bracket, team_id):
    assignment = next(
        (a for a in bracket.assignments if a.team_id == team_id), None
    )
    return assignment.user_id if assignment else None


@blueprint.route("/<int:league_id>/playoffs/rounds/<int:round_number>/start", methods=["POST"])
@login_required
def start_playoff_round(league_id, round_number):
    """Open a round: a week per bracket, and the matches it holds.

    Each bracket is its own format with its own constraints, which is what a
    week already is, so a round is one week per bracket. They are kept out of
    the ordinary week list and shown as brackets instead.
    """
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    effective = get_effective_user()
    if not _is_league_admin(league, effective):
        return jsonify({"error": "Admin access required"}), 403
    config = _config_for(league)
    if not _locked(config):
        return jsonify({"error": "Draw the brackets first"}), 400

    qualifiers = sorted(league.playoff_qualifiers, key=lambda q: q.position)
    total_rounds = rounds_needed(len(qualifiers))
    if round_number < 1 or round_number > total_rounds:
        return (
            jsonify({"error": f"This playoff has {total_rounds} round(s)"}),
            400,
        )

    brackets = sorted(league.playoff_brackets, key=lambda b: b.bracket_number)

    if round_number > 1:
        waiting = []
        for bracket in brackets:
            pending = _resolve_round(
                bracket, round_number - 1, total_rounds, config.consolation_enabled
            )
            for match in pending:
                label = bracket.name or f"Bracket {bracket.bracket_number}"
                waiting.append(label)
        if waiting:
            unique = sorted(set(waiting))
            return (
                jsonify(
                    {
                        "error": "Round "
                        f"{round_number - 1} is not finished and verified in: "
                        + ", ".join(unique[:6])
                        + ("..." if len(unique) > 6 else "")
                    }
                ),
                400,
            )
        db.session.flush()

    # week_number is unique per league, so each bracket-week takes the next
    # one rather than sharing a number with the rest of its round.
    next_number = max([w.week_number for w in league.weeks] or [0]) + 1
    created_weeks, created_matches = 0, 0
    for bracket in brackets:
        week = next(
            (
                w
                for w in league.weeks
                if w.playoff_bracket_id == bracket.id
                and w.playoff_round == round_number
            ),
            None,
        )
        if week is None:
            label = bracket.name or bracket.format_type
            week = LeagueWeek(
                league_id=league.id,
                week_number=next_number,
                name=f"{label} — Playoff round {round_number}",
                format_type=bracket.format_type,
                best_of_n=bracket.best_of_n,
                status=WeekStatus.DECK_SELECTION.value,
                playoff_bracket_id=bracket.id,
                playoff_round=round_number,
            )
            db.session.add(week)
            db.session.flush()
            next_number += 1
            created_weeks += 1

        matches = [
            m
            for m in bracket.matches
            if m.round_number == round_number
            and not m.is_bye
            and m.team1_id
            and m.team2_id
            and m.player_matchup_id is None
        ]
        for match in matches:
            player1 = _player_for(bracket, match.team1_id)
            player2 = _player_for(bracket, match.team2_id)
            if not player1 or not player2:
                continue
            wm = WeekMatchup(
                week_id=week.id, team1_id=match.team1_id, team2_id=match.team2_id
            )
            db.session.add(wm)
            db.session.flush()
            pm = PlayerMatchup(
                week_matchup_id=wm.id, player1_id=player1, player2_id=player2
            )
            db.session.add(pm)
            db.session.flush()
            match.player_matchup_id = pm.id
            created_matches += 1

    _log_admin_action(
        league.id, None, effective.id, "playoff_round_started",
        f"round {round_number}: {created_weeks} week(s), {created_matches} match(es)",
    )
    db.session.commit()
    db.session.refresh(league)
    tree = _bracket_tree(league)
    tree["started_round"] = round_number
    tree["weeks_created"] = created_weeks
    tree["matches_created"] = created_matches
    return jsonify(tree)
