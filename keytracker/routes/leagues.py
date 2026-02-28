from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from keytracker.schema import (
    db,
    Deck,
    EXPANSION_VALUES,
    KeyforgeSet,
    League,
    LeagueAdmin,
    LeagueAdminLog,
    LeagueSignup,
    LeagueStatus,
    LeagueWeek,
    WeekMatchup,
    PlayerMatchup,
    PlayerDeckSelection,
    MatchGame,
    StrikeSelection,
    SealedPoolDeck,
    AlliancePodSelection,
    ThiefCurationDeck,
    ThiefSteal,
    FeatureDesignation,
    PodStats,
    SignupStatus,
    WeekFormat,
    WeekStatus,
    Team,
    TeamMember,
    DraftPick,
    User,
    TOKEN_EXPANSION_IDS,
    PROPHECY_EXPANSION_ID,
)
from keytracker.serializers import (
    serialize_league_summary,
    serialize_league_detail,
    serialize_league_week,
    serialize_week_matchup,
    serialize_player_matchup,
    serialize_deck_selection,
    serialize_deck_summary,
    serialize_deck_brief,
    serialize_sealed_pool_entry,
    serialize_alliance_selection,
    serialize_match_game,
    serialize_team_detail,
    serialize_user_brief,
    serialize_admin_log_entry,
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
    return (
        LeagueAdmin.query.filter_by(league_id=league.id, user_id=user.id).first()
        is not None
    )


def _get_league_or_404(league_id):
    league = db.session.get(League, league_id)
    if league is None:
        return None, (jsonify({"error": "League not found"}), 404)
    return league, None


def _log_admin_action(league_id, week_id, user_id, action_type, details=None):
    """Record an admin action in the league admin log."""
    import datetime

    entry = LeagueAdminLog(
        league_id=league_id,
        week_id=week_id,
        user_id=user_id,
        action_type=action_type,
        details=details,
        created_at=datetime.datetime.utcnow(),
    )
    db.session.add(entry)


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
    effective = get_effective_user()
    viewer = effective if current_user.is_authenticated else None
    data = serialize_league_detail(league, viewer=viewer)
    if current_user.is_authenticated:
        data["is_admin"] = _is_league_admin(league, effective)
        signup = LeagueSignup.query.filter_by(
            league_id=league.id, user_id=effective.id
        ).first()
        data["is_signed_up"] = signup is not None
        # Find user's team membership
        member = (
            TeamMember.query.join(Team)
            .filter(
                Team.league_id == league.id,
                TeamMember.user_id == effective.id,
            )
            .first()
        )
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
    data = request.get_json(silent=True) or {}
    # week_bonus_points can be edited at any status
    if "week_bonus_points" in data:
        if (
            isinstance(data["week_bonus_points"], int)
            and data["week_bonus_points"] >= 0
        ):
            league.week_bonus_points = data["week_bonus_points"]
    if league.status != LeagueStatus.SETUP.value:
        db.session.commit()
        db.session.refresh(league)
        return jsonify(serialize_league_detail(league))
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


@blueprint.route("/<int:league_id>", methods=["DELETE"])
@login_required
def delete_league(league_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league, get_effective_user()):
        return jsonify({"error": "Admin access required"}), 403
    if not league.is_test:
        return jsonify({"error": "Only test leagues can be deleted"}), 400

    # Cascade delete all related data
    for week in LeagueWeek.query.filter_by(league_id=league.id).all():
        for matchup in WeekMatchup.query.filter_by(week_id=week.id).all():
            for pm in PlayerMatchup.query.filter_by(week_matchup_id=matchup.id).all():
                MatchGame.query.filter_by(player_matchup_id=pm.id).delete()
                StrikeSelection.query.filter_by(player_matchup_id=pm.id).delete()
                db.session.delete(pm)
            db.session.delete(matchup)
        PlayerDeckSelection.query.filter_by(week_id=week.id).delete()
        SealedPoolDeck.query.filter_by(week_id=week.id).delete()
        AlliancePodSelection.query.filter_by(week_id=week.id).delete()
        FeatureDesignation.query.filter_by(week_id=week.id).delete()
        for cd in ThiefCurationDeck.query.filter_by(week_id=week.id).all():
            ThiefSteal.query.filter_by(curation_deck_id=cd.id).delete()
        ThiefCurationDeck.query.filter_by(week_id=week.id).delete()
        db.session.delete(week)
    for team in Team.query.filter_by(league_id=league.id).all():
        TeamMember.query.filter_by(team_id=team.id).delete()
        DraftPick.query.filter_by(team_id=team.id).delete()
        db.session.delete(team)
    LeagueSignup.query.filter_by(league_id=league.id).delete()
    LeagueAdmin.query.filter_by(league_id=league.id).delete()
    db.session.delete(league)
    db.session.commit()
    return jsonify({"success": True}), 200


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
    if not effective.dok_profile_url or not effective.country or not effective.timezone:
        return (
            jsonify(
                {
                    "error": "You must set your DoK profile URL, country, and timezone in your account settings before signing up for a league."
                }
            ),
            400,
        )
    existing = LeagueSignup.query.filter_by(
        league_id=league.id, user_id=effective.id
    ).first()
    if existing:
        return jsonify({"error": "Already signed up"}), 409
    max_order = (
        db.session.query(db.func.max(LeagueSignup.signup_order))
        .filter_by(league_id=league.id)
        .scalar()
        or 0
    )
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
    is_captain = (
        TeamMember.query.filter_by(
            team_id=team.id, user_id=effective.id, is_captain=True
        ).first()
        is not None
    )
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
        return (
            jsonify({"error": "User must be signed up to be assigned as captain"}),
            400,
        )
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
        member = TeamMember(team_id=team.id, user_id=user_id, is_captain=True)
        db.session.add(member)
    db.session.commit()
    db.session.refresh(team)
    return jsonify(serialize_team_detail(team))


# --- Member reassignment ---


@blueprint.route(
    "/<int:league_id>/teams/<int:team_id>/members/<int:member_user_id>", methods=["PUT"]
)
@login_required
def reassign_member(league_id, team_id, member_user_id):
    """Replace a team member with a different signed-up user."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league, get_effective_user()):
        return jsonify({"error": "Admin access required"}), 403
    team = db.session.get(Team, team_id)
    if not team or team.league_id != league.id:
        return jsonify({"error": "Team not found"}), 404
    data = request.get_json(silent=True) or {}
    new_user_id = data.get("new_user_id")
    if not new_user_id:
        return jsonify({"error": "new_user_id is required"}), 400

    # Find the existing member
    member = TeamMember.query.filter_by(team_id=team.id, user_id=member_user_id).first()
    if not member:
        return jsonify({"error": "Member not found on this team"}), 404

    # Verify new user is signed up
    new_signup = LeagueSignup.query.filter_by(
        league_id=league.id, user_id=new_user_id
    ).first()
    if not new_signup:
        return jsonify({"error": "New user must be signed up for the league"}), 400

    # Verify new user isn't already on a team
    existing = TeamMember.query.filter(
        TeamMember.user_id == new_user_id,
        TeamMember.team_id.in_([t.id for t in league.teams]),
    ).first()
    if existing:
        return jsonify({"error": "New user is already on a team"}), 400

    was_captain = member.is_captain
    member.user_id = new_user_id
    member.is_captain = was_captain

    # Transfer deck selections from old user to new user
    week_ids = [w.id for w in league.weeks]
    if week_ids:
        PlayerDeckSelection.query.filter(
            PlayerDeckSelection.week_id.in_(week_ids),
            PlayerDeckSelection.user_id == member_user_id,
        ).update({PlayerDeckSelection.user_id: new_user_id}, synchronize_session=False)

    db.session.commit()
    db.session.refresh(team)
    return jsonify(serialize_team_detail(team))


# --- Fee tracking ---


@blueprint.route(
    "/<int:league_id>/teams/<int:team_id>/fees/<int:user_id>", methods=["POST"]
)
@login_required
def toggle_fee_paid(league_id, team_id, user_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    team = db.session.get(Team, team_id)
    if not team or team.league_id != league.id:
        return jsonify({"error": "Team not found"}), 404
    effective = get_effective_user()
    is_captain = (
        TeamMember.query.filter_by(
            team_id=team.id, user_id=effective.id, is_captain=True
        ).first()
        is not None
    )
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
    existing = LeagueAdmin.query.filter_by(league_id=league.id, user_id=user_id).first()
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
    admin = LeagueAdmin.query.filter_by(league_id=league.id, user_id=user_id).first()
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
        pick_history.append(
            {
                "round_number": p.round_number,
                "pick_number": p.pick_number,
                "team_id": p.team_id,
                "team_name": p.team.name if p.team else None,
                "picked_user": (
                    serialize_user_brief(p.picked_user) if p.picked_user else None
                ),
                "picked_at": p.picked_at.isoformat() if p.picked_at else None,
            }
        )
        picked_user_ids.add(p.picked_user_id)

    # Available players: signed_up status, not yet picked, not a captain
    captain_user_ids = set()
    for team in teams:
        for m in team.members:
            if m.is_captain:
                captain_user_ids.add(m.user_id)

    available = []
    for s in league.signups:
        if (
            s.status == SignupStatus.DRAFTED.value
            and s.user_id not in picked_user_ids
            and s.user_id not in captain_user_ids
        ):
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
                (
                    p
                    for p in pick_history
                    if p["round_number"] == r and p["team_id"] == t.id
                ),
                None,
            )
            round_picks.append(
                {
                    "team_id": t.id,
                    "team_name": t.name,
                    "pick": pick,
                }
            )
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
    is_captain = (
        TeamMember.query.join(Team)
        .filter(
            Team.league_id == league.id,
            TeamMember.user_id == effective.id,
            TeamMember.is_captain == True,
        )
        .first()
        is not None
    )
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
    is_current_captain = (
        TeamMember.query.filter_by(
            team_id=current_team_data["id"],
            user_id=effective.id,
            is_captain=True,
        ).first()
        is not None
    )
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
    if sets:
        return jsonify(
            [
                {"number": s.number, "name": s.name, "shortname": s.shortname}
                for s in sets
            ]
        )
    # Fallback to hardcoded EXPANSION_VALUES
    return jsonify(
        [
            {"number": ev.number, "name": ev.name, "shortname": ev.shortname}
            for ev in EXPANSION_VALUES
        ]
    )


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
    rounds = [[(a, b) for a, b in r if a is not None and b is not None] for r in rounds]
    return rounds


def _compute_player_strength(user_id, league_id):
    """Compute player strength for pairing purposes.

    Strength = match wins + sum(opponent_strength * 0.01)
    """
    # Find all completed player matchups for this user in this league
    completed_matchups = (
        PlayerMatchup.query.join(WeekMatchup)
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
            PlayerMatchup.query.join(WeekMatchup)
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


def _is_stolen_deck(week_id, stealing_team_id, deck_id):
    """Check if a deck was stolen by the given team."""
    return (
        ThiefSteal.query.join(ThiefCurationDeck)
        .filter(
            ThiefSteal.week_id == week_id,
            ThiefSteal.stealing_team_id == stealing_team_id,
            ThiefCurationDeck.deck_id == deck_id,
        )
        .first()
        is not None
    )


def _generate_thief_player_pairings(team1, team2, week_matchup, league, week):
    """Generate player pairings for Thief format.

    Stolen-deck players face non-stolen-deck players.
    Returns list of (player1_id, player2_id, is_feature) tuples.
    """
    members1 = list(team1.members)
    members2 = list(team2.members)

    def get_deck_id(user_id):
        sel = PlayerDeckSelection.query.filter_by(
            week_id=week.id, user_id=user_id
        ).first()
        return sel.deck_id if sel else None

    def is_stolen_player(team, user_id):
        deck_id = get_deck_id(user_id)
        if not deck_id:
            return False
        return _is_stolen_deck(week.id, team.id, deck_id)

    team1_stolen = [m for m in members1 if is_stolen_player(team1, m.user_id)]
    team1_not_stolen = [m for m in members1 if not is_stolen_player(team1, m.user_id)]
    team2_stolen = [m for m in members2 if is_stolen_player(team2, m.user_id)]
    team2_not_stolen = [m for m in members2 if not is_stolen_player(team2, m.user_id)]

    random.shuffle(team1_stolen)
    random.shuffle(team1_not_stolen)
    random.shuffle(team2_stolen)
    random.shuffle(team2_not_stolen)

    pairings = []
    is_feature = False

    # team1_stolen vs team2_not_stolen; team1_not_stolen vs team2_stolen
    stolen_pairs = list(zip(team1_stolen, team2_not_stolen))
    not_stolen_pairs = list(zip(team1_not_stolen, team2_stolen))

    # Determine feature pair based on thief_stolen_team_id
    feature_pair = None
    if league.team_size % 2 == 0 and week_matchup.thief_stolen_team_id:
        if week_matchup.thief_stolen_team_id == team1.id and stolen_pairs:
            # Feature: team1 stolen player vs team2 not-stolen player
            feature_pair = stolen_pairs[0]
            stolen_pairs = stolen_pairs[1:]
        elif week_matchup.thief_stolen_team_id == team2.id and not_stolen_pairs:
            # Feature: team1 not-stolen player vs team2 stolen player
            feature_pair = not_stolen_pairs[0]
            not_stolen_pairs = not_stolen_pairs[1:]

    if feature_pair:
        pairings.append((feature_pair[0].user_id, feature_pair[1].user_id, True))

    for m1, m2 in stolen_pairs:
        pairings.append((m1.user_id, m2.user_id, False))
    for m1, m2 in not_stolen_pairs:
        pairings.append((m1.user_id, m2.user_id, False))

    return pairings


def _generate_player_pairings(team1, team2, league, week, week_number):
    """Generate player pairings within a team matchup.

    Week 1: random. Week 2+: strength-based.
    Returns list of (player1_id, player2_id, is_feature) tuples.
    Feature pair (if any) is always first.
    """
    members1 = list(team1.members)
    members2 = list(team2.members)

    feature_pair = None
    if league.team_size % 2 == 0:
        fd1 = FeatureDesignation.query.filter_by(
            week_id=week.id, team_id=team1.id
        ).first()
        fd2 = FeatureDesignation.query.filter_by(
            week_id=week.id, team_id=team2.id
        ).first()
        if fd1 and fd2:
            feature_pair = (fd1.user_id, fd2.user_id)
            members1 = [m for m in members1 if m.user_id != fd1.user_id]
            members2 = [m for m in members2 if m.user_id != fd2.user_id]

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
    if feature_pair:
        pairings.append((feature_pair[0], feature_pair[1], True))
    for i in range(min(len(members1), len(members2))):
        pairings.append((members1[i].user_id, members2[i].user_id, False))
    return pairings


def _parse_deck_url(url_str):
    """Extract kf_id from a deck URL or raw ID."""
    url_str = url_str.strip()
    # Try keyforgegame.com/deck-details/{id}
    m = re.search(r"keyforgegame\.com/deck-details/([a-f0-9-]+)", url_str)
    if m:
        return m.group(1)
    # Try decksofkeyforge.com/decks/{id}
    m = re.search(r"decksofkeyforge\.com/decks/([a-f0-9-]+)", url_str)
    if m:
        return m.group(1)
    # Try raw UUID
    m = re.match(
        r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", url_str
    )
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
    if league.status not in (LeagueStatus.ACTIVE.value, LeagueStatus.PLAYOFFS.value):
        return jsonify({"error": "League must be active"}), 400

    data = request.get_json(silent=True) or {}
    format_type = data.get("format_type", "")
    valid_formats = [f.value for f in WeekFormat]
    if format_type not in valid_formats:
        return jsonify({"error": f"format_type must be one of: {valid_formats}"}), 400

    best_of_n = data.get("best_of_n", 1)
    if not isinstance(best_of_n, int) or best_of_n < 1 or best_of_n % 2 == 0:
        return jsonify({"error": "best_of_n must be a positive odd integer"}), 400

    if format_type == "triad":
        best_of_n = 3

    # Determine next week number
    max_week = (
        db.session.query(db.func.max(LeagueWeek.week_number))
        .filter_by(league_id=league.id)
        .scalar()
        or 0
    )

    allowed_sets = data.get("allowed_sets")
    allowed_sets_json = None
    if allowed_sets and isinstance(allowed_sets, list):
        allowed_sets_json = json.dumps(allowed_sets)

    week_name = (data.get("name") or "").strip() or None

    week = LeagueWeek(
        league_id=league.id,
        week_number=max_week + 1,
        name=week_name,
        format_type=format_type,
        status=WeekStatus.SETUP.value,
        best_of_n=best_of_n,
        allowed_sets=allowed_sets_json,
        max_sas=data.get("max_sas"),
        combined_max_sas=data.get("combined_max_sas"),
        set_diversity=data.get("set_diversity"),
        house_diversity=data.get("house_diversity"),
        decks_per_player=data.get("decks_per_player"),
        no_keycheat=bool(data.get("no_keycheat", False)),
    )
    db.session.add(week)
    db.session.commit()
    db.session.refresh(week)
    return jsonify(serialize_league_week(week)), 201


@blueprint.route("/<int:league_id>/weeks/<int:week_id>", methods=["DELETE"])
@login_required
def delete_week(league_id, week_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league, get_effective_user()):
        return jsonify({"error": "Admin access required"}), 403
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.status != WeekStatus.SETUP.value:
        return jsonify({"error": "Can only delete weeks in setup status"}), 400

    for matchup in WeekMatchup.query.filter_by(week_id=week.id).all():
        for pm in PlayerMatchup.query.filter_by(week_matchup_id=matchup.id).all():
            MatchGame.query.filter_by(player_matchup_id=pm.id).delete()
            StrikeSelection.query.filter_by(player_matchup_id=pm.id).delete()
            db.session.delete(pm)
        db.session.delete(matchup)
    PlayerDeckSelection.query.filter_by(week_id=week.id).delete()
    SealedPoolDeck.query.filter_by(week_id=week.id).delete()
    AlliancePodSelection.query.filter_by(week_id=week.id).delete()
    FeatureDesignation.query.filter_by(week_id=week.id).delete()
    # Delete thief data
    for cd in ThiefCurationDeck.query.filter_by(week_id=week.id).all():
        ThiefSteal.query.filter_by(curation_deck_id=cd.id).delete()
    ThiefCurationDeck.query.filter_by(week_id=week.id).delete()
    db.session.delete(week)
    db.session.commit()
    return jsonify({"success": True}), 200


@blueprint.route("/<int:league_id>/weeks", methods=["GET"])
def list_weeks(league_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    weeks = (
        LeagueWeek.query.filter_by(league_id=league.id)
        .order_by(LeagueWeek.week_number)
        .all()
    )
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

    data = request.get_json(silent=True) or {}
    if "name" in data:
        week.name = (data["name"] or "").strip() or None

    # format_type is only changeable while in setup
    if week.status == WeekStatus.SETUP.value and "format_type" in data:
        valid_formats = [f.value for f in WeekFormat]
        if data["format_type"] in valid_formats:
            week.format_type = data["format_type"]

    # All other settings are editable at any status
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
    if "no_keycheat" in data:
        week.no_keycheat = bool(data["no_keycheat"])

    db.session.commit()
    db.session.refresh(week)
    return jsonify(serialize_league_week(week))


# --- Week status transitions ---


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/open-deck-selection", methods=["POST"]
)
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

    # Thief format starts at curation, not deck_selection
    if week.format_type == WeekFormat.THIEF.value:
        week.status = WeekStatus.CURATION.value
    else:
        week.status = WeekStatus.DECK_SELECTION.value
    _log_admin_action(
        league.id,
        week.id,
        get_effective_user().id,
        "week_status_changed",
        f"status -> {week.status}",
    )
    db.session.commit()
    return jsonify(serialize_league_week(week))


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/generate-matchups", methods=["POST"]
)
@login_required
def generate_matchups(league_id, week_id):
    """Legacy endpoint: generates both team pairings and player matchups in one step."""
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
    active_members = _get_active_players(league)
    for member in active_members:
        if week.format_type == WeekFormat.SEALED_ALLIANCE.value:
            pod_count = AlliancePodSelection.query.filter_by(
                week_id=week.id, user_id=member.user_id, slot_type="pod"
            ).count()
            if pod_count < 3:
                user = db.session.get(User, member.user_id)
                name = user.name if user else f"User {member.user_id}"
                return (
                    jsonify(
                        {
                            "error": f"{name} has not forged their alliance ({pod_count}/3 pods)"
                        }
                    ),
                    400,
                )
        else:
            required_slots = 3 if week.format_type == WeekFormat.TRIAD.value else 1
            selections = PlayerDeckSelection.query.filter_by(
                week_id=week.id, user_id=member.user_id
            ).count()
            if selections < required_slots:
                user = db.session.get(User, member.user_id)
                name = user.name if user else f"User {member.user_id}"
                return (
                    jsonify(
                        {
                            "error": f"{name} has not submitted all deck selections ({selections}/{required_slots})"
                        }
                    ),
                    400,
                )

    # Delete existing matchups for this week (in case of re-generation)
    WeekMatchup.query.filter_by(week_id=week.id).delete()
    db.session.flush()

    # Generate round-robin team pairings
    teams = sorted(league.teams, key=lambda t: t.order_number)
    all_rounds = _generate_round_robin(teams)

    # Use the round corresponding to this week
    round_idx = week.week_number - 1
    if round_idx >= len(all_rounds):
        return (
            jsonify(
                {"error": "No more round-robin pairings available for this week number"}
            ),
            400,
        )

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
        player_pairs = _generate_player_pairings(
            team1, team2, league, week, week.week_number
        )
        for p1_id, p2_id, is_feature in player_pairs:
            pm = PlayerMatchup(
                week_matchup_id=wm.id,
                player1_id=p1_id,
                player2_id=p2_id,
                is_feature=is_feature,
            )
            db.session.add(pm)

    week.status = WeekStatus.PAIRING.value
    db.session.commit()
    db.session.refresh(week)
    return jsonify(serialize_league_week(week))


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/generate-team-pairings", methods=["POST"]
)
@login_required
def generate_team_pairings(league_id, week_id):
    """Generate team pairings only (no player matchups yet)."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league, get_effective_user()):
        return jsonify({"error": "Admin access required"}), 403
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    # Thief format runs team pairings from curation (before the thief phase)
    if week.format_type == WeekFormat.THIEF.value:
        if week.status != WeekStatus.CURATION.value:
            return jsonify({"error": "Week must be in curation status"}), 400
    elif week.status != WeekStatus.DECK_SELECTION.value:
        return jsonify({"error": "Week must be in deck_selection status"}), 400

    # Delete existing matchups
    WeekMatchup.query.filter_by(week_id=week.id).delete()
    db.session.flush()

    # Generate round-robin team pairings only
    teams = sorted(league.teams, key=lambda t: t.order_number)
    all_rounds = _generate_round_robin(teams)
    round_idx = week.week_number - 1
    if round_idx >= len(all_rounds):
        return (
            jsonify(
                {"error": "No more round-robin pairings available for this week number"}
            ),
            400,
        )

    for team1, team2 in all_rounds[round_idx]:
        # For Thief format, randomly assign which team must feature a stolen-deck player
        thief_stolen_team_id = None
        if week.format_type == WeekFormat.THIEF.value:
            thief_stolen_team_id = random.choice([team1.id, team2.id])
        wm = WeekMatchup(
            week_id=week.id,
            team1_id=team1.id,
            team2_id=team2.id,
            thief_stolen_team_id=thief_stolen_team_id,
        )
        db.session.add(wm)

    week.status = WeekStatus.TEAM_PAIRED.value
    _log_admin_action(
        league.id, week.id, get_effective_user().id, "team_pairings_generated"
    )
    db.session.commit()
    db.session.refresh(week)
    return jsonify(serialize_league_week(week))


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/generate-player-matchups", methods=["POST"]
)
@login_required
def generate_player_matchups(league_id, week_id):
    """Generate player matchups within existing team pairings."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league, get_effective_user()):
        return jsonify({"error": "Admin access required"}), 403
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    # Thief format runs player matchups from deck_selection (team pairings already exist)
    if week.format_type == WeekFormat.THIEF.value:
        if week.status != WeekStatus.DECK_SELECTION.value:
            return jsonify({"error": "Week must be in deck_selection status"}), 400
    elif week.status != WeekStatus.TEAM_PAIRED.value:
        return jsonify({"error": "Week must be in team_paired status"}), 400

    # Check all players have submitted deck selections (warn but allow force)
    data = request.get_json(silent=True) or {}
    if not data.get("force"):
        active_members = _get_active_players(league)
        missing = []
        if week.format_type == WeekFormat.SEALED_ALLIANCE.value:
            for member in active_members:
                pod_count = AlliancePodSelection.query.filter_by(
                    week_id=week.id, user_id=member.user_id, slot_type="pod"
                ).count()
                if pod_count < 3:
                    u = db.session.get(User, member.user_id)
                    name = u.name if u else f"User {member.user_id}"
                    missing.append(f"{name} ({pod_count}/3 pods)")
        else:
            required_slots = 3 if week.format_type == WeekFormat.TRIAD.value else 1
            for member in active_members:
                selections = PlayerDeckSelection.query.filter_by(
                    week_id=week.id, user_id=member.user_id
                ).count()
                if selections < required_slots:
                    u = db.session.get(User, member.user_id)
                    name = u.name if u else f"User {member.user_id}"
                    missing.append(f"{name} ({selections}/{required_slots})")
        if missing:
            return (
                jsonify(
                    {
                        "error": f"Some players have not submitted all deck selections: {', '.join(missing)}",
                        "incomplete_decks": True,
                        "missing": missing,
                    }
                ),
                400,
            )

    if week.week_number > 1:
        prev_week = LeagueWeek.query.filter_by(
            league_id=league.id, week_number=week.week_number - 1
        ).first()
        if prev_week and prev_week.status != WeekStatus.COMPLETED.value:
            return (
                jsonify(
                    {
                        "error": "Previous week must be completed before generating player matchups"
                    }
                ),
                400,
            )

    matchups = WeekMatchup.query.filter_by(week_id=week.id).all()
    if not matchups:
        return jsonify({"error": "No team pairings found"}), 400

    # Pre-flight check: for even team_size leagues, all teams must have a feature designation
    # (Skip for Thief format - feature is auto-constrained by thief_stolen_team_id)
    if league.team_size % 2 == 0 and week.format_type != WeekFormat.THIEF.value:
        missing_teams = []
        seen_team_ids = set()
        for wm in matchups:
            for team_id in [wm.team1_id, wm.team2_id]:
                if team_id in seen_team_ids:
                    continue
                seen_team_ids.add(team_id)
                fd = FeatureDesignation.query.filter_by(
                    week_id=week.id, team_id=team_id
                ).first()
                if not fd:
                    missing_teams.append(team_id)
        if missing_teams:
            return (
                jsonify(
                    {
                        "error": "missing_feature_designations",
                        "missing_teams": missing_teams,
                    }
                ),
                400,
            )

    # Pre-flight: verify no selected deck has been used in a prior week
    SEALED_FORMATS = (WeekFormat.SEALED_ARCHON.value, WeekFormat.SEALED_ALLIANCE.value)
    if week.format_type not in SEALED_FORMATS:
        pairing_conflicts = (
            db.session.query(PlayerDeckSelection, LeagueWeek, User, Deck)
            .join(LeagueWeek, PlayerDeckSelection.week_id == LeagueWeek.id)
            .join(User, PlayerDeckSelection.user_id == User.id)
            .join(Deck, PlayerDeckSelection.deck_id == Deck.id)
            .filter(PlayerDeckSelection.week_id == week.id)  # selections for THIS week
            .all()
        )
        # For each selection in this week, check if the deck appears in an earlier week
        conflict_messages = []
        for sel, _, submitter, sel_deck in pairing_conflicts:
            prior = (
                db.session.query(PlayerDeckSelection, LeagueWeek, User)
                .join(LeagueWeek, PlayerDeckSelection.week_id == LeagueWeek.id)
                .join(User, PlayerDeckSelection.user_id == User.id)
                .filter(
                    PlayerDeckSelection.deck_id == sel_deck.id,
                    LeagueWeek.league_id == league.id,
                    LeagueWeek.id != week.id,
                    LeagueWeek.week_number < week.week_number,
                    ~LeagueWeek.format_type.in_(SEALED_FORMATS),
                )
                .first()
            )
            if prior:
                prior_sel, prior_week, prior_user = prior
                conflict_messages.append(
                    f"{submitter.name}'s deck ({sel_deck.name}) for this week "
                    f"was already used in {prior_week.name} (Week {prior_week.week_number}) "
                    f"by {prior_user.name}."
                )
        if conflict_messages:
            return (
                jsonify(
                    {
                        "error": "Deck conflicts detected: "
                        + " ".join(conflict_messages),
                        "deck_conflicts": True,
                    }
                ),
                409,
            )

    # Clear any existing player matchups
    for wm in matchups:
        PlayerMatchup.query.filter_by(week_matchup_id=wm.id).delete()

    db.session.flush()

    for wm in matchups:
        team1 = db.session.get(Team, wm.team1_id)
        team2 = db.session.get(Team, wm.team2_id)

        if week.format_type == WeekFormat.THIEF.value:
            player_pairs = _generate_thief_player_pairings(
                team1, team2, wm, league, week
            )
        else:
            player_pairs = _generate_player_pairings(
                team1, team2, league, week, week.week_number
            )
        for p1_id, p2_id, is_feature in player_pairs:
            pm = PlayerMatchup(
                week_matchup_id=wm.id,
                player1_id=p1_id,
                player2_id=p2_id,
                is_feature=is_feature,
            )
            db.session.add(pm)

    week.status = WeekStatus.PAIRING.value
    _log_admin_action(
        league.id, week.id, get_effective_user().id, "player_matchups_generated"
    )
    db.session.commit()
    db.session.refresh(week)
    return jsonify(serialize_league_week(week))


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/matchups/<int:matchup_id>", methods=["PUT"]
)
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

    wm = pm.week_matchup
    team1_member_ids = {m.user_id for m in wm.team1.members}
    team2_member_ids = {m.user_id for m in wm.team2.members}

    data = request.get_json(silent=True) or {}
    if "player1_id" in data:
        new_p1 = data["player1_id"]
        if new_p1 not in team1_member_ids:
            return jsonify({"error": "player1_id must be a member of team1"}), 400
        pm.player1_id = new_p1
    if "player2_id" in data:
        new_p2 = data["player2_id"]
        if new_p2 not in team2_member_ids:
            return jsonify({"error": "player2_id must be a member of team2"}), 400
        pm.player2_id = new_p2

    _log_admin_action(
        league.id,
        week.id,
        get_effective_user().id,
        "player_matchup_edited",
        f"matchup_id={matchup_id}",
    )
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
    active_members = _get_active_players(league)
    for member in active_members:
        if week.format_type == WeekFormat.SEALED_ALLIANCE.value:
            pod_count = AlliancePodSelection.query.filter_by(
                week_id=week.id, user_id=member.user_id, slot_type="pod"
            ).count()
            if pod_count < 3:
                user = db.session.get(User, member.user_id)
                name = user.name if user else f"User {member.user_id}"
                return (
                    jsonify({"error": f"{name} has not forged their alliance"}),
                    400,
                )
        else:
            required_slots = 3 if week.format_type == WeekFormat.TRIAD.value else 1
            selections = PlayerDeckSelection.query.filter_by(
                week_id=week.id, user_id=member.user_id
            ).count()
            if selections < required_slots:
                user = db.session.get(User, member.user_id)
                name = user.name if user else f"User {member.user_id}"
                return (
                    jsonify({"error": f"{name} has not submitted all deck selections"}),
                    400,
                )

    week.status = WeekStatus.PUBLISHED.value
    _log_admin_action(league.id, week.id, get_effective_user().id, "week_published")
    db.session.commit()
    return jsonify(serialize_league_week(week))


# --- Sealed pool generation ---


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/generate-sealed-pools", methods=["POST"]
)
@login_required
def generate_sealed_pools(league_id, week_id):
    from sqlalchemy.sql.expression import func

    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league, get_effective_user()):
        return jsonify({"error": "Admin access required"}), 403
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.format_type not in (
        WeekFormat.SEALED_ARCHON.value,
        WeekFormat.SEALED_ALLIANCE.value,
    ):
        return (
            jsonify(
                {
                    "error": "Sealed pools only for Sealed Archon or Sealed Alliance format"
                }
            ),
            400,
        )
    if week.sealed_pools_generated:
        return jsonify({"error": "Sealed pools already generated"}), 400

    decks_per_player = week.decks_per_player or 4
    active_members = _get_active_players(league)
    num_players = len(active_members)
    total_decks_needed = decks_per_player * num_players

    # Query random decks from allowed sets
    query = Deck.query
    if week.allowed_sets:
        try:
            allowed = json.loads(week.allowed_sets)
            query = query.filter(Deck.expansion.in_(allowed))
        except (json.JSONDecodeError, TypeError):
            pass

    decks = query.order_by(func.rand()).limit(total_decks_needed).all()
    if len(decks) < total_decks_needed:
        return (
            jsonify(
                {
                    "error": f"Not enough decks in database ({len(decks)} available, {total_decks_needed} needed)"
                }
            ),
            400,
        )

    # Assign decks to players
    random.shuffle(decks)
    for i, member in enumerate(active_members):
        player_decks = decks[i * decks_per_player : (i + 1) * decks_per_player]
        for d in player_decks:
            spd = SealedPoolDeck(
                week_id=week.id,
                user_id=member.user_id,
                deck_id=d.id,
            )
            db.session.add(spd)

    week.sealed_pools_generated = True
    _log_admin_action(
        league.id, week.id, get_effective_user().id, "sealed_pools_generated"
    )
    db.session.commit()
    return jsonify(serialize_league_week(week))


@blueprint.route("/<int:league_id>/weeks/<int:week_id>/sealed-pool", methods=["GET"])
@login_required
def get_sealed_pool(league_id, week_id):
    """Get the sealed pool for a user (defaults to current user)."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404

    effective = get_effective_user()
    target_user_id = request.args.get("user_id", type=int) or effective.id

    if target_user_id != effective.id:
        is_admin = _is_league_admin(league, effective)
        is_captain_of_team = False
        for team in league.teams:
            team_user_ids = {m.user_id for m in team.members}
            if target_user_id in team_user_ids:
                if any(
                    m.user_id == effective.id and m.is_captain for m in team.members
                ):
                    is_captain_of_team = True
                break
        if not is_admin and not is_captain_of_team:
            return jsonify({"error": "Cannot view sealed pool for this user"}), 403

    pool = SealedPoolDeck.query.filter_by(week_id=week.id, user_id=target_user_id).all()
    return jsonify([serialize_sealed_pool_entry(spd) for spd in pool])


