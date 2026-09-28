"""Playoff setup: configuration, qualifying teams, brackets and assignments.

The playoffs run several brackets at once -- one per player on a team, each in
its own format, each advancing on its own -- so they need their own setup
before any of the week machinery can be pointed at them. This module covers
that setup; drawing the brackets and playing the rounds come after.
"""

import datetime
import json

from flask import Blueprint, jsonify, request
from flask_login import login_required

from keytracker.routes.leagues import (
    _get_league_or_404,
    _is_league_admin,
    _log_admin_action,
    get_effective_user,
)
from keytracker.schema import (
    PlayoffAssignment,
    PlayoffBracket,
    PlayoffByePolicy,
    PlayoffConfig,
    PlayoffQualifier,
    Team,
    TeamMember,
    User,
    WeekFormat,
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

    viewer = None
    try:
        viewer = get_effective_user()
    except Exception:  # noqa: BLE001 - anonymous viewers may read the setup
        viewer = None
    my_team_id = None
    is_captain = False
    if viewer is not None and getattr(viewer, "id", None):
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
