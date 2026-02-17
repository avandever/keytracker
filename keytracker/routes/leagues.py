from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from keytracker.schema import (
    db,
    League,
    LeagueAdmin,
    LeagueSignup,
    LeagueStatus,
    SignupStatus,
    Team,
    TeamMember,
    DraftPick,
)
from keytracker.serializers import (
    serialize_league_summary,
    serialize_league_detail,
    serialize_team_detail,
    serialize_user_brief,
)
import datetime


blueprint = Blueprint("leagues", __name__, url_prefix="/api/v2/leagues")


def _is_league_admin(league):
    if not current_user.is_authenticated:
        return False
    return LeagueAdmin.query.filter_by(
        league_id=league.id, user_id=current_user.id
    ).first() is not None


def _get_league_or_404(league_id):
    league = db.session.get(League, league_id)
    if league is None:
        return None, (jsonify({"error": "League not found"}), 404)
    return league, None


@blueprint.route("/", methods=["GET"])
def list_leagues():
    leagues = League.query.order_by(League.created_at.desc()).all()
    return jsonify([serialize_league_summary(l) for l in leagues])


@blueprint.route("/", methods=["POST"])
@login_required
def create_league():
    if not current_user.is_league_admin:
        return jsonify({"error": "League admin permission required"}), 403
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    team_size = data.get("team_size")
    num_teams = data.get("num_teams")
    if not isinstance(team_size, int) or team_size < 1:
        return jsonify({"error": "team_size must be a positive integer"}), 400
    if not isinstance(num_teams, int) or num_teams < 2:
        return jsonify({"error": "num_teams must be at least 2"}), 400
    league = League(
        name=name,
        description=(data.get("description") or "").strip() or None,
        fee_amount=data.get("fee_amount"),
        team_size=team_size,
        num_teams=num_teams,
        status=LeagueStatus.SETUP.value,
        created_by_id=current_user.id,
    )
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=current_user.id))
    db.session.commit()
    db.session.refresh(league)
    return jsonify(serialize_league_detail(league)), 201