# --- Alliance pod selection (Sealed Alliance format) ---


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/alliance-selection", methods=["POST"]
)
@login_required
def submit_alliance_selection(league_id, week_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404

    if week.format_type != WeekFormat.SEALED_ALLIANCE.value:
        return jsonify({"error": "Only for Sealed Alliance format"}), 400
    if week.status not in (
        WeekStatus.DECK_SELECTION.value,
        WeekStatus.TEAM_PAIRED.value,
    ):
        return jsonify({"error": "Alliance selection is not open"}), 400

    effective = get_effective_user()
    data = request.get_json(silent=True) or {}
    target_user_id = data.get("user_id", effective.id)

    # If submitting for another user, must be admin or captain
    if target_user_id != effective.id:
        is_admin = _is_league_admin(league, effective)
        is_captain_of_team = False
        for team in league.teams:
            team_user_ids = {m.user_id for m in team.members}
            if target_user_id in team_user_ids:
                if any(
                    m.user_id == effective.id and m.is_captain for m in team.members
                ):
                    is_captain_of_team = True
                break
        if not is_admin and not is_captain_of_team:
            return (
                jsonify({"error": "Cannot submit alliance selection for this user"}),
                403,
            )

    # Verify target is a league member
    member = (
        TeamMember.query.join(Team)
        .filter(Team.league_id == league.id, TeamMember.user_id == target_user_id)
        .first()
    )
    if not member:
        return jsonify({"error": "User is not a member of this league"}), 400

    pods = data.get("pods", [])
    token_deck_id = data.get("token_deck_id")
    prophecy_deck_id = data.get("prophecy_deck_id")

    if not isinstance(pods, list) or len(pods) != 3:
        return jsonify({"error": "Exactly 3 pods are required"}), 400

    # Build player's sealed pool as set of deck_ids
    pool = SealedPoolDeck.query.filter_by(week_id=week.id, user_id=target_user_id).all()
    pool_deck_ids = {spd.deck_id for spd in pool}

    pod_deck_ids = []
    houses = []
    for i, pod in enumerate(pods):
        deck_id = pod.get("deck_id")
        house = pod.get("house", "")
        if not deck_id or not house:
            return jsonify({"error": f"Pod {i+1} requires deck_id and house"}), 400

        # Deck must be in pool
        if deck_id not in pool_deck_ids:
            return jsonify({"error": f"Pod {i+1}: deck not in your sealed pool"}), 400

        # House must be a valid house for this deck
        valid_house = (
            PodStats.query.filter_by(deck_id=deck_id)
            .filter(PodStats.house == house)
            .first()
        )
        if not valid_house:
            return (
                jsonify(
                    {"error": f"Pod {i+1}: {house} is not a house of the selected deck"}
                ),
                400,
            )

        pod_deck_ids.append(deck_id)
        houses.append(house)

    # 3 unique houses required
    if len(set(houses)) != 3:
        return jsonify({"error": "All 3 pods must have unique houses"}), 400

    # Parse allowed sets for token/prophecy requirements
    allowed_sets = set()
    if week.allowed_sets:
        try:
            allowed_sets = set(json.loads(week.allowed_sets))
        except (json.JSONDecodeError, TypeError):
            pass

    needs_token = bool(allowed_sets & TOKEN_EXPANSION_IDS)
    needs_prophecy = PROPHECY_EXPANSION_ID in allowed_sets

    if needs_token:
        if not token_deck_id:
            return (
                jsonify({"error": "token_deck_id is required for this week's sets"}),
                400,
            )
        if token_deck_id not in pod_deck_ids:
            return (
                jsonify({"error": "token_deck_id must be one of the 3 pod decks"}),
                400,
            )

    if needs_prophecy:
        if not prophecy_deck_id:
            return (
                jsonify(
                    {"error": "prophecy_deck_id is required for Prophetic Visions"}
                ),
                400,
            )
        if prophecy_deck_id not in pod_deck_ids:
            return (
                jsonify({"error": "prophecy_deck_id must be one of the 3 pod decks"}),
                400,
            )

    # Replace existing alliance selections
    AlliancePodSelection.query.filter_by(
        week_id=week.id, user_id=target_user_id
    ).delete()

    for i, pod in enumerate(pods):
        sel = AlliancePodSelection(
            week_id=week.id,
            user_id=target_user_id,
            deck_id=pod["deck_id"],
            house_name=pod["house"],
            slot_type="pod",
            slot_number=i + 1,
        )
        db.session.add(sel)

    if needs_token and token_deck_id:
        sel = AlliancePodSelection(
            week_id=week.id,
            user_id=target_user_id,
            deck_id=token_deck_id,
            house_name=None,
            slot_type="token",
            slot_number=1,
        )
        db.session.add(sel)

    if needs_prophecy and prophecy_deck_id:
        sel = AlliancePodSelection(
            week_id=week.id,
            user_id=target_user_id,
            deck_id=prophecy_deck_id,
            house_name=None,
            slot_type="prophecy",
            slot_number=1,
        )
        db.session.add(sel)

    db.session.commit()

    selections = AlliancePodSelection.query.filter_by(
        week_id=week.id, user_id=target_user_id
    ).all()
    return jsonify([serialize_alliance_selection(s) for s in selections])


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/alliance-selection", methods=["DELETE"]
)
@login_required
def clear_alliance_selection(league_id, week_id):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404

    if week.format_type != WeekFormat.SEALED_ALLIANCE.value:
        return jsonify({"error": "Only for Sealed Alliance format"}), 400

    effective = get_effective_user()
    target_user_id = request.args.get("user_id", type=int) or effective.id

    if target_user_id != effective.id:
        is_admin = _is_league_admin(league, effective)
        is_captain_of_team = False
        for team in league.teams:
            team_user_ids = {m.user_id for m in team.members}
            if target_user_id in team_user_ids:
                if any(
                    m.user_id == effective.id and m.is_captain for m in team.members
                ):
                    is_captain_of_team = True
                break
        if not is_admin and not is_captain_of_team:
            return (
                jsonify({"error": "Cannot clear alliance selection for this user"}),
                403,
            )

    AlliancePodSelection.query.filter_by(
        week_id=week.id, user_id=target_user_id
    ).delete()
    db.session.commit()
    return "", 204


