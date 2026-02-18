from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from keytracker.schema import (
    db,
    Deck,
    KeyforgeSet,
    League,
    LeagueAdmin,
    LeagueSignup,
    LeagueStatus,
    LeagueWeek,
    WeekMatchup,
    PlayerMatchup,
    PlayerDeckSelection,
    MatchGame,
    SignupStatus,
    WeekFormat,
    WeekStatus,
    Team,
    TeamMember,
    DraftPick,
    User,
)
from keytracker.serializers import (
    serialize_league_summary,
    serialize_league_detail,
    serialize_league_week,
    serialize_week_matchup,
    serialize_player_matchup,
    serialize_deck_selection,
    serialize_match_game,
    serialize_team_detail,
    serialize_user_brief,
)
import datetime
import json
import logging
import math
import random
import re

logger = logging.getLogger(__name__)

blueprint = Blueprint("leagues", __name__, url_prefix="/api/v2/leagues")


def get_effective_user():
    """Return the effective user for league operations.

    If the X-Test-User-Id header is present, validates that the real current_user
    is a league admin and the target is a test user, then returns the test user.
    Otherwise returns current_user.
    """
    test_user_id = request.headers.get("X-Test-User-Id")
    if not test_user_id:
        return current_user
    if not current_user.is_authenticated or not current_user.is_league_admin:
        return current_user
    try:
        test_user_id = int(test_user_id)
    except (ValueError, TypeError):
        return current_user
    test_user = db.session.get(User, test_user_id)
    if not test_user or not test_user.is_test_user:
        return current_user
    return test_user


