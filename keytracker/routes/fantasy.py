"""Fantasy league routes.

A fantasy league hangs off a real League but is run separately: its commissioner
need not be a league admin, and anyone with an account may enter whether or not
they are playing in the league itself.

Visibility follows one rule. Rosters are private until the league locks, because
the scarcity bonus depends on how many teams hold each player -- if entries were
public while drafting is open, a late entrant could count the field and pick into
the best band, or pile onto a rival's player to push them into the penalty. Once
locked, everything is public and permanent.
"""

import datetime
import json
import logging

from flask import Blueprint, jsonify, request
from flask_login import login_required

from keytracker.fantasy_service import (
    generate_player_costs,
    roster_validation_error,
    score_fantasy_league,
)
from keytracker.routes.leagues import get_effective_user
from keytracker.schema import (
    FantasyLeague,
    FantasyLeagueStatus,
    FantasyPlayerCost,
    FantasyRosterSlot,
    FantasyTeam,
    League,
    User,
    db,
)

logger = logging.getLogger(__name__)

blueprint = Blueprint("fantasy", __name__, url_prefix="/api/v2/fantasy")

# Statuses in which entries may be created or changed.
_ENTRY_OPEN = {FantasyLeagueStatus.OPEN.value}
_ROSTERS_PUBLIC = {
    FantasyLeagueStatus.LOCKED.value,
    FantasyLeagueStatus.COMPLETED.value,
}


def _get_or_404(fantasy_league_id):
    fl = db.session.get(FantasyLeague, fantasy_league_id)
    if not fl:
        return None, (jsonify({"error": "Fantasy league not found"}), 404)
    return fl, None


def _is_commissioner(fl, user=None):
    user = user or get_effective_user()
    return bool(
        user and getattr(user, "is_authenticated", False) and fl.commissioner_id == user.id
    )


def _rosters_visible_to(fl, user):
    """Everyone sees rosters once locked; before that, only your own."""
    return fl.status in _ROSTERS_PUBLIC


def _serialize_cost(row):
    return {
        "player_user_id": row.player_user_id,
        "player_name": row.player.name if row.player else None,
        "cost": row.cost,
        "is_new_player": row.is_new_player,
        "source_wins": row.source_wins,
    }


def _serialize_team(team, include_roster):
    data = {
        "id": team.id,
        "name": team.name,
        "manager_user_id": team.manager_user_id,
        "manager_name": team.manager.name if team.manager else None,
        "joined_week_number": team.joined_week_number,
        "roster_cost": sum(s.cost_at_draft for s in team.roster),
    }
    if include_roster:
        data["roster"] = [
            {
                "player_user_id": s.player_user_id,
                "player_name": s.player.name if s.player else None,
                "slot_number": s.slot_number,
                "is_captain": s.is_captain,
                "cost_at_draft": s.cost_at_draft,
                "is_new_at_draft": s.is_new_at_draft,
            }
            for s in sorted(team.roster, key=lambda s: s.slot_number)
        ]
    return data


def _serialize_league(fl, viewer=None, include_teams=True):
    viewer = viewer or get_effective_user()
    viewer_id = viewer.id if getattr(viewer, "is_authenticated", False) else None
    public = _rosters_visible_to(fl, viewer)
    data = {
        "id": fl.id,
        "league_id": fl.league_id,
        "league_name": fl.league.name if fl.league else None,
        "name": fl.name,
        "status": fl.status,
        "commissioner_id": fl.commissioner_id,
        "commissioner_name": fl.commissioner.name if fl.commissioner else None,
        "viewer_is_commissioner": _is_commissioner(fl, viewer),
        "roster_lock_at": (
            fl.roster_lock_at.isoformat() + "Z" if fl.roster_lock_at else None
        ),
        "allow_late_entry": fl.allow_late_entry,
        "roster_size": fl.roster_size,
        "salary_cap": fl.salary_cap,
        "cost_source_league_id": fl.cost_source_league_id,
        "cost_min": fl.cost_min,
        "cost_max": fl.cost_max,
        "points_per_match_win": fl.points_per_match_win,
        "weekly_threshold": fl.weekly_threshold,
        "weekly_threshold_bonus": fl.weekly_threshold_bonus,
        "captain_bonus_enabled": fl.captain_bonus_enabled,
        "feature_win_bonus": fl.feature_win_bonus,
        "scarcity_bonus_enabled": fl.scarcity_bonus_enabled,
        "scarcity_bands": (
            json.loads(fl.scarcity_bands) if fl.scarcity_bands else None
        ),
        "rosters_public": public,
        "team_count": len(fl.teams),
    }
    if include_teams:
        data["teams"] = [
            _serialize_team(
                t, include_roster=public or t.manager_user_id == viewer_id
            )
            for t in sorted(fl.teams, key=lambda t: t.name.lower())
        ]
    return data