# --- Deck selection ---


def _check_deck_cross_week_conflicts(league, week, deck, target_team):
    """
    Returns a list of human-readable conflict error strings, or an empty list if clean.

    Error 1: Deck was selected in any earlier non-sealed week (any team/user).
    Error 2: Deck is selected in any other non-sealed week by any member of target_team.
    """
    SEALED_FORMATS = (WeekFormat.SEALED_ARCHON.value, WeekFormat.SEALED_ALLIANCE.value)

    # Skip check entirely if the current week is sealed
    if week.format_type in SEALED_FORMATS:
        return []

    errors = []

    # --- Error 1: used by anyone in a previous (lower week_number) non-sealed week ---
    prior_conflicts = (
        db.session.query(PlayerDeckSelection, LeagueWeek, User)
        .join(LeagueWeek, PlayerDeckSelection.week_id == LeagueWeek.id)
        .join(User, PlayerDeckSelection.user_id == User.id)
        .filter(
            PlayerDeckSelection.deck_id == deck.id,
            LeagueWeek.league_id == league.id,
            LeagueWeek.id != week.id,
            LeagueWeek.week_number < week.week_number,
            ~LeagueWeek.format_type.in_(SEALED_FORMATS),
        )
        .all()
    )
    for sel, prior_week, user in prior_conflicts:
        errors.append(
            f"This deck ({deck.name}) was already used in "
            f"{prior_week.name} (Week {prior_week.week_number}) by {user.name}."
        )

    # --- Error 2: selected for any other week by a teammate ---
    if target_team:
        team_member_ids = [m.user_id for m in target_team.members]
        team_conflicts = (
            db.session.query(PlayerDeckSelection, LeagueWeek, User)
            .join(LeagueWeek, PlayerDeckSelection.week_id == LeagueWeek.id)
            .join(User, PlayerDeckSelection.user_id == User.id)
            .filter(
                PlayerDeckSelection.deck_id == deck.id,
                LeagueWeek.league_id == league.id,
                LeagueWeek.id != week.id,
                PlayerDeckSelection.user_id.in_(team_member_ids),
                ~LeagueWeek.format_type.in_(SEALED_FORMATS),
            )
            .all()
        )
        for sel, other_week, user in team_conflicts:
            errors.append(
                f"This deck ({deck.name}) is already selected for "
                f"{other_week.name} (Week {other_week.week_number}) by your teammate {user.name}."
            )

    return errors


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/deck-selection", methods=["POST"]
)
@login_required
def submit_deck_selection(league_id, week_id):
    from keytracker.utils import get_deck_by_id_with_zeal

    league, err = _get_league_or_404(league_id)
    if err:
        return err
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404

    if week.status not in (
        WeekStatus.DECK_SELECTION.value,
        WeekStatus.TEAM_PAIRED.value,
        WeekStatus.PAIRING.value,
    ):
        return jsonify({"error": "Deck selection is not open"}), 400

    # Sealed Alliance uses a different endpoint for pod selection
    if week.format_type == WeekFormat.SEALED_ALLIANCE.value:
        return (
            jsonify(
                {"error": "Sealed Alliance format uses /alliance-selection endpoint"}
            ),
            400,
        )

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
                if any(
                    m.user_id == effective.id and m.is_captain for m in team.members
                ):
                    is_captain_of_team = True
                break
        if not is_admin and not is_captain_of_team:
            return jsonify({"error": "Cannot submit deck selection for this user"}), 403

    # Verify target user is in the league
    member = (
        TeamMember.query.join(Team)
        .filter(
            Team.league_id == league.id,
            TeamMember.user_id == target_user_id,
        )
        .first()
    )
    if not member:
        return jsonify({"error": "User is not a member of this league"}), 400

    # Resolve the player's team for cross-week conflict checking
    target_team = db.session.get(Team, member.team_id)

    slot_number = data.get("slot_number", 1)
    max_slots = 3 if week.format_type == WeekFormat.TRIAD.value else 1
    if not isinstance(slot_number, int) or slot_number < 1 or slot_number > max_slots:
        return jsonify({"error": f"slot_number must be between 1 and {max_slots}"}), 400

    # Sealed Archon: select from pool by deck_id
    if week.format_type == WeekFormat.SEALED_ARCHON.value:
        deck_db_id = data.get("deck_id")
        if not deck_db_id:
            return jsonify({"error": "deck_id is required for Sealed Archon"}), 400
        # Verify deck is in player's sealed pool
        pool_entry = SealedPoolDeck.query.filter_by(
            week_id=week.id, user_id=target_user_id, deck_id=deck_db_id
        ).first()
        if not pool_entry:
            return jsonify({"error": "Deck is not in your sealed pool"}), 400
        deck = db.session.get(Deck, deck_db_id)
        if not deck:
            return jsonify({"error": "Deck not found"}), 400
    elif week.format_type == WeekFormat.THIEF.value:
        # Thief: select from team's thief pool by deck_id
        deck_db_id = data.get("deck_id")
        if not deck_db_id:
            return jsonify({"error": "deck_id is required for Thief format"}), 400
        # Find player's team
        player_team = None
        for team in league.teams:
            if any(m.user_id == target_user_id for m in team.members):
                player_team = team
                break
        if not player_team:
            return jsonify({"error": "User is not on a team"}), 400
        # Build thief pool
        stolen_by_team = {
            ts.curation_deck.deck_id
            for ts in ThiefSteal.query.filter_by(
                week_id=week.id, stealing_team_id=player_team.id
            ).all()
        }
        stolen_from_team = {
            ts.curation_deck.deck_id
            for ts in ThiefSteal.query.join(ThiefCurationDeck)
            .filter(
                ThiefSteal.week_id == week.id,
                ThiefCurationDeck.team_id == player_team.id,
            )
            .all()
        }
        own_left = {
            cd.deck_id
            for cd in ThiefCurationDeck.query.filter_by(
                week_id=week.id, team_id=player_team.id
            ).all()
        } - stolen_from_team
        valid_pool = stolen_by_team | own_left
        if deck_db_id not in valid_pool:
            return jsonify({"error": "Deck is not in your thief pool"}), 400
        # Enforce feature player deck-type constraint (even team size only)
        if league.team_size % 2 == 0:
            fd = FeatureDesignation.query.filter_by(
                week_id=week.id, team_id=player_team.id
            ).first()
            if fd and fd.user_id == target_user_id:
                wm_for_sel = WeekMatchup.query.filter(
                    WeekMatchup.week_id == week.id,
                    db.or_(
                        WeekMatchup.team1_id == player_team.id,
                        WeekMatchup.team2_id == player_team.id,
                    ),
                ).first()
                if wm_for_sel and wm_for_sel.thief_stolen_team_id:
                    if wm_for_sel.thief_stolen_team_id == player_team.id:
                        if deck_db_id not in stolen_by_team:
                            return (
                                jsonify(
                                    {
                                        "error": "Feature player on the thieving-favored team must use a stolen deck"
                                    }
                                ),
                                400,
                            )
                    else:
                        if deck_db_id not in own_left:
                            return (
                                jsonify(
                                    {
                                        "error": "Feature player on the non-thieving-favored team must use one of their own decks"
                                    }
                                ),
                                400,
                            )
        # Validate deck not already assigned to another player on this team
        other_selections = (
            PlayerDeckSelection.query.filter_by(week_id=week.id, deck_id=deck_db_id)
            .filter(PlayerDeckSelection.user_id != target_user_id)
            .all()
        )
        for other_sel in other_selections:
            if any(m.user_id == other_sel.user_id for m in player_team.members):
                return jsonify({"error": "Deck is already assigned to a teammate"}), 400
        deck = db.session.get(Deck, deck_db_id)
        if not deck:
            return jsonify({"error": "Deck not found"}), 400
    else:
        # Normal: parse deck URL
        deck_url = (data.get("deck_url") or "").strip()
        if not deck_url:
            return jsonify({"error": "deck_url is required"}), 400

        kf_id = _parse_deck_url(deck_url)
        if not kf_id:
            return jsonify({"error": "Could not parse deck ID from URL"}), 400

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
                kf_set = db.session.get(KeyforgeSet, deck.expansion)
                set_name = kf_set.name if kf_set else str(deck.expansion)
                return (
                    jsonify(
                        {"error": f"Decks from {set_name} are not allowed this week"}
                    ),
                    400,
                )
        except (json.JSONDecodeError, TypeError):
            pass

    # Validate max SAS
    if week.max_sas is not None:
        sas = deck.sas_rating
        if sas and sas > week.max_sas:
            return (
                jsonify(
                    {"error": f"Deck SAS ({sas}) exceeds max SAS ({week.max_sas})"}
                ),
                400,
            )

    # Validate no_keycheat
    if week.no_keycheat:
        from keytracker.match_helpers import deck_has_keycheat

        if deck_has_keycheat(deck.id):
            return (
                jsonify(
                    {"error": "Deck contains a keycheat card (prohibited this week)"}
                ),
                400,
            )

    # Within-week same-team deck uniqueness check (all formats)
    if target_team:
        team_user_ids = {m.user_id for m in target_team.members} - {target_user_id}
        if team_user_ids:
            teammate_sel = PlayerDeckSelection.query.filter(
                PlayerDeckSelection.week_id == week.id,
                PlayerDeckSelection.deck_id == deck.id,
                PlayerDeckSelection.user_id.in_(team_user_ids),
            ).first()
            if teammate_sel:
                u = db.session.get(User, teammate_sel.user_id)
                name = u.name if u else "a teammate"
                return (
                    jsonify(
                        {"error": f"Deck already selected by teammate {name} this week"}
                    ),
                    409,
                )

    # Cross-week deck uniqueness check (skip for sealed formats)
    if week.format_type not in (
        WeekFormat.SEALED_ARCHON.value,
        WeekFormat.SEALED_ALLIANCE.value,
    ):
        conflicts = _check_deck_cross_week_conflicts(league, week, deck, target_team)
        if conflicts:
            return jsonify({"error": " ".join(conflicts)}), 409

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

    db.session.flush()

    # Triad-specific validation (check whenever 2+ decks selected)
    if week.format_type == WeekFormat.TRIAD.value:
        all_selections = PlayerDeckSelection.query.filter_by(
            week_id=week.id, user_id=target_user_id
        ).all()
        if len(all_selections) >= 2:
            selected_decks = [Deck.query.get(s.deck_id) for s in all_selections]
            selected_decks = [d for d in selected_decks if d is not None]

            # Combined max SAS (only enforce when all 3 slots filled)
            if len(all_selections) == 3 and week.combined_max_sas is not None:
                total_sas = sum(d.sas_rating or 0 for d in selected_decks)
                if total_sas > week.combined_max_sas:
                    db.session.rollback()
                    return (
                        jsonify(
                            {
                                "error": f"Combined SAS ({total_sas}) exceeds limit ({week.combined_max_sas})"
                            }
                        ),
                        400,
                    )

            # Set diversity: no two decks share an expansion
            if week.set_diversity:
                expansions = [d.expansion for d in selected_decks]
                if len(set(expansions)) != len(expansions):
                    db.session.rollback()
                    return (
                        jsonify(
                            {
                                "error": "Set diversity required: no two decks can share an expansion"
                            }
                        ),
                        400,
                    )

            # House diversity: no two decks share any house
            if week.house_diversity:
                all_houses = []
                for d in selected_decks:
                    houses = {
                        ps.house for ps in d.pod_stats if ps.house != "Archon Power"
                    }
                    all_houses.append(houses)
                for i in range(len(all_houses)):
                    for j in range(i + 1, len(all_houses)):
                        shared = all_houses[i] & all_houses[j]
                        if shared:
                            db.session.rollback()
                            return (
                                jsonify(
                                    {
                                        "error": f"House diversity required: decks share house(s): {', '.join(shared)}"
                                    }
                                ),
                                400,
                            )

    db.session.commit()

    # Return all selections for this user/week
    selections = (
        PlayerDeckSelection.query.filter_by(week_id=week.id, user_id=target_user_id)
        .order_by(PlayerDeckSelection.slot_number)
        .all()
    )
    return jsonify([serialize_deck_selection(s) for s in selections])


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/deck-selection/<int:slot>", methods=["DELETE"]
)
@login_required
def remove_deck_selection(league_id, week_id, slot):
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404

    if week.status not in (
        WeekStatus.DECK_SELECTION.value,
        WeekStatus.TEAM_PAIRED.value,
        WeekStatus.PAIRING.value,
    ):
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
                if any(
                    m.user_id == effective.id and m.is_captain for m in team.members
                ):
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