@blueprint.route("/<int:league_id>", methods=["GET"])
def get_league(league_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    data = serialize_league_detail(league)
    if current_user.is_authenticated:
        data["is_admin"] = _is_league_admin(league)
        signup = LeagueSignup.query.filter_by(
            league_id=league.id, user_id=current_user.id
        ).first()
        data["is_signed_up"] = signup is not None
        # Find user's team membership
        member = TeamMember.query.join(Team).filter(
            Team.league_id == league.id,
            TeamMember.user_id == current_user.id,
        ).first()
        data["my_team_id"] = member.team_id if member else None
        data["is_captain"] = member.is_captain if member else False
    else:
        data["is_admin"] = False
        data["is_signed_up"] = False
        data["my_team_id"] = None
        data["is_captain"] = False
    return jsonify(data)


@blueprint.route("/<int:league_id>", methods=["PUT"])
@login_required
def update_league(league_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league):
        return jsonify({"error": "Admin access required"}), 403
    if league.status != LeagueStatus.SETUP.value:
        return jsonify({"error": "Can only edit league during setup"}), 400
    data = request.get_json(silent=True) or {}
    if "name" in data:
        name = (data["name"] or "").strip()
        if name:
            league.name = name
    if "description" in data:
        league.description = (data["description"] or "").strip() or None
    if "fee_amount" in data:
        league.fee_amount = data["fee_amount"]
    if "team_size" in data:
        if isinstance(data["team_size"], int) and data["team_size"] >= 1:
            league.team_size = data["team_size"]
    if "num_teams" in data:
        if isinstance(data["num_teams"], int) and data["num_teams"] >= 2:
            league.num_teams = data["num_teams"]
    db.session.commit()
    db.session.refresh(league)
    return jsonify(serialize_league_detail(league))


# --- Signups ---

@blueprint.route("/<int:league_id>/signup", methods=["POST"])
@login_required
def signup(league_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if league.status != LeagueStatus.SETUP.value:
        return jsonify({"error": "Signups only during setup"}), 400
    existing = LeagueSignup.query.filter_by(
        league_id=league.id, user_id=current_user.id
    ).first()
    if existing:
        return jsonify({"error": "Already signed up"}), 409
    max_order = db.session.query(db.func.max(LeagueSignup.signup_order)).filter_by(
        league_id=league.id
    ).scalar() or 0
    signup_entry = LeagueSignup(
        league_id=league.id,
        user_id=current_user.id,
        signup_order=max_order + 1,
        status=SignupStatus.SIGNED_UP.value,
    )
    db.session.add(signup_entry)
    db.session.commit()
    return jsonify({"success": True}), 201


@blueprint.route("/<int:league_id>/signup", methods=["DELETE"])
@login_required
def withdraw(league_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if league.status != LeagueStatus.SETUP.value:
        return jsonify({"error": "Can only withdraw during setup"}), 400
    existing = LeagueSignup.query.filter_by(
        league_id=league.id, user_id=current_user.id
    ).first()
    if not existing:
        return jsonify({"error": "Not signed up"}), 404
    db.session.delete(existing)
    db.session.commit()
    return jsonify({"success": True})


# --- Teams ---

@blueprint.route("/<int:league_id>/teams", methods=["GET"])
def list_teams(league_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    teams = sorted(league.teams, key=lambda t: t.order_number)
    return jsonify([serialize_team_detail(t) for t in teams])


@blueprint.route("/<int:league_id>/teams", methods=["POST"])
@login_required
def create_team(league_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league):
        return jsonify({"error": "Admin access required"}), 403
    if len(league.teams) >= league.num_teams:
        return jsonify({"error": "Maximum number of teams reached"}), 400
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Team name is required"}), 400
    max_order = max((t.order_number for t in league.teams), default=0)
    team = Team(
        league_id=league.id,
        name=name,
        order_number=max_order + 1,
    )
    db.session.add(team)
    db.session.commit()
    db.session.refresh(team)
    return jsonify(serialize_team_detail(team)), 201


@blueprint.route("/<int:league_id>/teams/<int:team_id>", methods=["PUT"])
@login_required
def update_team(league_id, team_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    team = db.session.get(Team, team_id)
    if not team or team.league_id != league.id:
        return jsonify({"error": "Team not found"}), 404
    # Allow league admin or team captain
    is_captain = TeamMember.query.filter_by(
        team_id=team.id, user_id=current_user.id, is_captain=True
    ).first() is not None
    if not _is_league_admin(league) and not is_captain:
        return jsonify({"error": "Admin or captain access required"}), 403
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if name:
        team.name = name
    db.session.commit()
    return jsonify(serialize_team_detail(team))


@blueprint.route("/<int:league_id>/teams/<int:team_id>", methods=["DELETE"])
@login_required
def delete_team(league_id, team_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league):
        return jsonify({"error": "Admin access required"}), 403
    if league.status != LeagueStatus.SETUP.value:
        return jsonify({"error": "Can only delete teams during setup"}), 400
    team = db.session.get(Team, team_id)
    if not team or team.league_id != league.id:
        return jsonify({"error": "Team not found"}), 404
    db.session.delete(team)
    db.session.commit()
    return jsonify({"success": True})


# --- Captain assignment ---

@blueprint.route("/<int:league_id>/teams/<int:team_id>/captain", methods=["POST"])
@login_required
def assign_captain(league_id, team_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league):
        return jsonify({"error": "Admin access required"}), 403
    team = db.session.get(Team, team_id)
    if not team or team.league_id != league.id:
        return jsonify({"error": "Team not found"}), 404
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    # Verify user is signed up
    signup_entry = LeagueSignup.query.filter_by(
        league_id=league.id, user_id=user_id
    ).first()
    if not signup_entry:
        return jsonify({"error": "User must be signed up to be assigned as captain"}), 400
    # Remove existing captain
    TeamMember.query.filter_by(team_id=team.id, is_captain=True).update(
        {"is_captain": False}
    )
    # Add or update member
    member = TeamMember.query.filter_by(team_id=team.id, user_id=user_id).first()
    if member:
        member.is_captain = True
    else:
        # Remove from other teams in this league first
        TeamMember.query.filter(
            TeamMember.user_id == user_id,
            TeamMember.team_id.in_([t.id for t in league.teams]),
        ).delete(synchronize_session="fetch")
        member = TeamMember(
            team_id=team.id, user_id=user_id, is_captain=True
        )
        db.session.add(member)
    db.session.commit()
    db.session.refresh(team)
    return jsonify(serialize_team_detail(team))


# --- Fee tracking ---

@blueprint.route("/<int:league_id>/teams/<int:team_id>/fees/<int:user_id>", methods=["POST"])
@login_required
def toggle_fee_paid(league_id, team_id, user_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    team = db.session.get(Team, team_id)
    if not team or team.league_id != league.id:
        return jsonify({"error": "Team not found"}), 404
    is_captain = TeamMember.query.filter_by(
        team_id=team.id, user_id=current_user.id, is_captain=True
    ).first() is not None
    if not _is_league_admin(league) and not is_captain:
        return jsonify({"error": "Admin or captain access required"}), 403
    member = TeamMember.query.filter_by(team_id=team.id, user_id=user_id).first()
    if not member:
        return jsonify({"error": "Member not found"}), 404
    data = request.get_json(silent=True) or {}
    member.has_paid = bool(data.get("has_paid", not member.has_paid))
    db.session.commit()
    return jsonify(serialize_team_detail(team))


# --- League admins ---

@blueprint.route("/<int:league_id>/admins", methods=["POST"])
@login_required
def add_admin(league_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league):
        return jsonify({"error": "Admin access required"}), 403
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    existing = LeagueAdmin.query.filter_by(
        league_id=league.id, user_id=user_id
    ).first()
    if existing:
        return jsonify({"error": "Already an admin"}), 409
    db.session.add(LeagueAdmin(league_id=league.id, user_id=user_id))
    db.session.commit()
    return jsonify({"success": True}), 201


@blueprint.route("/<int:league_id>/admins/<int:user_id>", methods=["DELETE"])
@login_required
def remove_admin(league_id, user_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league):
        return jsonify({"error": "Admin access required"}), 403
    admin = LeagueAdmin.query.filter_by(
        league_id=league.id, user_id=user_id
    ).first()
    if not admin:
        return jsonify({"error": "Admin not found"}), 404
    # Don't allow removing the last admin
    admin_count = LeagueAdmin.query.filter_by(league_id=league.id).count()
    if admin_count <= 1:
        return jsonify({"error": "Cannot remove the last admin"}), 400
    db.session.delete(admin)
    db.session.commit()
    return jsonify({"success": True})