# --------------------------------------------------------------------------
# Fantasy leagues
# --------------------------------------------------------------------------


@blueprint.route("/", methods=["GET"])
def list_fantasy_leagues():
    query = FantasyLeague.query
    league_id = request.args.get("league_id", type=int)
    if league_id:
        query = query.filter(FantasyLeague.league_id == league_id)
    leagues = query.order_by(FantasyLeague.created_at.desc()).all()
    return jsonify(
        [_serialize_league(fl, include_teams=False) for fl in leagues]
    )


@blueprint.route("/<int:fantasy_league_id>", methods=["GET"])
def get_fantasy_league(fantasy_league_id):
    fl, err = _get_or_404(fantasy_league_id)
    if err:
        return err
    return jsonify(_serialize_league(fl))


@blueprint.route("/", methods=["POST"])
@login_required
def create_fantasy_league():
    data = request.get_json(silent=True) or {}
    league_id = data.get("league_id")
    league = db.session.get(League, league_id) if league_id else None
    if not league:
        return jsonify({"error": "league_id must be an existing league"}), 400
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    effective = get_effective_user()
    fl = FantasyLeague(
        league_id=league.id,
        name=name,
        commissioner_id=effective.id,
        cost_source_league_id=data.get("cost_source_league_id"),
    )
    db.session.add(fl)
    db.session.commit()
    return jsonify(_serialize_league(fl)), 201


# Fields a commissioner may change, and how to coerce them.
_EDITABLE = {
    "name": lambda v: (v or "").strip() or None,
    "allow_late_entry": bool,
    "roster_size": int,
    "salary_cap": int,
    "cost_source_league_id": lambda v: int(v) if v is not None else None,
    "cost_min": int,
    "cost_max": int,
    "points_per_match_win": int,
    "weekly_threshold": lambda v: int(v) if v is not None else None,
    "weekly_threshold_bonus": int,
    "captain_bonus_enabled": bool,
    "feature_win_bonus": int,
    "scarcity_bonus_enabled": bool,
}


@blueprint.route("/<int:fantasy_league_id>", methods=["PUT"])
@login_required
def update_fantasy_league(fantasy_league_id):
    fl, err = _get_or_404(fantasy_league_id)
    if err:
        return err
    if not _is_commissioner(fl):
        return jsonify({"error": "Commissioner access required"}), 403

    data = request.get_json(silent=True) or {}
    # Rules that decide scores must not move once anyone has entered under
    # them, so scoring settings freeze at lock.
    locked = fl.status in _ROSTERS_PUBLIC
    scoring_fields = {
        "roster_size",
        "salary_cap",
        "cost_min",
        "cost_max",
        "points_per_match_win",
        "weekly_threshold",
        "weekly_threshold_bonus",
        "captain_bonus_enabled",
        "feature_win_bonus",
        "scarcity_bonus_enabled",
        "scarcity_bands",
    }
    for field, coerce in _EDITABLE.items():
        if field not in data:
            continue
        if locked and field in scoring_fields:
            return (
                jsonify(
                    {"error": f"{field} cannot change once the league is locked"}
                ),
                400,
            )
        try:
            setattr(fl, field, coerce(data[field]))
        except (TypeError, ValueError):
            return jsonify({"error": f"{field} is not valid"}), 400

    if "scarcity_bands" in data:
        if locked:
            return (
                jsonify(
                    {"error": "scarcity_bands cannot change once the league is locked"}
                ),
                400,
            )
        bands = data["scarcity_bands"]
        if bands is None:
            fl.scarcity_bands = None
        elif isinstance(bands, list) and all(
            isinstance(b, (list, tuple)) and len(b) == 2 for b in bands
        ):
            fl.scarcity_bands = json.dumps(bands)
        else:
            return (
                jsonify(
                    {"error": "scarcity_bands must be a list of [max_teams, points]"}
                ),
                400,
            )

    if "roster_lock_at" in data:
        raw = data["roster_lock_at"]
        if raw in (None, ""):
            fl.roster_lock_at = None
        else:
            try:
                parsed = datetime.datetime.fromisoformat(
                    str(raw).replace("Z", "+00:00")
                )
            except ValueError:
                return jsonify({"error": "roster_lock_at must be ISO 8601"}), 400
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            fl.roster_lock_at = parsed

    db.session.commit()
    return jsonify(_serialize_league(fl))