# --- Feature designation ---


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/feature-designation", methods=["POST"]
)
@login_required
def set_feature_designation(league_id, week_id):
    """Set the feature player for the requesting captain's team for this week."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.status in (
        WeekStatus.SETUP.value,
        WeekStatus.PAIRING.value,
        WeekStatus.PUBLISHED.value,
        WeekStatus.COMPLETED.value,
    ):
        return (
            jsonify(
                {
                    "error": "Feature designation is not allowed after player pairings are generated"
                }
            ),
            400,
        )

    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    effective = get_effective_user()
    is_admin = _is_league_admin(league, effective)

    # Find the team that user_id belongs to
    target_team = None
    for team in league.teams:
        if any(m.user_id == user_id for m in team.members):
            target_team = team
            break
    if not target_team:
        return (
            jsonify({"error": "User is not a member of any team in this league"}),
            404,
        )

    # Auth: must be captain of that team or league admin
    is_captain = (
        TeamMember.query.filter_by(
            team_id=target_team.id, user_id=effective.id, is_captain=True
        ).first()
        is not None
    )
    if not is_admin and not is_captain:
        return jsonify({"error": "Must be captain of the team or league admin"}), 403

    # Ensure this player hasn't been the feature player in any other week of this league
    other_fd = (
        FeatureDesignation.query.join(
            LeagueWeek, FeatureDesignation.week_id == LeagueWeek.id
        )
        .filter(
            LeagueWeek.league_id == league.id,
            FeatureDesignation.week_id != week.id,
            FeatureDesignation.user_id == user_id,
        )
        .first()
    )
    if other_fd:
        other_week = db.session.get(LeagueWeek, other_fd.week_id)
        week_label = (
            (other_week.name or f"Week {other_week.week_number}")
            if other_week
            else "another week"
        )
        return (
            jsonify(
                {"error": f"This player is already the feature player for {week_label}"}
            ),
            400,
        )

    # Upsert: delete existing designation for this team+week, then insert new one
    FeatureDesignation.query.filter_by(week_id=week.id, team_id=target_team.id).delete()
    fd = FeatureDesignation(week_id=week.id, team_id=target_team.id, user_id=user_id)
    db.session.add(fd)
    db.session.commit()
    db.session.refresh(week)
    viewer = effective if current_user.is_authenticated else None
    return jsonify(serialize_league_week(week, viewer=viewer))


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/feature-designation", methods=["DELETE"]
)
@login_required
def clear_feature_designation(league_id, week_id):
    """Clear the feature player designation for the requesting captain's team."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.status in (
        WeekStatus.SETUP.value,
        WeekStatus.PAIRING.value,
        WeekStatus.PUBLISHED.value,
        WeekStatus.COMPLETED.value,
    ):
        return (
            jsonify(
                {
                    "error": "Feature designation is not allowed after player pairings are generated"
                }
            ),
            400,
        )

    effective = get_effective_user()
    is_admin = _is_league_admin(league, effective)

    # Find the team the effective user captains
    captain_team = None
    for team in league.teams:
        if TeamMember.query.filter_by(
            team_id=team.id, user_id=effective.id, is_captain=True
        ).first():
            captain_team = team
            break

    if not captain_team and not is_admin:
        return jsonify({"error": "Must be a team captain or league admin"}), 403

    if is_admin and not captain_team:
        # Admin: require team_id in body
        data = request.get_json(silent=True) or {}
        team_id = data.get("team_id")
        if not team_id:
            return jsonify({"error": "team_id required for admin"}), 400
        FeatureDesignation.query.filter_by(week_id=week.id, team_id=team_id).delete()
    else:
        FeatureDesignation.query.filter_by(
            week_id=week.id, team_id=captain_team.id
        ).delete()

    db.session.commit()
    db.session.refresh(week)
    viewer = effective if current_user.is_authenticated else None
    return jsonify(serialize_league_week(week, viewer=viewer))