def _is_league_admin(league, user=None):
    user = user or current_user
    if not hasattr(user, "is_authenticated") or not user.is_authenticated:
        # Test users from get_effective_user() are plain User objects (not UserMixin login)
        # so check by id directly
        pass
    return LeagueAdmin.query.filter_by(
        league_id=league.id, user_id=user.id
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
        is_test=bool(data.get("is_test", False)),
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
    effective = get_effective_user()
    if current_user.is_authenticated:
        data["is_admin"] = _is_league_admin(league, effective)
        signup = LeagueSignup.query.filter_by(
            league_id=league.id, user_id=effective.id
        ).first()
        data["is_signed_up"] = signup is not None
        # Find user's team membership
        member = TeamMember.query.join(Team).filter(
            Team.league_id == league.id,
            TeamMember.user_id == effective.id,
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
    if not _is_league_admin(league, get_effective_user()):
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
    effective = get_effective_user()
    existing = LeagueSignup.query.filter_by(
        league_id=league.id, user_id=effective.id
    ).first()
    if existing:
        return jsonify({"error": "Already signed up"}), 409
    max_order = db.session.query(db.func.max(LeagueSignup.signup_order)).filter_by(
        league_id=league.id
    ).scalar() or 0
    signup_entry = LeagueSignup(
        league_id=league.id,
        user_id=effective.id,
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
    effective = get_effective_user()
    existing = LeagueSignup.query.filter_by(
        league_id=league.id, user_id=effective.id
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
    if not _is_league_admin(league, get_effective_user()):
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
    effective = get_effective_user()
    # Allow league admin or team captain
    is_captain = TeamMember.query.filter_by(
        team_id=team.id, user_id=effective.id, is_captain=True
    ).first() is not None
    if not _is_league_admin(league, effective) and not is_captain:
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
    if not _is_league_admin(league, get_effective_user()):
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
    if not _is_league_admin(league, get_effective_user()):
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
    effective = get_effective_user()
    is_captain = TeamMember.query.filter_by(
        team_id=team.id, user_id=effective.id, is_captain=True
    ).first() is not None
    if not _is_league_admin(league, effective) and not is_captain:
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
    if not _is_league_admin(league, get_effective_user()):
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
    if not _is_league_admin(league, get_effective_user()):
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
    if not _is_league_admin(league, get_effective_user()):
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
    effective = get_effective_user()
    # Only captains and league admins can see draft board
    is_admin = _is_league_admin(league, effective)
    is_captain = TeamMember.query.join(Team).filter(
        Team.league_id == league.id,
        TeamMember.user_id == effective.id,
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
    effective = get_effective_user()
    is_admin = _is_league_admin(league, effective)
    is_current_captain = TeamMember.query.filter_by(
        team_id=current_team_data["id"],
        user_id=effective.id,
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


# --- Test users ---

@blueprint.route("/test-users", methods=["GET"])
@login_required
def list_test_users():
    if not current_user.is_league_admin:
        return jsonify({"error": "League admin permission required"}), 403
    test_users = User.query.filter_by(is_test_user=True).order_by(User.id).all()
    return jsonify([serialize_user_brief(u) for u in test_users])


# --- Sets reference ---

@blueprint.route("/sets", methods=["GET"])
def list_sets():
    sets = KeyforgeSet.query.order_by(KeyforgeSet.number).all()
    return jsonify([
        {"number": s.number, "name": s.name, "shortname": s.shortname}
        for s in sets
    ])


# --- Week management ---

def _get_active_players(league):
    """Get all non-waitlisted players in the league (team members)."""
    players = []
    for team in league.teams:
        for member in team.members:
            players.append(member)
    return players


def _generate_round_robin(teams):
    """Generate round-robin pairings using the circle method.

    Returns list of rounds, each round is a list of (team1, team2) tuples.
    """
    team_list = list(teams)
    n = len(team_list)
    if n < 2:
        return []
    # If odd number of teams, add a bye (None)
    if n % 2 == 1:
        team_list.append(None)
        n += 1

    rounds = []
    # Fix first team, rotate the rest
    fixed = team_list[0]
    rotating = team_list[1:]
    for _ in range(n - 1):
        round_pairings = []
        # First pairing: fixed vs last in rotating
        round_pairings.append((fixed, rotating[-1]))
        # Pair from outside in
        for j in range(len(rotating) // 2):
            if j < len(rotating) - 1 - j:
                round_pairings.append((rotating[j], rotating[len(rotating) - 2 - j]))
        rounds.append(round_pairings)
        # Rotate: move last element to front
        rotating = [rotating[-1]] + rotating[:-1]
    # Filter out byes
    rounds = [
        [(a, b) for a, b in r if a is not None and b is not None]
        for r in rounds
    ]
    return rounds


def _compute_player_strength(user_id, league_id):
    """Compute player strength for pairing purposes.

    Strength = match wins + sum(opponent_strength * 0.01)
    """
    # Find all completed player matchups for this user in this league
    completed_matchups = (
        PlayerMatchup.query
        .join(WeekMatchup)
        .join(LeagueWeek)
        .filter(
            LeagueWeek.league_id == league_id,
            LeagueWeek.status == WeekStatus.COMPLETED.value,
            db.or_(
                PlayerMatchup.player1_id == user_id,
                PlayerMatchup.player2_id == user_id,
            ),
        )
        .all()
    )

    wins = 0
    opponent_ids = []
    for pm in completed_matchups:
        opponent_id = pm.player2_id if pm.player1_id == user_id else pm.player1_id
        opponent_ids.append(opponent_id)
        # Count games won
        games_won = sum(1 for g in pm.games if g.winner_id == user_id)
        games_lost = sum(1 for g in pm.games if g.winner_id != user_id)
        if games_won > games_lost:
            wins += 1

    # Strength of schedule
    sos_bonus = 0.0
    for opp_id in opponent_ids:
        opp_wins = 0
        opp_matchups = (
            PlayerMatchup.query
            .join(WeekMatchup)
            .join(LeagueWeek)
            .filter(
                LeagueWeek.league_id == league_id,
                LeagueWeek.status == WeekStatus.COMPLETED.value,
                db.or_(
                    PlayerMatchup.player1_id == opp_id,
                    PlayerMatchup.player2_id == opp_id,
                ),
            )
            .all()
        )
        for opm in opp_matchups:
            g_won = sum(1 for g in opm.games if g.winner_id == opp_id)
            g_lost = sum(1 for g in opm.games if g.winner_id != opp_id)
            if g_won > g_lost:
                opp_wins += 1
        sos_bonus += opp_wins * 0.01

    return wins + sos_bonus


def _generate_player_pairings(team1, team2, league, week_number):
    """Generate player pairings within a team matchup.

    Week 1: random. Week 2+: strength-based.
    """
    members1 = list(team1.members)
    members2 = list(team2.members)

    if week_number == 1:
        random.shuffle(members1)
        random.shuffle(members2)
    else:
        # Sort by strength descending, randomize ties
        def strength_key(m):
            s = _compute_player_strength(m.user_id, league.id)
            return (-s, random.random())
        members1.sort(key=strength_key)
        members2.sort(key=strength_key)

    pairings = []
    for i in range(min(len(members1), len(members2))):
        pairings.append((members1[i].user_id, members2[i].user_id))
    return pairings


def _parse_deck_url(url_str):
    """Extract kf_id from a deck URL or raw ID."""
    url_str = url_str.strip()
    # Try keyforgegame.com/deck-details/{id}
    m = re.search(r'keyforgegame\.com/deck-details/([a-f0-9-]+)', url_str)
    if m:
        return m.group(1)
    # Try decksofkeyforge.com/decks/{id}
    m = re.search(r'decksofkeyforge\.com/decks/([a-f0-9-]+)', url_str)
    if m:
        return m.group(1)
    # Try raw UUID
    m = re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', url_str)
    if m:
        return url_str
    return None


@blueprint.route("/<int:league_id>/weeks", methods=["POST"])
@login_required
def create_week(league_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league, get_effective_user()):
        return jsonify({"error": "Admin access required"}), 403
    if league.status != LeagueStatus.ACTIVE.value:
        return jsonify({"error": "League must be active"}), 400

    data = request.get_json(silent=True) or {}
    format_type = data.get("format_type", "")
    valid_formats = [f.value for f in WeekFormat]
    if format_type not in valid_formats:
        return jsonify({"error": f"format_type must be one of: {valid_formats}"}), 400

    best_of_n = data.get("best_of_n", 1)
    if not isinstance(best_of_n, int) or best_of_n < 1 or best_of_n % 2 == 0:
        return jsonify({"error": "best_of_n must be a positive odd integer"}), 400

    # Determine next week number
    max_week = db.session.query(db.func.max(LeagueWeek.week_number)).filter_by(
        league_id=league.id
    ).scalar() or 0

    allowed_sets = data.get("allowed_sets")
    allowed_sets_json = None
    if allowed_sets and isinstance(allowed_sets, list):
        allowed_sets_json = json.dumps(allowed_sets)

    week = LeagueWeek(
        league_id=league.id,
        week_number=max_week + 1,
        format_type=format_type,
        status=WeekStatus.SETUP.value,
        best_of_n=best_of_n,
        allowed_sets=allowed_sets_json,
        max_sas=data.get("max_sas"),
        combined_max_sas=data.get("combined_max_sas"),
        set_diversity=data.get("set_diversity"),
        house_diversity=data.get("house_diversity"),
        decks_per_player=data.get("decks_per_player"),
    )
    db.session.add(week)
    db.session.commit()
    db.session.refresh(week)
    return jsonify(serialize_league_week(week)), 201


@blueprint.route("/<int:league_id>/weeks", methods=["GET"])
def list_weeks(league_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    weeks = LeagueWeek.query.filter_by(league_id=league.id).order_by(
        LeagueWeek.week_number
    ).all()
    return jsonify([serialize_league_week(w) for w in weeks])


@blueprint.route("/<int:league_id>/weeks/<int:week_id>", methods=["GET"])
def get_week(league_id, week_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    viewer = get_effective_user() if current_user.is_authenticated else None
    return jsonify(serialize_league_week(week, viewer=viewer))


@blueprint.route("/<int:league_id>/weeks/<int:week_id>", methods=["PUT"])
@login_required
def update_week(league_id, week_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league, get_effective_user()):
        return jsonify({"error": "Admin access required"}), 403
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.status != WeekStatus.SETUP.value:
        return jsonify({"error": "Can only edit week during setup"}), 400

    data = request.get_json(silent=True) or {}
    if "format_type" in data:
        valid_formats = [f.value for f in WeekFormat]
        if data["format_type"] in valid_formats:
            week.format_type = data["format_type"]
    if "best_of_n" in data:
        bon = data["best_of_n"]
        if isinstance(bon, int) and bon >= 1 and bon % 2 == 1:
            week.best_of_n = bon
    if "allowed_sets" in data:
        if data["allowed_sets"] and isinstance(data["allowed_sets"], list):
            week.allowed_sets = json.dumps(data["allowed_sets"])
        else:
            week.allowed_sets = None
    if "max_sas" in data:
        week.max_sas = data["max_sas"]
    if "combined_max_sas" in data:
        week.combined_max_sas = data["combined_max_sas"]
    if "set_diversity" in data:
        week.set_diversity = data["set_diversity"]
    if "house_diversity" in data:
        week.house_diversity = data["house_diversity"]
    if "decks_per_player" in data:
        week.decks_per_player = data["decks_per_player"]

    db.session.commit()
    db.session.refresh(week)
    return jsonify(serialize_league_week(week))


# --- Week status transitions ---

@blueprint.route("/<int:league_id>/weeks/<int:week_id>/open-deck-selection", methods=["POST"])
@login_required
def open_deck_selection(league_id, week_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league, get_effective_user()):
        return jsonify({"error": "Admin access required"}), 403
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.status != WeekStatus.SETUP.value:
        return jsonify({"error": "Week must be in setup status"}), 400

    week.status = WeekStatus.DECK_SELECTION.value
    db.session.commit()
    return jsonify(serialize_league_week(week))


@blueprint.route("/<int:league_id>/weeks/<int:week_id>/generate-matchups", methods=["POST"])
@login_required
def generate_matchups(league_id, week_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league, get_effective_user()):
        return jsonify({"error": "Admin access required"}), 403
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.status != WeekStatus.DECK_SELECTION.value:
        return jsonify({"error": "Week must be in deck_selection status"}), 400

    # Check previous week is completed (unless week 1)
    if week.week_number > 1:
        prev_week = LeagueWeek.query.filter_by(
            league_id=league.id, week_number=week.week_number - 1
        ).first()
        if prev_week and prev_week.status != WeekStatus.COMPLETED.value:
            return jsonify({"error": "Previous week must be completed first"}), 400

    # Check all players have submitted deck selections
    required_slots = 3 if week.format_type == WeekFormat.TRIAD.value else 1
    active_members = _get_active_players(league)
    for member in active_members:
        selections = PlayerDeckSelection.query.filter_by(
            week_id=week.id, user_id=member.user_id
        ).count()
        if selections < required_slots:
            user = db.session.get(User, member.user_id)
            name = user.name if user else f"User {member.user_id}"
            return jsonify({"error": f"{name} has not submitted all deck selections ({selections}/{required_slots})"}), 400

    # Delete existing matchups for this week (in case of re-generation)
    WeekMatchup.query.filter_by(week_id=week.id).delete()
    db.session.flush()

    # Generate round-robin team pairings
    teams = sorted(league.teams, key=lambda t: t.order_number)
    all_rounds = _generate_round_robin(teams)

    # Use the round corresponding to this week
    round_idx = week.week_number - 1
    if round_idx >= len(all_rounds):
        return jsonify({"error": "No more round-robin pairings available for this week number"}), 400

    round_pairings = all_rounds[round_idx]

    for team1, team2 in round_pairings:
        wm = WeekMatchup(
            week_id=week.id,
            team1_id=team1.id,
            team2_id=team2.id,
        )
        db.session.add(wm)
        db.session.flush()

        # Generate player pairings
        player_pairs = _generate_player_pairings(team1, team2, league, week.week_number)
        for p1_id, p2_id in player_pairs:
            pm = PlayerMatchup(
                week_matchup_id=wm.id,
                player1_id=p1_id,
                player2_id=p2_id,
            )
            db.session.add(pm)

    week.status = WeekStatus.PAIRING.value
    db.session.commit()
    db.session.refresh(week)
    return jsonify(serialize_league_week(week))


@blueprint.route("/<int:league_id>/weeks/<int:week_id>/matchups/<int:matchup_id>", methods=["PUT"])
@login_required
def edit_matchup(league_id, week_id, matchup_id):
    """Admin endpoint to edit player pairings during PAIRING status."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league, get_effective_user()):
        return jsonify({"error": "Admin access required"}), 403
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.status != WeekStatus.PAIRING.value:
        return jsonify({"error": "Can only edit matchups during pairing"}), 400

    pm = db.session.get(PlayerMatchup, matchup_id)
    if not pm or pm.week_matchup.week_id != week.id:
        return jsonify({"error": "Matchup not found"}), 404

    data = request.get_json(silent=True) or {}
    if "player1_id" in data:
        pm.player1_id = data["player1_id"]
    if "player2_id" in data:
        pm.player2_id = data["player2_id"]
    db.session.commit()
    return jsonify(serialize_player_matchup(pm))


@blueprint.route("/<int:league_id>/weeks/<int:week_id>/publish", methods=["POST"])
@login_required
def publish_week(league_id, week_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league, get_effective_user()):
        return jsonify({"error": "Admin access required"}), 403
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.status != WeekStatus.PAIRING.value:
        return jsonify({"error": "Week must be in pairing status"}), 400

    # Verify all deck selections are in
    required_slots = 3 if week.format_type == WeekFormat.TRIAD.value else 1
    active_members = _get_active_players(league)
    for member in active_members:
        selections = PlayerDeckSelection.query.filter_by(
            week_id=week.id, user_id=member.user_id
        ).count()
        if selections < required_slots:
            user = db.session.get(User, member.user_id)
            name = user.name if user else f"User {member.user_id}"
            return jsonify({"error": f"{name} has not submitted all deck selections"}), 400

    week.status = WeekStatus.PUBLISHED.value
    db.session.commit()
    return jsonify(serialize_league_week(week))


# --- Deck selection ---

@blueprint.route("/<int:league_id>/weeks/<int:week_id>/deck-selection", methods=["POST"])
@login_required
def submit_deck_selection(league_id, week_id):
    from keytracker.utils import get_deck_by_id_with_zeal

    league, err = _get_league_or_404(league_id)
    if err:
        return err
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404

    if week.status not in (WeekStatus.DECK_SELECTION.value, WeekStatus.PAIRING.value):
        return jsonify({"error": "Deck selection is not open"}), 400

    effective = get_effective_user()

    # Check user is a league member (or admin/captain submitting for teammate)
    data = request.get_json(silent=True) or {}
    target_user_id = data.get("user_id", effective.id)

    # If submitting for another user, must be admin or captain of that user's team
    if target_user_id != effective.id:
        is_admin = _is_league_admin(league, effective)
        is_captain_of_team = False
        for team in league.teams:
            team_user_ids = {m.user_id for m in team.members}
            if target_user_id in team_user_ids:
                if any(m.user_id == effective.id and m.is_captain for m in team.members):
                    is_captain_of_team = True
                break
        if not is_admin and not is_captain_of_team:
            return jsonify({"error": "Cannot submit deck selection for this user"}), 403

    # Verify target user is in the league
    member = TeamMember.query.join(Team).filter(
        Team.league_id == league.id,
        TeamMember.user_id == target_user_id,
    ).first()
    if not member:
        return jsonify({"error": "User is not a member of this league"}), 400

    deck_url = (data.get("deck_url") or "").strip()
    if not deck_url:
        return jsonify({"error": "deck_url is required"}), 400

    kf_id = _parse_deck_url(deck_url)
    if not kf_id:
        return jsonify({"error": "Could not parse deck ID from URL"}), 400

    slot_number = data.get("slot_number", 1)
    max_slots = 3 if week.format_type == WeekFormat.TRIAD.value else 1
    if not isinstance(slot_number, int) or slot_number < 1 or slot_number > max_slots:
        return jsonify({"error": f"slot_number must be between 1 and {max_slots}"}), 400

    # Fetch/ensure deck in DB
    try:
        deck = get_deck_by_id_with_zeal(kf_id)
    except Exception as e:
        logger.error("Failed to fetch deck %s: %s", kf_id, e)
        return jsonify({"error": f"Failed to fetch deck: {str(e)}"}), 400

    # Validate allowed sets
    if week.allowed_sets:
        try:
            allowed = json.loads(week.allowed_sets)
            if deck.expansion not in allowed:
                return jsonify({"error": f"Deck set ({deck.expansion}) is not in the allowed sets for this week"}), 400
        except (json.JSONDecodeError, TypeError):
            pass

    # Validate max SAS
    if week.max_sas is not None:
        sas = deck.sas_rating
        if sas and sas > week.max_sas:
            return jsonify({"error": f"Deck SAS ({sas}) exceeds max SAS ({week.max_sas})"}), 400

    # Upsert the selection
    existing = PlayerDeckSelection.query.filter_by(
        week_id=week.id, user_id=target_user_id, slot_number=slot_number
    ).first()
    if existing:
        existing.deck_id = deck.id
    else:
        sel = PlayerDeckSelection(
            week_id=week.id,
            user_id=target_user_id,
            deck_id=deck.id,
            slot_number=slot_number,
        )
        db.session.add(sel)

    db.session.commit()

    # Return all selections for this user/week
    selections = PlayerDeckSelection.query.filter_by(
        week_id=week.id, user_id=target_user_id
    ).order_by(PlayerDeckSelection.slot_number).all()
    return jsonify([serialize_deck_selection(s) for s in selections])


@blueprint.route("/<int:league_id>/weeks/<int:week_id>/deck-selection/<int:slot>", methods=["DELETE"])
@login_required
def remove_deck_selection(league_id, week_id, slot):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404

    if week.status not in (WeekStatus.DECK_SELECTION.value, WeekStatus.PAIRING.value):
        return jsonify({"error": "Deck selection is not open"}), 400

    effective = get_effective_user()

    # Also allow user_id in query params for captain/admin
    target_user_id = request.args.get("user_id", type=int) or effective.id

    if target_user_id != effective.id:
        is_admin = _is_league_admin(league, effective)
        is_captain_of_team = False
        for team in league.teams:
            team_user_ids = {m.user_id for m in team.members}
            if target_user_id in team_user_ids:
                if any(m.user_id == effective.id and m.is_captain for m in team.members):
                    is_captain_of_team = True
                break
        if not is_admin and not is_captain_of_team:
            return jsonify({"error": "Cannot remove deck selection for this user"}), 403

    sel = PlayerDeckSelection.query.filter_by(
        week_id=week.id, user_id=target_user_id, slot_number=slot
    ).first()
    if not sel:
        return jsonify({"error": "Selection not found"}), 404

    db.session.delete(sel)
    db.session.commit()
    return jsonify({"success": True})


# --- Match flow ---

@blueprint.route("/<int:league_id>/matches/<int:matchup_id>/start", methods=["POST"])
@login_required
def start_match(league_id, matchup_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    pm = db.session.get(PlayerMatchup, matchup_id)
    if not pm:
        return jsonify({"error": "Matchup not found"}), 404

    # Verify matchup belongs to this league
    wm = pm.week_matchup
    week = wm.week if wm else None
    if not week or week.league_id != league.id:
        return jsonify({"error": "Matchup not found"}), 404
    if week.status != WeekStatus.PUBLISHED.value:
        return jsonify({"error": "Week is not published yet"}), 400

    effective = get_effective_user()
    if effective.id == pm.player1_id:
        pm.player1_started = True
    elif effective.id == pm.player2_id:
        pm.player2_started = True
    else:
        # Allow admin to start for either player
        if _is_league_admin(league, effective):
            data = request.get_json(silent=True) or {}
            player_id = data.get("player_id")
            if player_id == pm.player1_id:
                pm.player1_started = True
            elif player_id == pm.player2_id:
                pm.player2_started = True
            else:
                return jsonify({"error": "Specify player_id for admin start"}), 400
        else:
            return jsonify({"error": "You are not in this matchup"}), 403

    db.session.commit()
    return jsonify(serialize_player_matchup(pm))


@blueprint.route("/<int:league_id>/matches/<int:matchup_id>", methods=["GET"])
def get_match(league_id, matchup_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    pm = db.session.get(PlayerMatchup, matchup_id)
    if not pm:
        return jsonify({"error": "Matchup not found"}), 404
    wm = pm.week_matchup
    week = wm.week if wm else None
    if not week or week.league_id != league.id:
        return jsonify({"error": "Matchup not found"}), 404

    viewer = get_effective_user() if current_user.is_authenticated else None
    return jsonify(serialize_player_matchup(pm, viewer=viewer))


# --- Game reporting ---

@blueprint.route("/<int:league_id>/matches/<int:matchup_id>/games", methods=["POST"])
@login_required
def report_game(league_id, matchup_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    pm = db.session.get(PlayerMatchup, matchup_id)
    if not pm:
        return jsonify({"error": "Matchup not found"}), 404
    wm = pm.week_matchup
    week = wm.week if wm else None
    if not week or week.league_id != league.id:
        return jsonify({"error": "Matchup not found"}), 404
    if week.status != WeekStatus.PUBLISHED.value:
        return jsonify({"error": "Week is not published"}), 400

    # Both players must have started
    if not pm.player1_started or not pm.player2_started:
        return jsonify({"error": "Both players must start before reporting games"}), 400

    effective = get_effective_user()
    is_admin = _is_league_admin(league, effective)
    is_participant = effective.id in (pm.player1_id, pm.player2_id)
    if not is_admin and not is_participant:
        return jsonify({"error": "You are not in this matchup"}), 403

    data = request.get_json(silent=True) or {}
    game_number = data.get("game_number")
    winner_id = data.get("winner_id")

    if not isinstance(game_number, int) or game_number < 1:
        return jsonify({"error": "game_number must be a positive integer"}), 400
    if winner_id not in (pm.player1_id, pm.player2_id):
        return jsonify({"error": "winner_id must be one of the players"}), 400

    # Check game_number is sequential
    existing_games = sorted(pm.games, key=lambda g: g.game_number)
    expected_next = len(existing_games) + 1
    if game_number != expected_next:
        return jsonify({"error": f"Expected game_number {expected_next}"}), 400

    # Check match not already decided
    wins_needed = math.ceil(week.best_of_n / 2)
    p1_wins = sum(1 for g in existing_games if g.winner_id == pm.player1_id)
    p2_wins = sum(1 for g in existing_games if g.winner_id == pm.player2_id)
    if p1_wins >= wins_needed or p2_wins >= wins_needed:
        return jsonify({"error": "Match is already decided"}), 400

    p1_keys = data.get("player1_keys", 0)
    p2_keys = data.get("player2_keys", 0)
    if not isinstance(p1_keys, int) or p1_keys < 0 or p1_keys > 3:
        return jsonify({"error": "player1_keys must be 0-3"}), 400
    if not isinstance(p2_keys, int) or p2_keys < 0 or p2_keys > 3:
        return jsonify({"error": "player2_keys must be 0-3"}), 400

    game = MatchGame(
        player_matchup_id=pm.id,
        game_number=game_number,
        winner_id=winner_id,
        player1_keys=p1_keys,
        player2_keys=p2_keys,
        went_to_time=bool(data.get("went_to_time", False)),
        loser_conceded=bool(data.get("loser_conceded", False)),
        player1_deck_id=data.get("player1_deck_id"),
        player2_deck_id=data.get("player2_deck_id"),
        reported_by_id=effective.id,
    )
    db.session.add(game)
    db.session.flush()

    # Check if match is now complete - auto-complete week if all matches done
    all_games = sorted(pm.games + [game], key=lambda g: g.game_number)
    p1_total = sum(1 for g in all_games if g.winner_id == pm.player1_id)
    p2_total = sum(1 for g in all_games if g.winner_id == pm.player2_id)

    # Check if entire week is complete
    if p1_total >= wins_needed or p2_total >= wins_needed:
        _check_week_completion(week)

    db.session.commit()
    return jsonify(serialize_match_game(game)), 201


def _check_week_completion(week):
    """Check if all matches in a week are complete, and if so mark week as COMPLETED."""
    wins_needed = math.ceil(week.best_of_n / 2)
    for wm in week.matchups:
        for pm in wm.player_matchups:
            games = sorted(pm.games, key=lambda g: g.game_number)
            p1_wins = sum(1 for g in games if g.winner_id == pm.player1_id)
            p2_wins = sum(1 for g in games if g.winner_id == pm.player2_id)
            if p1_wins < wins_needed and p2_wins < wins_needed:
                return  # Not all matches complete
    week.status = WeekStatus.COMPLETED.value