_ALLOWED_TRANSITIONS = {
    FantasyLeagueStatus.SETUP.value: {FantasyLeagueStatus.OPEN.value},
    FantasyLeagueStatus.OPEN.value: {
        FantasyLeagueStatus.SETUP.value,
        FantasyLeagueStatus.LOCKED.value,
    },
    FantasyLeagueStatus.LOCKED.value: {FantasyLeagueStatus.COMPLETED.value},
    FantasyLeagueStatus.COMPLETED.value: set(),
}


@blueprint.route("/<int:fantasy_league_id>/status", methods=["POST"])
@login_required
def set_status(fantasy_league_id):
    fl, err = _get_or_404(fantasy_league_id)
    if err:
        return err
    if not _is_commissioner(fl):
        return jsonify({"error": "Commissioner access required"}), 403

    target = (request.get_json(silent=True) or {}).get("status")
    valid = {s.value for s in FantasyLeagueStatus}
    if target not in valid:
        return jsonify({"error": f"status must be one of {sorted(valid)}"}), 400
    if target not in _ALLOWED_TRANSITIONS.get(fl.status, set()):
        return (
            jsonify({"error": f"Cannot move from {fl.status} to {target}"}),
            400,
        )
    if target == FantasyLeagueStatus.OPEN.value and not fl.player_costs:
        return (
            jsonify({"error": "Generate player costs before opening for entries"}),
            400,
        )

    fl.status = target
    db.session.commit()
    return jsonify(_serialize_league(fl))


# --------------------------------------------------------------------------
# Player costs
# --------------------------------------------------------------------------


@blueprint.route("/<int:fantasy_league_id>/costs", methods=["GET"])
def get_costs(fantasy_league_id):
    fl, err = _get_or_404(fantasy_league_id)
    if err:
        return err
    # Costs are the price list everyone drafts against, so they are public as
    # soon as they exist -- only the commissioner sees them during setup.
    if fl.status == FantasyLeagueStatus.SETUP.value and not _is_commissioner(fl):
        return jsonify([])
    rows = sorted(fl.player_costs, key=lambda r: ((r.player.name or "").lower()))
    return jsonify([_serialize_cost(r) for r in rows])


@blueprint.route("/<int:fantasy_league_id>/costs/generate", methods=["POST"])
@login_required
def regenerate_costs(fantasy_league_id):
    fl, err = _get_or_404(fantasy_league_id)
    if err:
        return err
    if not _is_commissioner(fl):
        return jsonify({"error": "Commissioner access required"}), 403
    if fl.status != FantasyLeagueStatus.SETUP.value:
        return (
            jsonify({"error": "Costs can only be regenerated during setup"}),
            400,
        )
    generate_player_costs(fl)
    db.session.commit()
    rows = sorted(fl.player_costs, key=lambda r: ((r.player.name or "").lower()))
    return jsonify([_serialize_cost(r) for r in rows])


@blueprint.route(
    "/<int:fantasy_league_id>/costs/<int:player_user_id>", methods=["PUT"]
)
@login_required
def update_cost(fantasy_league_id, player_user_id):
    fl, err = _get_or_404(fantasy_league_id)
    if err:
        return err
    if not _is_commissioner(fl):
        return jsonify({"error": "Commissioner access required"}), 403
    if fl.status != FantasyLeagueStatus.SETUP.value:
        return jsonify({"error": "Costs can only be edited during setup"}), 400

    row = FantasyPlayerCost.query.filter_by(
        fantasy_league_id=fl.id, player_user_id=player_user_id
    ).first()
    if not row:
        return jsonify({"error": "Player not found in this fantasy league"}), 404

    data = request.get_json(silent=True) or {}
    if "cost" in data:
        try:
            row.cost = int(data["cost"])
        except (TypeError, ValueError):
            return jsonify({"error": "cost must be an integer"}), 400
        if row.cost < 0:
            return jsonify({"error": "cost cannot be negative"}), 400
    if "is_new_player" in data:
        row.is_new_player = bool(data["is_new_player"])
    db.session.commit()
    return jsonify(_serialize_cost(row))


# --------------------------------------------------------------------------
# Entries
# --------------------------------------------------------------------------


@blueprint.route("/<int:fantasy_league_id>/teams/mine", methods=["GET"])
@login_required
def get_my_team(fantasy_league_id):
    fl, err = _get_or_404(fantasy_league_id)
    if err:
        return err
    effective = get_effective_user()
    team = FantasyTeam.query.filter_by(
        fantasy_league_id=fl.id, manager_user_id=effective.id
    ).first()
    if not team:
        return jsonify(None)
    return jsonify(_serialize_team(team, include_roster=True))