# --- Thief format routes ---


@blueprint.route("/<int:league_id>/weeks/<int:week_id>/curation-deck", methods=["POST"])
@login_required
def submit_curation_deck(league_id, week_id):
    """Captain submits a deck URL for the team's curation pool."""
    from keytracker.utils import get_deck_by_id_with_zeal

    league, err = _get_league_or_404(league_id)
    if err:
        return err
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.format_type != WeekFormat.THIEF.value:
        return jsonify({"error": "Only for Thief format"}), 400
    if week.status not in (WeekStatus.CURATION.value, WeekStatus.TEAM_PAIRED.value):
        return jsonify({"error": "Curation is not open"}), 400

    effective = get_effective_user()
    # Must be captain of their team
    captain_team = None
    for team in league.teams:
        m = TeamMember.query.filter_by(
            team_id=team.id, user_id=effective.id, is_captain=True
        ).first()
        if m:
            captain_team = team
            break
    if not captain_team and not _is_league_admin(league, effective):
        return jsonify({"error": "Only team captains can submit curation decks"}), 403

    # Admin acting: get team_id from body
    if not captain_team:
        data_tmp = request.get_json(silent=True) or {}
        team_id = data_tmp.get("team_id")
        if not team_id:
            return jsonify({"error": "team_id required for admin"}), 400
        captain_team = db.session.get(Team, team_id)
        if not captain_team or captain_team.league_id != league.id:
            return jsonify({"error": "Team not found"}), 404

    data = request.get_json(silent=True) or {}
    deck_url = (data.get("deck_url") or "").strip()
    slot_number = data.get("slot_number")

    if not deck_url:
        return jsonify({"error": "deck_url is required"}), 400
    if (
        not isinstance(slot_number, int)
        or slot_number < 1
        or slot_number > league.team_size
    ):
        return (
            jsonify({"error": f"slot_number must be between 1 and {league.team_size}"}),
            400,
        )

    # Check slot not already occupied
    existing = ThiefCurationDeck.query.filter_by(
        week_id=week.id, team_id=captain_team.id, slot_number=slot_number
    ).first()
    if existing:
        return jsonify({"error": f"Slot {slot_number} already has a deck"}), 400

    kf_id = _parse_deck_url(deck_url)
    if not kf_id:
        return jsonify({"error": "Could not parse deck ID from URL"}), 400

    try:
        deck = get_deck_by_id_with_zeal(kf_id)
    except Exception as e:
        logger.error("Failed to fetch deck %s: %s", kf_id, e)
        return jsonify({"error": f"Failed to fetch deck: {str(e)}"}), 400

    cd = ThiefCurationDeck(
        week_id=week.id,
        team_id=captain_team.id,
        deck_id=deck.id,
        slot_number=slot_number,
    )
    db.session.add(cd)
    db.session.commit()
    db.session.refresh(week)
    viewer = effective if current_user.is_authenticated else None
    return jsonify(serialize_league_week(week, viewer=viewer))


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/curation-deck/<int:slot>", methods=["DELETE"]
)
@login_required
def remove_curation_deck(league_id, week_id, slot):
    """Captain removes a deck from the team's curation pool."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.format_type != WeekFormat.THIEF.value:
        return jsonify({"error": "Only for Thief format"}), 400
    if week.status not in (WeekStatus.CURATION.value, WeekStatus.TEAM_PAIRED.value):
        return jsonify({"error": "Curation is not open"}), 400

    effective = get_effective_user()
    captain_team = None
    for team in league.teams:
        m = TeamMember.query.filter_by(
            team_id=team.id, user_id=effective.id, is_captain=True
        ).first()
        if m:
            captain_team = team
            break
    if not captain_team and not _is_league_admin(league, effective):
        return jsonify({"error": "Only team captains can remove curation decks"}), 403

    team_id = captain_team.id if captain_team else None
    if not team_id:
        team_id = request.args.get("team_id", type=int)
        if not team_id:
            return jsonify({"error": "team_id required"}), 400

    cd = ThiefCurationDeck.query.filter_by(
        week_id=week.id, team_id=team_id, slot_number=slot
    ).first()
    if not cd:
        return jsonify({"error": "Curation deck not found"}), 404

    db.session.delete(cd)
    db.session.commit()
    return "", 204


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/advance-to-thief", methods=["POST"]
)
@login_required
def advance_to_thief(league_id, week_id):
    """Admin advances from curation to thief status."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league, get_effective_user()):
        return jsonify({"error": "Admin access required"}), 403
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.format_type != WeekFormat.THIEF.value:
        return jsonify({"error": "Only for Thief format"}), 400
    if week.status != WeekStatus.TEAM_PAIRED.value:
        return jsonify({"error": "Week must be in team_paired status"}), 400

    # Validate each team has exactly team_size curation decks
    teams = league.teams
    for team in teams:
        count = ThiefCurationDeck.query.filter_by(
            week_id=week.id, team_id=team.id
        ).count()
        if count != league.team_size:
            return (
                jsonify(
                    {
                        "error": f"Team '{team.name}' has {count}/{league.team_size} curation decks"
                    }
                ),
                400,
            )

    # The per-matchup coin toss (thief_stolen_team_id) was already set during
    # generate_team_pairings — no additional week-level randomization needed.
    week.status = WeekStatus.THIEF_STEP.value
    db.session.commit()
    db.session.refresh(week)
    viewer = get_effective_user() if current_user.is_authenticated else None
    return jsonify(serialize_league_week(week, viewer=viewer))


