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
import logging

logger = logging.getLogger(__name__)

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
    logger.warning(
        "create_league called: user_id=%s, is_league_admin=%r, type=%s",
        current_user.id,
        current_user.is_league_admin,
        type(current_user.is_league_admin),
    )
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


# --- Draft system ---

def compute_draft_state(league):
    """Pure function: compute draft state from DraftPick records + team order."""
    teams = sorted(league.teams, key=lambda t: t.order_number)
    num_teams = len(teams)
    # Captains count as 1, so draft picks fill team_size - 1 slots
    picks_per_team = league.team_size - 1
    total_picks = picks_per_team * num_teams

    # Get existing picks ordered
    picks = (
        DraftPick.query.filter_by(league_id=league.id)
        .order_by(DraftPick.round_number, DraftPick.pick_number)
        .all()
    )

    # Build pick history
    pick_history = []
    picked_user_ids = set()
    for p in picks:
        pick_history.append({
            "round_number": p.round_number,
            "pick_number": p.pick_number,
            "team_id": p.team_id,
            "team_name": p.team.name if p.team else None,
            "picked_user": serialize_user_brief(p.picked_user) if p.picked_user else None,
            "picked_at": p.picked_at.isoformat() if p.picked_at else None,
        })
        picked_user_ids.add(p.picked_user_id)

    # Available players: signed_up status, not yet picked, not a captain
    captain_user_ids = set()
    for team in teams:
        for m in team.members:
            if m.is_captain:
                captain_user_ids.add(m.user_id)

    available = []
    for s in league.signups:
        if s.status == SignupStatus.DRAFTED.value and s.user_id not in picked_user_ids and s.user_id not in captain_user_ids:
            available.append(serialize_user_brief(s.user))

    # Compute current pick
    picks_made = len(picks)
    is_complete = picks_made >= total_picks

    current_round = None
    current_pick = None
    current_team = None
    if not is_complete and num_teams > 0:
        current_round = (picks_made // num_teams) + 1
        pick_in_round = picks_made % num_teams
        # Snake: odd rounds (1-indexed) go forward, even rounds go reverse
        if current_round % 2 == 1:
            current_team_idx = pick_in_round
        else:
            current_team_idx = num_teams - 1 - pick_in_round
        current_pick = pick_in_round + 1
        current_team = serialize_team_detail(teams[current_team_idx])

    # Build draft board (rounds x teams grid)
    draft_board = []
    for r in range(1, picks_per_team + 1):
        round_picks = []
        for t in teams:
            pick = next(
                (p for p in pick_history if p["round_number"] == r and p["team_id"] == t.id),
                None,
            )
            round_picks.append({
                "team_id": t.id,
                "team_name": t.name,
                "pick": pick,
            })
        draft_board.append({"round": r, "picks": round_picks})

    return {
        "league_id": league.id,
        "status": league.status,
        "is_complete": is_complete,
        "total_picks": total_picks,
        "picks_made": picks_made,
        "current_round": current_round,
        "current_pick": current_pick,
        "current_team": current_team,
        "available_players": available,
        "pick_history": pick_history,
        "draft_board": draft_board,
        "teams": [serialize_team_detail(t) for t in teams],
    }


@blueprint.route("/<int:league_id>/draft/start", methods=["POST"])
@login_required
def start_draft(league_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league):
        return jsonify({"error": "Admin access required"}), 403
    if league.status != LeagueStatus.SETUP.value:
        return jsonify({"error": "Draft can only start from setup status"}), 400

    teams = sorted(league.teams, key=lambda t: t.order_number)
    if len(teams) < 2:
        return jsonify({"error": "Need at least 2 teams"}), 400

    # Validate all teams have captains
    for team in teams:
        has_captain = any(m.is_captain for m in team.members)
        if not has_captain:
            return jsonify({"error": f"Team '{team.name}' has no captain"}), 400

    # Determine total spots: num_teams * team_size, minus captains (1 per team)
    total_draft_spots = league.num_teams * (league.team_size - 1)
    signups = sorted(league.signups, key=lambda s: s.signup_order)

    # Captain user IDs
    captain_ids = set()
    for team in teams:
        for m in team.members:
            if m.is_captain:
                captain_ids.add(m.user_id)

    # Non-captain signups
    non_captain_signups = [s for s in signups if s.user_id not in captain_ids]

    # Mark drafted vs waitlisted
    for i, s in enumerate(non_captain_signups):
        if i < total_draft_spots:
            s.status = SignupStatus.DRAFTED.value
        else:
            s.status = SignupStatus.WAITLISTED.value

    # Mark captain signups as drafted
    for s in signups:
        if s.user_id in captain_ids:
            s.status = SignupStatus.DRAFTED.value

    league.status = LeagueStatus.DRAFTING.value
    db.session.commit()
    return jsonify(compute_draft_state(league))


@blueprint.route("/<int:league_id>/draft", methods=["GET"])
@login_required
def get_draft(league_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    # Only captains and league admins can see draft board
    is_admin = _is_league_admin(league)
    is_captain = TeamMember.query.join(Team).filter(
        Team.league_id == league.id,
        TeamMember.user_id == current_user.id,
        TeamMember.is_captain == True,
    ).first() is not None
    if not is_admin and not is_captain:
        return jsonify({"error": "Captains and admins only"}), 403
    return jsonify(compute_draft_state(league))


@blueprint.route("/<int:league_id>/draft/pick", methods=["POST"])
@login_required
def make_pick(league_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if league.status != LeagueStatus.DRAFTING.value:
        return jsonify({"error": "Draft is not active"}), 400

    state = compute_draft_state(league)
    if state["is_complete"]:
        return jsonify({"error": "Draft is already complete"}), 400

    current_team_data = state["current_team"]
    if not current_team_data:
        return jsonify({"error": "No current team"}), 400

    # Check permission: must be captain of current team or league admin
    is_admin = _is_league_admin(league)
    is_current_captain = TeamMember.query.filter_by(
        team_id=current_team_data["id"],
        user_id=current_user.id,
        is_captain=True,
    ).first() is not None
    if not is_admin and not is_current_captain:
        return jsonify({"error": "Not your turn to pick"}), 403

    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    # Verify user is available
    available_ids = {p["id"] for p in state["available_players"]}
    if user_id not in available_ids:
        return jsonify({"error": "Player not available"}), 400

    # Create the pick
    pick = DraftPick(
        league_id=league.id,
        round_number=state["current_round"],
        pick_number=state["current_pick"],
        team_id=current_team_data["id"],
        picked_user_id=user_id,
    )
    db.session.add(pick)

    # Add to team
    member = TeamMember(
        team_id=current_team_data["id"],
        user_id=user_id,
        is_captain=False,
    )
    db.session.add(member)
    db.session.flush()

    # Check if draft is now complete
    new_state = compute_draft_state(league)
    if new_state["is_complete"]:
        league.status = LeagueStatus.ACTIVE.value

    db.session.commit()
    return jsonify(compute_draft_state(league))