@blueprint.route("/<int:fantasy_league_id>/teams", methods=["POST"])
@login_required
def submit_entry(fantasy_league_id):
    """Create or replace the caller's entry.

    Replacing wholesale rather than editing slot by slot keeps the cap check
    honest: a roster is only ever written after it has been validated as a
    complete, legal team.
    """
    fl, err = _get_or_404(fantasy_league_id)
    if err:
        return err
    if fl.status not in _ENTRY_OPEN:
        return (
            jsonify({"error": "This fantasy league is not accepting entries"}),
            400,
        )

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Team name is required"}), 400
    player_ids = data.get("player_user_ids")
    if not isinstance(player_ids, list) or not all(
        isinstance(p, int) for p in player_ids
    ):
        return jsonify({"error": "player_user_ids must be a list of user ids"}), 400
    captain_id = data.get("captain_user_id")

    problem = roster_validation_error(fl, player_ids, captain_id)
    if problem:
        return jsonify({"error": problem}), 400

    effective = get_effective_user()
    team = FantasyTeam.query.filter_by(
        fantasy_league_id=fl.id, manager_user_id=effective.id
    ).first()
    if team:
        for slot in list(team.roster):
            db.session.delete(slot)
        team.name = name
    else:
        team = FantasyTeam(
            fantasy_league_id=fl.id,
            manager_user_id=effective.id,
            name=name,
        )
        # Record a mid-season entry so standings can mark it. Scoring still
        # counts every week; the cap does the balancing.
        current = _current_week_number(fl)
        if current and current > 1:
            team.joined_week_number = current
        db.session.add(team)
        db.session.flush()

    costs = {
        r.player_user_id: r
        for r in FantasyPlayerCost.query.filter_by(fantasy_league_id=fl.id).all()
    }
    for index, player_id in enumerate(player_ids, start=1):
        row = costs[player_id]
        db.session.add(
            FantasyRosterSlot(
                fantasy_team_id=team.id,
                player_user_id=player_id,
                slot_number=index,
                is_captain=(player_id == captain_id),
                cost_at_draft=row.cost,
                is_new_at_draft=row.is_new_player,
            )
        )
    db.session.commit()
    return jsonify(_serialize_team(team, include_roster=True)), 201


@blueprint.route("/<int:fantasy_league_id>/teams/mine", methods=["DELETE"])
@login_required
def withdraw_entry(fantasy_league_id):
    fl, err = _get_or_404(fantasy_league_id)
    if err:
        return err
    if fl.status not in _ENTRY_OPEN:
        return (
            jsonify({"error": "Entries can no longer be withdrawn"}),
            400,
        )
    effective = get_effective_user()
    team = FantasyTeam.query.filter_by(
        fantasy_league_id=fl.id, manager_user_id=effective.id
    ).first()
    if not team:
        return jsonify({"error": "You have no entry in this fantasy league"}), 404
    db.session.delete(team)
    db.session.commit()
    return jsonify({"status": "withdrawn"})


# --------------------------------------------------------------------------
# Standings
# --------------------------------------------------------------------------


@blueprint.route("/<int:fantasy_league_id>/standings", methods=["GET"])
def standings(fantasy_league_id):
    fl, err = _get_or_404(fantasy_league_id)
    if err:
        return err
    # Before lock, publishing standings would leak the rosters they are
    # computed from.
    if fl.status not in _ROSTERS_PUBLIC:
        return jsonify({"status": fl.status, "standings": []})

    teams = {t.id: t for t in fl.teams}
    rows = []
    for rank, (team_id, score) in enumerate(score_fantasy_league(fl), 1):
        team = teams.get(team_id)
        if not team:
            continue
        rows.append(
            {
                "rank": rank,
                "team_id": team_id,
                "team_name": team.name,
                "manager_name": team.manager.name if team.manager else None,
                "joined_week_number": team.joined_week_number,
                "match_wins": score.match_wins,
                "weekly_bonus": score.weekly_bonus,
                "captain_bonus": score.captain_bonus,
                "scarcity_bonus": score.scarcity_bonus,
                "feature_bonus": score.feature_bonus,
                "total": score.total,
                "roster_cost": score.roster_cost,
                "weekly": score.weekly,
            }
        )
    return jsonify({"status": fl.status, "standings": rows})


def _current_week_number(fl):
    """The week the real league is currently playing, if any."""
    league = fl.league
    if not league:
        return None
    live = [
        w
        for w in (league.weeks or [])
        if w.status not in ("setup", "completed")
    ]
    if live:
        return min(w.week_number for w in live)
    played = [w for w in (league.weeks or []) if w.status == "completed"]
    return max((w.week_number for w in played), default=None)