@blueprint.route("/<int:league_id>/weeks/<int:week_id>/steal", methods=["POST"])
@login_required
def submit_steals(league_id, week_id):
    """Team member submits steal selections for opponent's curation decks."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.format_type != WeekFormat.THIEF.value:
        return jsonify({"error": "Only for Thief format"}), 400
    if week.status != WeekStatus.THIEF_STEP.value:
        return jsonify({"error": "Week must be in thief status"}), 400

    effective = get_effective_user()
    # Find user's team
    player_team = None
    for team in league.teams:
        if any(m.user_id == effective.id for m in team.members):
            player_team = team
            break
    if not player_team:
        return jsonify({"error": "You are not on a team in this league"}), 403

    data = request.get_json(silent=True) or {}
    curation_deck_ids = data.get("curation_deck_ids", [])
    if not isinstance(curation_deck_ids, list):
        return jsonify({"error": "curation_deck_ids must be a list"}), 400

    # Determine how many this team should steal using the per-matchup coin toss.
    # The team with thief_stolen_team_id == their team favors thieving (ceil steals);
    # their opponent steals floor.
    n = league.team_size
    wm_for_steal = WeekMatchup.query.filter(
        WeekMatchup.week_id == week.id,
        db.or_(
            WeekMatchup.team1_id == player_team.id,
            WeekMatchup.team2_id == player_team.id,
        ),
    ).first()
    if wm_for_steal and wm_for_steal.thief_stolen_team_id:
        if wm_for_steal.thief_stolen_team_id == player_team.id:
            required_count = math.ceil(n / 2)
        else:
            required_count = math.floor(n / 2)
    else:
        # Fallback for legacy weeks that used thief_floor_team_id on the week
        required_count = (
            math.floor(n / 2)
            if week.thief_floor_team_id == player_team.id
            else math.ceil(n / 2)
        )

    if len(curation_deck_ids) != required_count:
        return jsonify({"error": f"Must steal exactly {required_count} decks"}), 400

    # Find opponent team (the team in the same matchup pairing)
    # If matchups exist, use them; otherwise allow selecting from any opposing team
    opponent_team_ids = set()
    matchups = WeekMatchup.query.filter_by(week_id=week.id).all()
    if matchups:
        for wm in matchups:
            if wm.team1_id == player_team.id:
                opponent_team_ids.add(wm.team2_id)
            elif wm.team2_id == player_team.id:
                opponent_team_ids.add(wm.team1_id)
    else:
        # Before team pairings: can steal from any other team
        opponent_team_ids = {t.id for t in league.teams if t.id != player_team.id}

    # Validate all selected curation decks belong to opponent teams
    for cd_id in curation_deck_ids:
        cd = db.session.get(ThiefCurationDeck, cd_id)
        if not cd:
            return jsonify({"error": f"Curation deck {cd_id} not found"}), 400
        if cd.week_id != week.id:
            return (
                jsonify(
                    {"error": f"Curation deck {cd_id} belongs to a different week"}
                ),
                400,
            )
        if cd.team_id not in opponent_team_ids:
            return (
                jsonify(
                    {"error": f"Curation deck {cd_id} is not from an opponent team"}
                ),
                400,
            )

    # Replace steals for this team
    ThiefSteal.query.filter_by(
        week_id=week.id, stealing_team_id=player_team.id
    ).delete()
    for cd_id in curation_deck_ids:
        steal = ThiefSteal(
            week_id=week.id,
            stealing_team_id=player_team.id,
            curation_deck_id=cd_id,
        )
        db.session.add(steal)

    db.session.commit()
    db.session.refresh(week)
    viewer = effective if current_user.is_authenticated else None
    return jsonify(serialize_league_week(week, viewer=viewer))


@blueprint.route("/<int:league_id>/weeks/<int:week_id>/end-thief", methods=["POST"])
@login_required
def end_thief(league_id, week_id):
    """Admin ends thief phase and advances to deck_selection."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league, get_effective_user()):
        return jsonify({"error": "Admin access required"}), 403
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.format_type != WeekFormat.THIEF.value:
        return jsonify({"error": "Only for Thief format"}), 400
    if week.status != WeekStatus.THIEF_STEP.value:
        return jsonify({"error": "Week must be in thief status"}), 400

    # Validate steal counts
    n = league.team_size
    for team in league.teams:
        if week.thief_floor_team_id == team.id:
            required = math.floor(n / 2)
        else:
            required = math.ceil(n / 2)
        count = ThiefSteal.query.filter_by(
            week_id=week.id, stealing_team_id=team.id
        ).count()
        if count != required:
            return (
                jsonify(
                    {"error": f"Team '{team.name}' has stolen {count}/{required} decks"}
                ),
                400,
            )

    week.status = WeekStatus.DECK_SELECTION.value
    db.session.commit()
    db.session.refresh(week)
    viewer = get_effective_user() if current_user.is_authenticated else None
    return jsonify(serialize_league_week(week, viewer=viewer))


# --- Strike phase (Triad) ---


@blueprint.route("/<int:league_id>/matches/<int:matchup_id>/strike", methods=["POST"])
@login_required
def submit_strike(league_id, matchup_id):
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
    if week.format_type != WeekFormat.TRIAD.value:
        return jsonify({"error": "Strikes are only for Triad format"}), 400
    if week.status != WeekStatus.PUBLISHED.value:
        return jsonify({"error": "Week is not published"}), 400

    # Both must have started
    if not pm.player1_started or not pm.player2_started:
        return jsonify({"error": "Both players must start before striking"}), 400

    effective = get_effective_user()
    if effective.id not in (pm.player1_id, pm.player2_id):
        return jsonify({"error": "You are not in this matchup"}), 403

    # Check not already struck
    existing_strike = StrikeSelection.query.filter_by(
        player_matchup_id=pm.id, striking_user_id=effective.id
    ).first()
    if existing_strike:
        return jsonify({"error": "You have already submitted a strike"}), 400

    data = request.get_json(silent=True) or {}
    struck_selection_id = data.get("struck_deck_selection_id")
    if not struck_selection_id:
        return jsonify({"error": "struck_deck_selection_id is required"}), 400

    # Validate: struck deck must belong to the opponent
    opponent_id = pm.player2_id if effective.id == pm.player1_id else pm.player1_id
    struck_sel = db.session.get(PlayerDeckSelection, struck_selection_id)
    if (
        not struck_sel
        or struck_sel.user_id != opponent_id
        or struck_sel.week_id != week.id
    ):
        return jsonify({"error": "Invalid deck selection to strike"}), 400

    strike = StrikeSelection(
        player_matchup_id=pm.id,
        striking_user_id=effective.id,
        struck_deck_selection_id=struck_selection_id,
    )
    db.session.add(strike)
    db.session.commit()

    return jsonify(serialize_player_matchup(pm))


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

    p1_deck_id = data.get("player1_deck_id")
    p2_deck_id = data.get("player2_deck_id")

    # Adaptive: block game 3 until bidding is complete
    if week.format_type == WeekFormat.ADAPTIVE.value and game_number == 3:
        if not pm.adaptive_bidding_complete:
            return (
                jsonify(
                    {
                        "error": "Adaptive bidding must be completed before game 3 can be played"
                    }
                ),
                400,
            )

    # Triad-specific validation
    if week.format_type == WeekFormat.TRIAD.value:
        if not p1_deck_id or not p2_deck_id:
            return (
                jsonify(
                    {"error": "player1_deck_id and player2_deck_id required for Triad"}
                ),
                400,
            )

        # Get stricken deck selection IDs
        stricken_sel_ids = {s.struck_deck_selection_id for s in pm.strikes}
        stricken_deck_ids = set()
        for sel_id in stricken_sel_ids:
            sel = db.session.get(PlayerDeckSelection, sel_id)
            if sel:
                stricken_deck_ids.add(sel.deck_id)

        # Validate decks aren't stricken
        if p1_deck_id in stricken_deck_ids:
            return jsonify({"error": "Player 1's selected deck has been stricken"}), 400
        if p2_deck_id in stricken_deck_ids:
            return jsonify({"error": "Player 2's selected deck has been stricken"}), 400

        # Validate decks that already won can't be reused
        for g in existing_games:
            if g.winner_id == pm.player1_id and g.player1_deck_id == p1_deck_id:
                return (
                    jsonify(
                        {
                            "error": "Player 1's deck already won a game and cannot be reused"
                        }
                    ),
                    400,
                )
            if g.winner_id == pm.player2_id and g.player2_deck_id == p2_deck_id:
                return (
                    jsonify(
                        {
                            "error": "Player 2's deck already won a game and cannot be reused"
                        }
                    ),
                    400,
                )

    game = MatchGame(
        player_matchup_id=pm.id,
        game_number=game_number,
        winner_id=winner_id,
        player1_keys=p1_keys,
        player2_keys=p2_keys,
        went_to_time=bool(data.get("went_to_time", False)),
        loser_conceded=bool(data.get("loser_conceded", False)),
        player1_deck_id=p1_deck_id,
        player2_deck_id=p2_deck_id,
        reported_by_id=effective.id,
    )
    db.session.add(game)
    db.session.flush()
    # Expire pm so _check_week_completion reloads pm.games from the DB
    # rather than the stale in-memory collection that predates this flush
    db.session.expire(pm, ["games"])

    # Adaptive: after game 2 creates a 1-1 tie, initialize bidding
    if week.format_type == WeekFormat.ADAPTIVE.value and game_number == 2:
        from keytracker.match_helpers import (
            get_adaptive_winning_deck_player_id,
            init_adaptive_bidding,
        )

        winning_deck_player_id = get_adaptive_winning_deck_player_id(pm)
        if winning_deck_player_id is not None:
            init_adaptive_bidding(pm)

    # Check if match is now complete - auto-complete week if all matches done
    all_games = sorted(pm.games, key=lambda g: g.game_number)
    p1_total = sum(1 for g in all_games if g.winner_id == pm.player1_id)
    p2_total = sum(1 for g in all_games if g.winner_id == pm.player2_id)

    # Check if entire week is complete
    if p1_total >= wins_needed or p2_total >= wins_needed:
        _check_week_completion(week)

    db.session.commit()
    return jsonify(serialize_match_game(game)), 201


@blueprint.route(
    "/<int:league_id>/matches/<int:matchup_id>/adaptive-bid", methods=["POST"]
)
@login_required
def submit_adaptive_bid(league_id, matchup_id):
    """Submit an adaptive bid or concede for a league match."""
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
    if week.format_type != WeekFormat.ADAPTIVE.value:
        return jsonify({"error": "Only for Adaptive format"}), 400
    if week.status != WeekStatus.PUBLISHED.value:
        return jsonify({"error": "Week is not published"}), 400

    effective = get_effective_user()
    is_participant = effective.id in (pm.player1_id, pm.player2_id)
    if not is_participant:
        return jsonify({"error": "You are not in this matchup"}), 403

    data = request.get_json(silent=True) or {}
    chains = data.get("chains")
    concede = bool(data.get("concede", False))

    from keytracker.match_helpers import validate_adaptive_bid

    success, error = validate_adaptive_bid(
        pm, effective.id, chains=chains, concede=concede
    )
    if not success:
        return jsonify({"error": error}), 400

    db.session.commit()
    viewer = get_effective_user() if current_user.is_authenticated else None
    return jsonify(serialize_player_matchup(pm, viewer=viewer))


def _check_week_completion(week):
    """Check if all matches in a week are complete, and if so mark week as COMPLETED.

    Also transitions the league to PLAYOFFS if all weeks are now complete.
    """
    wins_needed = math.ceil(week.best_of_n / 2)
    for wm in week.matchups:
        for pm in wm.player_matchups:
            games = sorted(pm.games, key=lambda g: g.game_number)
            p1_wins = sum(1 for g in games if g.winner_id == pm.player1_id)
            p2_wins = sum(1 for g in games if g.winner_id == pm.player2_id)
            if p1_wins < wins_needed and p2_wins < wins_needed:
                return  # Not all matches complete
    week.status = WeekStatus.COMPLETED.value

    # Check if all weeks in the league are now complete
    league = week.league
    if league.status == LeagueStatus.ACTIVE.value:
        all_weeks = league.weeks
        if all_weeks and all(w.status == WeekStatus.COMPLETED.value for w in all_weeks):
            league.status = LeagueStatus.PLAYOFFS.value


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/check-completion", methods=["POST"]
)
@login_required
def check_week_completion(league_id, week_id):
    """Manually trigger the week completion check. Admin-only."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    if not _is_league_admin(league, get_effective_user()):
        return jsonify({"error": "Admin access required"}), 403
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.status != WeekStatus.PUBLISHED.value:
        return jsonify({"error": "Week must be in published status"}), 400
    _check_week_completion(week)
    db.session.commit()
    db.session.refresh(week)
    return jsonify(serialize_league_week(week))


# --- Admin Log ---


@blueprint.route("/<int:league_id>/admin-log", methods=["GET"])
def get_admin_log(league_id):
    """Return last 200 admin log entries for the league (public)."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    entries = (
        LeagueAdminLog.query.filter_by(league_id=league.id)
        .order_by(LeagueAdminLog.created_at.desc())
        .limit(200)
        .all()
    )
    return jsonify([serialize_admin_log_entry(e) for e in entries])


# --- Regenerate Player Matchups ---


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/regenerate-player-matchups", methods=["POST"]
)
@login_required
def regenerate_player_matchups(league_id, week_id):
    """Delete all PlayerMatchup rows and re-run pairing generation. Admin-only, pairing status only."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    user = get_effective_user()
    if not _is_league_admin(league, user):
        return jsonify({"error": "Admin access required"}), 403
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.status != WeekStatus.PAIRING.value:
        return jsonify({"error": "Week must be in pairing status"}), 400

    matchups = WeekMatchup.query.filter_by(week_id=week.id).all()
    if not matchups:
        return jsonify({"error": "No team pairings found"}), 400

    # Delete all existing player matchups
    for wm in matchups:
        PlayerMatchup.query.filter_by(week_matchup_id=wm.id).delete()
    db.session.flush()

    # Re-run pairing generation
    for wm in matchups:
        team1 = db.session.get(Team, wm.team1_id)
        team2 = db.session.get(Team, wm.team2_id)
        if week.format_type == WeekFormat.THIEF.value:
            player_pairs = _generate_thief_player_pairings(
                team1, team2, wm, league, week
            )
        else:
            player_pairs = _generate_player_pairings(
                team1, team2, league, week, week.week_number
            )
        for p1_id, p2_id, is_feature in player_pairs:
            pm = PlayerMatchup(
                week_matchup_id=wm.id,
                player1_id=p1_id,
                player2_id=p2_id,
                is_feature=is_feature,
            )
            db.session.add(pm)

    _log_admin_action(league.id, week.id, user.id, "player_matchups_regenerated")
    db.session.commit()
    db.session.refresh(week)
    return jsonify(serialize_league_week(week))


# --- Regenerate Sealed Pools ---


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/regenerate-sealed-pools", methods=["POST"]
)
@login_required
def regenerate_sealed_pools(league_id, week_id):
    """Regenerate sealed pools for all or specific players. Admin-only."""
    from sqlalchemy.sql.expression import func as sql_func

    league, err = _get_league_or_404(league_id)
    if err:
        return err
    user = get_effective_user()
    if not _is_league_admin(league, user):
        return jsonify({"error": "Admin access required"}), 403
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404
    if week.format_type not in (
        WeekFormat.SEALED_ARCHON.value,
        WeekFormat.SEALED_ALLIANCE.value,
    ):
        return (
            jsonify(
                {
                    "error": "Sealed pools only for Sealed Archon or Sealed Alliance format"
                }
            ),
            400,
        )
    if week.status not in (
        WeekStatus.DECK_SELECTION.value,
        WeekStatus.TEAM_PAIRED.value,
    ):
        return (
            jsonify({"error": "Week must be in deck_selection or team_paired status"}),
            400,
        )
    if not week.sealed_pools_generated:
        return jsonify({"error": "Sealed pools have not been generated yet"}), 400

    data = request.get_json(silent=True) or {}
    target_user_ids = data.get("user_ids")  # optional list of int

    active_members = _get_active_players(league)
    if target_user_ids is not None:
        active_members = [m for m in active_members if m.user_id in target_user_ids]

    if not active_members:
        return jsonify({"error": "No target players found"}), 400

    decks_per_player = week.decks_per_player or 4

    # Collect already-assigned deck ids for players NOT being regenerated
    all_member_ids = {m.user_id for m in _get_active_players(league)}
    regen_ids = {m.user_id for m in active_members}
    kept_ids = all_member_ids - regen_ids
    excluded_deck_ids = set()
    if kept_ids:
        kept_pools = SealedPoolDeck.query.filter(
            SealedPoolDeck.week_id == week.id,
            SealedPoolDeck.user_id.in_(kept_ids),
        ).all()
        excluded_deck_ids = {spd.deck_id for spd in kept_pools}

    # For each target player: delete their pool, selections, and pod selections
    for member in active_members:
        uid = member.user_id
        SealedPoolDeck.query.filter_by(week_id=week.id, user_id=uid).delete()
        PlayerDeckSelection.query.filter_by(week_id=week.id, user_id=uid).delete()
        AlliancePodSelection.query.filter_by(week_id=week.id, user_id=uid).delete()

    db.session.flush()

    total_needed = decks_per_player * len(active_members)
    query = Deck.query
    if week.allowed_sets:
        try:
            allowed = json.loads(week.allowed_sets)
            query = query.filter(Deck.expansion.in_(allowed))
        except (json.JSONDecodeError, TypeError):
            pass
    if excluded_deck_ids:
        query = query.filter(~Deck.id.in_(excluded_deck_ids))

    decks = query.order_by(sql_func.rand()).limit(total_needed).all()
    if len(decks) < total_needed:
        db.session.rollback()
        return (
            jsonify(
                {
                    "error": f"Not enough decks in database ({len(decks)} available, {total_needed} needed)"
                }
            ),
            400,
        )

    random.shuffle(decks)
    for i, member in enumerate(active_members):
        player_decks = decks[i * decks_per_player : (i + 1) * decks_per_player]
        for d in player_decks:
            spd = SealedPoolDeck(week_id=week.id, user_id=member.user_id, deck_id=d.id)
            db.session.add(spd)

    details = f"Regenerated for {len(active_members)} player(s)"
    _log_admin_action(league.id, week.id, user.id, "sealed_pools_regenerated", details)
    db.session.commit()
    db.session.refresh(week)
    return jsonify(serialize_league_week(week))


# --- Completed Match Decks ---


@blueprint.route(
    "/<int:league_id>/weeks/<int:week_id>/completed-match-decks", methods=["GET"]
)
def completed_match_decks(league_id, week_id):
    """Return deck info for completed player matchups in the week. Public endpoint."""
    league, err = _get_league_or_404(league_id)
    if err:
        return err
    week = db.session.get(LeagueWeek, week_id)
    if not week or week.league_id != league.id:
        return jsonify({"error": "Week not found"}), 404

    wins_needed = math.ceil(week.best_of_n / 2)
    is_alliance = week.format_type == WeekFormat.SEALED_ALLIANCE.value
    result = {}

    for wm in week.matchups:
        for pm in wm.player_matchups:
            p1_wins = sum(1 for g in pm.games if g.winner_id == pm.player1_id)
            p2_wins = sum(1 for g in pm.games if g.winner_id == pm.player2_id)
            if p1_wins < wins_needed and p2_wins < wins_needed:
                continue  # not complete

            if is_alliance:

                def _pods_for(user_id):
                    sels = (
                        AlliancePodSelection.query.filter_by(
                            week_id=week.id, user_id=user_id
                        )
                        .order_by(
                            AlliancePodSelection.slot_type,
                            AlliancePodSelection.slot_number,
                        )
                        .all()
                    )
                    return [
                        {
                            "deck": serialize_deck_brief(s.deck) if s.deck else None,
                            "house_name": s.house_name,
                            "slot_type": s.slot_type,
                            "slot_number": s.slot_number,
                        }
                        for s in sels
                        if s.deck
                    ]

                result[str(pm.id)] = {
                    "player1_pods": _pods_for(pm.player1_id),
                    "player2_pods": _pods_for(pm.player2_id),
                }
            else:
                p1_sels = (
                    PlayerDeckSelection.query.filter_by(
                        week_id=week.id, user_id=pm.player1_id
                    )
                    .order_by(PlayerDeckSelection.slot_number)
                    .all()
                )
                p2_sels = (
                    PlayerDeckSelection.query.filter_by(
                        week_id=week.id, user_id=pm.player2_id
                    )
                    .order_by(PlayerDeckSelection.slot_number)
                    .all()
                )
                result[str(pm.id)] = {
                    "player1_decks": [
                        serialize_deck_brief(s.deck) for s in p1_sels if s.deck
                    ],
                    "player2_decks": [
                        serialize_deck_brief(s.deck) for s in p2_sels if s.deck
                    ],
                }

    return jsonify(result)
