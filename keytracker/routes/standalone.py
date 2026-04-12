"""
Standalone (one-off) match routes.
Supports: archon_standard, triad, sealed_archon, sealed_alliance, alliance.
Thief format is NOT supported here and should remain so until explicitly requested
(thief has team-based mechanics incompatible with 1v1 standalone play).

Business logic shared with leagues.py via keytracker/match_helpers.py.
When adding new formats to leagues.py, also update standalone.py.
See keytracker/routes/FORMATS.md for full details.
"""

import datetime
import logging
import math
import uuid as uuid_module

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from keytracker.routes.auth import member_required

from keytracker.schema import (
    db,
    User,
    Deck,
    PlayerMatchup,
    PlayerDeckSelection,
    AlliancePodSelection,
    SealedPoolDeck,
    StrikeSelection,
    TriadShortPick,
    AdaptiveShortChoice,
    ExchangeBorrow,
    NordicHexadAction,
    MoiraiAssignment,
    StandaloneMatch,
    StandaloneMatchStatus,
    WeekFormat,
)
from keytracker.serializers import (
    serialize_standalone_match,
    serialize_sealed_pool_entry,
    serialize_alliance_selection,
    serialize_player_matchup,
    serialize_match_game,
)
from keytracker.response_helpers import etag_response
from keytracker.match_helpers import (
    validate_deck_for_standalone,
    generate_sealed_pools_for_standalone,
    validate_alliance_for_standalone,
    validate_alliance_open,
    validate_strike_standalone,
    validate_triad_short_pick,
    validate_oubliette_ban,
    get_oubliette_eligible_deck_ids,
    validate_adaptive_short_choice,
    init_adaptive_short_bidding,
    validate_adaptive_short_bid,
    validate_exchange_borrow,
    check_exchange_win_condition,
    _get_exchange_selections,
    validate_nordic_action,
    advance_nordic_phase,
    get_nordic_remaining_deck_ids,
    validate_moirai_assignments,
    get_moirai_game_deck_sel_ids,
    get_moirai_g3_pool_sel_ids,
    validate_moirai_adaptive_choice,
    validate_and_record_game,
    validate_adaptive_bid,
)

logger = logging.getLogger(__name__)

standalone_bp = Blueprint(
    "standalone", __name__, url_prefix="/api/v2/standalone-matches"
)

SEALED_FORMATS = (WeekFormat.SEALED_ARCHON, WeekFormat.SEALED_ALLIANCE)
ALLIANCE_FORMATS = (WeekFormat.SEALED_ALLIANCE, WeekFormat.ALLIANCE)


def _parse_deck_url(url_str):
    """Extract kf_id from a deck URL or raw ID."""
    import re

    url_str = url_str.strip()
    m = re.search(r"keyforgegame\.com/deck-details/([a-f0-9-]+)", url_str)
    if m:
        return m.group(1)
    m = re.search(r"decksofkeyforge\.com/decks/([a-f0-9-]+)", url_str)
    if m:
        return m.group(1)
    m = re.match(
        r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", url_str
    )
    if m:
        return url_str
    return None


def _cleanup_old_matches():
    """Delete unfinished standalone matches older than 24h."""
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
    StandaloneMatch.query.filter(
        StandaloneMatch.status != StandaloneMatchStatus.COMPLETED,
        StandaloneMatch.created_at < cutoff,
    ).delete(synchronize_session=False)
    db.session.commit()


def _get_match_or_404(match_id):
    match = db.session.get(StandaloneMatch, match_id)
    if match is None:
        return None, (jsonify({"error": "Match not found"}), 404)
    return match, None


def _current_user_or_guest():
    """Return current user if authenticated, else create/return guest user."""
    if current_user.is_authenticated:
        return current_user
    # Try to get or create the nobody@example.com guest user
    guest = User.query.filter_by(email="nobody@example.com").first()
    return guest


@standalone_bp.route("/", methods=["POST"])
@member_required
def create_match():
    """Create a new standalone match."""
    data = request.get_json(silent=True) or {}

    format_str = data.get("format_type", "")
    try:
        format_type = WeekFormat(format_str)
    except ValueError:
        return jsonify({"error": f"Invalid format_type: {format_str}"}), 400

    if format_type == WeekFormat.THIEF:
        return (
            jsonify({"error": "Thief format is not supported for standalone matches"}),
            400,
        )

    best_of_n = data.get("best_of_n", 1)
    if not isinstance(best_of_n, int) or best_of_n < 1:
        return jsonify({"error": "best_of_n must be a positive integer"}), 400
    if format_type in (
        WeekFormat.TRIAD,
        WeekFormat.ADAPTIVE,
        WeekFormat.EXCHANGE,
        WeekFormat.NORDIC_HEXAD,
        WeekFormat.MOIRAI,
    ):
        best_of_n = 3  # These formats are always best of 3
    if format_type in (
        WeekFormat.REVERSAL,
        WeekFormat.TRIAD_SHORT,
        WeekFormat.OUBLIETTE,
        WeekFormat.ADAPTIVE_SHORT,
    ):
        best_of_n = 1  # These formats are always BO1

    is_public = bool(data.get("is_public", False))
    max_sas = data.get("max_sas")
    combined_max_sas = data.get("combined_max_sas")
    set_diversity = bool(data.get("set_diversity", False))
    house_diversity = bool(data.get("house_diversity", False))
    allowed_sets = data.get("allowed_sets")
    is_sealed = format_type in (WeekFormat.SEALED_ARCHON, WeekFormat.SEALED_ALLIANCE)
    decks_per_player = data.get("decks_per_player", 3 if is_sealed else 1)

    if allowed_sets is not None and not isinstance(allowed_sets, list):
        return jsonify({"error": "allowed_sets must be a list of set numbers"}), 400
    if not isinstance(decks_per_player, int) or decks_per_player < 1:
        return jsonify({"error": "decks_per_player must be a positive integer"}), 400

    # Alliance format: accept optional restricted list version
    alliance_restricted_list_version_id = None
    if format_type == WeekFormat.ALLIANCE:
        from keytracker.schema import AllianceRestrictedListVersion

        rl_id = data.get("alliance_restricted_list_version_id")
        if rl_id is not None:
            rl_version = db.session.get(AllianceRestrictedListVersion, rl_id)
            if not rl_version:
                return (
                    jsonify({"error": "Alliance restricted list version not found"}),
                    400,
                )
            alliance_restricted_list_version_id = rl_id
        else:
            # Default to latest version if any exist
            latest = AllianceRestrictedListVersion.query.order_by(
                AllianceRestrictedListVersion.version.desc()
            ).first()
            if latest:
                alliance_restricted_list_version_id = latest.id

    match = StandaloneMatch(
        uuid=str(uuid_module.uuid4()),
        creator_id=current_user.id,
        opponent_id=None,
        format_type=format_type,
        status=StandaloneMatchStatus.SETUP,
        best_of_n=best_of_n,
        is_public=is_public,
        max_sas=max_sas,
        combined_max_sas=combined_max_sas,
        set_diversity=set_diversity,
        house_diversity=house_diversity,
        decks_per_player=decks_per_player,
        sealed_pools_generated=False,
        allowed_sets=allowed_sets,
        alliance_restricted_list_version_id=alliance_restricted_list_version_id,
    )
    db.session.add(match)
    db.session.commit()
    return jsonify(serialize_standalone_match(match, current_user.id)), 201


@standalone_bp.route("/public", methods=["GET"])
def list_public_matches():
    """List public unjoined matches. Auto-deletes stale matches."""
    _cleanup_old_matches()
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
    matches = (
        StandaloneMatch.query.filter(
            StandaloneMatch.is_public == True,
            StandaloneMatch.opponent_id == None,
            StandaloneMatch.status == StandaloneMatchStatus.SETUP,
            StandaloneMatch.created_at > cutoff,
        )
        .order_by(StandaloneMatch.created_at.desc())
        .all()
    )
    return jsonify([serialize_standalone_match(m) for m in matches])


@standalone_bp.route("/<int:match_id>", methods=["GET"])
def get_match(match_id):
    """Get match state. UUID required unless caller is creator or opponent."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    provided_uuid = request.args.get("uuid", "")
    is_creator = current_user.is_authenticated and current_user.id == match.creator_id
    is_opponent = (
        current_user.is_authenticated
        and match.opponent_id
        and current_user.id == match.opponent_id
    )

    if not is_creator and not is_opponent:
        if provided_uuid != match.uuid:
            return jsonify({"error": "UUID required to view this match"}), 403

    viewer_id = current_user.id if current_user.is_authenticated else None
    return etag_response(serialize_standalone_match(match, viewer_id))


@standalone_bp.route("/<int:match_id>/join", methods=["POST"])
def join_match(match_id):
    """Join a standalone match as opponent. UUID required."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    provided_uuid = data.get("uuid") or request.args.get("uuid", "")
    if provided_uuid != match.uuid:
        return jsonify({"error": "Invalid UUID"}), 403

    if match.status != StandaloneMatchStatus.SETUP:
        return jsonify({"error": "Match is not in setup phase"}), 400
    if match.opponent_id is not None:
        return jsonify({"error": "Match already has an opponent"}), 400

    # Determine who is joining
    user = _current_user_or_guest()
    if user is None:
        return jsonify({"error": "Guest account not available"}), 500

    if user.id == match.creator_id:
        return jsonify({"error": "You cannot join your own match"}), 400

    match.opponent_id = user.id
    match.status = StandaloneMatchStatus.DECK_SELECTION

    # For sealed formats, auto-generate sealed pools (Alliance does not use sealed pools)
    if match.format_type in SEALED_FORMATS:
        errors = generate_sealed_pools_for_standalone(match, match.creator_id, user.id)
        if errors:
            db.session.rollback()
            return jsonify({"error": errors[0]}), 400

    db.session.commit()
    viewer_id = user.id if current_user.is_authenticated else None
    return jsonify(serialize_standalone_match(match, viewer_id))


@standalone_bp.route("/<int:match_id>/sealed-pool", methods=["GET"])
def get_sealed_pool(match_id):
    """Get the current user's sealed pool for this match."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    provided_uuid = request.args.get("uuid", "")
    is_creator = current_user.is_authenticated and current_user.id == match.creator_id
    is_opponent = (
        current_user.is_authenticated
        and match.opponent_id
        and current_user.id == match.opponent_id
    )
    if not is_creator and not is_opponent and provided_uuid != match.uuid:
        return jsonify({"error": "Access denied"}), 403

    user = _current_user_or_guest()
    if user is None:
        return jsonify({"error": "Not authenticated"}), 401

    pool = SealedPoolDeck.query.filter_by(
        standalone_match_id=match.id, user_id=user.id
    ).all()
    return jsonify([serialize_sealed_pool_entry(spd) for spd in pool])


@standalone_bp.route("/<int:match_id>/deck-selection", methods=["POST"])
def submit_deck_selection(match_id):
    """Select a deck for the standalone match."""
    from keytracker.utils import get_deck_by_id_with_zeal

    match, err = _get_match_or_404(match_id)
    if err:
        return err

    provided_uuid = request.args.get("uuid", "")
    is_creator = current_user.is_authenticated and current_user.id == match.creator_id
    is_opponent = (
        current_user.is_authenticated
        and match.opponent_id
        and current_user.id == match.opponent_id
    )
    if not is_creator and not is_opponent and provided_uuid != match.uuid:
        return jsonify({"error": "Access denied"}), 403

    if match.status != StandaloneMatchStatus.DECK_SELECTION:
        return jsonify({"error": "Deck selection is not open"}), 400

    if match.format_type in ALLIANCE_FORMATS:
        return (
            jsonify({"error": "Alliance formats use /alliance-selection endpoint"}),
            400,
        )

    user = _current_user_or_guest()
    if user is None:
        return jsonify({"error": "Not authenticated"}), 401
    if user.id not in (match.creator_id, match.opponent_id):
        return jsonify({"error": "You are not in this match"}), 403

    data = request.get_json(silent=True) or {}
    slot_number = data.get("slot_number", 1)
    _three_slot = (WeekFormat.TRIAD, WeekFormat.TRIAD_SHORT, WeekFormat.MOIRAI)
    _two_slot = (WeekFormat.OUBLIETTE, WeekFormat.ADAPTIVE_SHORT, WeekFormat.EXCHANGE)
    _six_slot = (WeekFormat.NORDIC_HEXAD,)
    max_slots = (
        6
        if match.format_type in _six_slot
        else (
            3
            if match.format_type in _three_slot
            else (2 if match.format_type in _two_slot else 1)
        )
    )
    if not isinstance(slot_number, int) or slot_number < 1 or slot_number > max_slots:
        return jsonify({"error": f"slot_number must be between 1 and {max_slots}"}), 400

    # Resolve deck
    if match.format_type == WeekFormat.SEALED_ARCHON:
        deck_db_id = data.get("deck_id")
        if not deck_db_id:
            return jsonify({"error": "deck_id is required for Sealed Archon"}), 400
        pool_entry = SealedPoolDeck.query.filter_by(
            standalone_match_id=match.id, user_id=user.id, deck_id=deck_db_id
        ).first()
        if not pool_entry:
            return jsonify({"error": "Deck is not in your sealed pool"}), 400
        deck = db.session.get(Deck, deck_db_id)
        if not deck:
            return jsonify({"error": "Deck not found"}), 400
    else:
        deck_url = (data.get("deck_url") or "").strip()
        if not deck_url:
            return jsonify({"error": "deck_url is required"}), 400
        kf_id = _parse_deck_url(deck_url)
        if not kf_id:
            return jsonify({"error": "Could not parse deck ID from URL"}), 400
        try:
            deck = get_deck_by_id_with_zeal(kf_id)
        except Exception as e:
            logger.error("Failed to fetch deck %s: %s", kf_id, e)
            return jsonify({"error": f"Failed to fetch deck: {str(e)}"}), 400

    # Get existing selections for this user
    existing = PlayerDeckSelection.query.filter_by(
        standalone_match_id=match.id, user_id=user.id
    ).all()
    existing_without_slot = [s for s in existing if s.slot_number != slot_number]

    errors = validate_deck_for_standalone(
        match, user.id, deck, slot_number, existing_without_slot
    )
    if errors:
        return jsonify({"error": errors[0]}), 400

    # Upsert
    sel = PlayerDeckSelection.query.filter_by(
        standalone_match_id=match.id, user_id=user.id, slot_number=slot_number
    ).first()
    if sel:
        sel.deck_id = deck.id
    else:
        sel = PlayerDeckSelection(
            standalone_match_id=match.id,
            week_id=None,
            user_id=user.id,
            deck_id=deck.id,
            slot_number=slot_number,
        )
        db.session.add(sel)

    db.session.commit()

    selections = (
        PlayerDeckSelection.query.filter_by(
            standalone_match_id=match.id, user_id=user.id
        )
        .order_by(PlayerDeckSelection.slot_number)
        .all()
    )
    from keytracker.serializers import serialize_deck_selection

    return jsonify([serialize_deck_selection(s) for s in selections])


@standalone_bp.route("/<int:match_id>/deck-selection", methods=["DELETE"])
def remove_deck_selection(match_id):
    """Remove a deck selection."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    if match.status != StandaloneMatchStatus.DECK_SELECTION:
        return jsonify({"error": "Deck selection is not open"}), 400

    user = _current_user_or_guest()
    if user is None or user.id not in (match.creator_id, match.opponent_id):
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json(silent=True) or {}
    slot_number = data.get("slot_number", 1)

    sel = PlayerDeckSelection.query.filter_by(
        standalone_match_id=match.id, user_id=user.id, slot_number=slot_number
    ).first()
    if not sel:
        return jsonify({"error": "Selection not found"}), 404

    db.session.delete(sel)
    db.session.commit()
    return jsonify({"success": True})


@standalone_bp.route("/<int:match_id>/alliance-selection", methods=["POST"])
def submit_alliance_selection(match_id):
    """Submit alliance pod selection (Sealed Alliance or Alliance format)."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    if match.format_type not in ALLIANCE_FORMATS:
        return jsonify({"error": "Only for Alliance formats"}), 400
    if match.status != StandaloneMatchStatus.DECK_SELECTION:
        return jsonify({"error": "Alliance selection is not open"}), 400

    user = _current_user_or_guest()
    if user is None or user.id not in (match.creator_id, match.opponent_id):
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json(silent=True) or {}
    pods = data.get("pods", [])
    token_deck_id = data.get("token_deck_id")
    prophecy_deck_id = data.get("prophecy_deck_id")

    if match.format_type == WeekFormat.ALLIANCE:
        errors = validate_alliance_open(
            match, user.id, pods, token_deck_id, prophecy_deck_id
        )
    else:
        errors = validate_alliance_for_standalone(
            match, user.id, pods, token_deck_id, prophecy_deck_id
        )
    if errors:
        return jsonify({"error": errors[0]}), 400

    from keytracker.schema import TOKEN_EXPANSION_IDS, PROPHECY_EXPANSION_ID

    if match.format_type == WeekFormat.ALLIANCE:
        # For open Alliance, derive token/prophecy needs from actual pod expansions
        from keytracker.schema import Deck as _Deck

        pod_expansions = set()
        for pod in pods:
            d = db.session.get(_Deck, pod.get("deck_id"))
            if d:
                pod_expansions.add(d.expansion)
        needs_token = bool(pod_expansions & TOKEN_EXPANSION_IDS)
        needs_prophecy = PROPHECY_EXPANSION_ID in pod_expansions
    else:
        allowed_sets = set(match.allowed_sets) if match.allowed_sets else set()
        needs_token = bool(allowed_sets & TOKEN_EXPANSION_IDS)
        needs_prophecy = PROPHECY_EXPANSION_ID in allowed_sets

    # Replace existing selections
    AlliancePodSelection.query.filter_by(
        standalone_match_id=match.id, user_id=user.id
    ).delete()

    for i, pod in enumerate(pods):
        sel = AlliancePodSelection(
            standalone_match_id=match.id,
            week_id=None,
            user_id=user.id,
            deck_id=pod["deck_id"],
            house_name=pod["house"],
            slot_type="pod",
            slot_number=i + 1,
        )
        db.session.add(sel)

    if needs_token and token_deck_id:
        sel = AlliancePodSelection(
            standalone_match_id=match.id,
            week_id=None,
            user_id=user.id,
            deck_id=token_deck_id,
            house_name=None,
            slot_type="token",
            slot_number=1,
        )
        db.session.add(sel)

    if needs_prophecy and prophecy_deck_id:
        sel = AlliancePodSelection(
            standalone_match_id=match.id,
            week_id=None,
            user_id=user.id,
            deck_id=prophecy_deck_id,
            house_name=None,
            slot_type="prophecy",
            slot_number=1,
        )
        db.session.add(sel)

    db.session.commit()
    selections = AlliancePodSelection.query.filter_by(
        standalone_match_id=match.id, user_id=user.id
    ).all()
    return jsonify([serialize_alliance_selection(s) for s in selections])


@standalone_bp.route("/<int:match_id>/alliance-selection", methods=["DELETE"])
def clear_alliance_selection(match_id):
    """Clear alliance pod selection."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    if match.format_type not in ALLIANCE_FORMATS:
        return jsonify({"error": "Only for Alliance formats"}), 400

    user = _current_user_or_guest()
    if user is None or user.id not in (match.creator_id, match.opponent_id):
        return jsonify({"error": "Access denied"}), 403

    AlliancePodSelection.query.filter_by(
        standalone_match_id=match.id, user_id=user.id
    ).delete()
    db.session.commit()
    return "", 204


@standalone_bp.route("/<int:match_id>/start", methods=["POST"])
def start_match(match_id):
    """Confirm deck selection is done. When both players start, advances to PUBLISHED."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    if match.status != StandaloneMatchStatus.DECK_SELECTION:
        return jsonify({"error": "Match is not in deck selection phase"}), 400

    user = _current_user_or_guest()
    if user is None or user.id not in (match.creator_id, match.opponent_id):
        return jsonify({"error": "You are not in this match"}), 403

    # Get or create PlayerMatchup
    if not match.matchup:
        pm = PlayerMatchup(
            standalone_match_id=match.id,
            week_matchup_id=None,
            player1_id=match.creator_id,
            player2_id=match.opponent_id,
        )
        db.session.add(pm)
        db.session.flush()
        db.session.refresh(match)

    pm = match.matchup

    if user.id == match.creator_id:
        pm.player1_started = True
    else:
        pm.player2_started = True

    # Check if both started
    if pm.player1_started and pm.player2_started:
        match.status = StandaloneMatchStatus.PUBLISHED
        if match.format_type == WeekFormat.NORDIC_HEXAD:
            pm.nordic_hexad_phase = 1

    db.session.commit()
    viewer_id = user.id if current_user.is_authenticated else None
    return jsonify(serialize_standalone_match(match, viewer_id))


@standalone_bp.route("/<int:match_id>/strike", methods=["POST"])
def submit_strike(match_id):
    """Submit a Triad strike. Only valid in PUBLISHED status after both started."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    if match.format_type not in (WeekFormat.TRIAD, WeekFormat.TRIAD_SHORT):
        return jsonify({"error": "Strikes are only for Triad/Triad Short format"}), 400
    if match.status != StandaloneMatchStatus.PUBLISHED:
        return jsonify({"error": "Match is not published"}), 400
    if not match.matchup:
        return jsonify({"error": "Match not started yet"}), 400

    user = _current_user_or_guest()
    if user is None or user.id not in (match.creator_id, match.opponent_id):
        return jsonify({"error": "You are not in this match"}), 403

    data = request.get_json(silent=True) or {}
    struck_selection_id = data.get("struck_deck_selection_id")
    if not struck_selection_id:
        return jsonify({"error": "struck_deck_selection_id is required"}), 400

    pm = match.matchup
    error = validate_strike_standalone(pm, user.id, struck_selection_id)
    if error:
        return jsonify({"error": error}), 400

    strike = StrikeSelection(
        player_matchup_id=pm.id,
        striking_user_id=user.id,
        struck_deck_selection_id=struck_selection_id,
    )
    db.session.add(strike)
    db.session.commit()

    return jsonify(
        serialize_standalone_match(
            match, user.id if current_user.is_authenticated else None
        )
    )


@standalone_bp.route("/<int:match_id>/triad-short-pick", methods=["POST"])
def submit_triad_short_pick(match_id):
    """Submit a Triad Short pick. Valid after both players have struck."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    if match.format_type != WeekFormat.TRIAD_SHORT:
        return jsonify({"error": "Only for Triad Short format"}), 400
    if match.status != StandaloneMatchStatus.PUBLISHED:
        return jsonify({"error": "Match is not published"}), 400
    if not match.matchup:
        return jsonify({"error": "Match not started yet"}), 400

    user = _current_user_or_guest()
    if user is None or user.id not in (match.creator_id, match.opponent_id):
        return jsonify({"error": "You are not in this match"}), 403

    data = request.get_json(silent=True) or {}
    picked_selection_id = data.get("picked_deck_selection_id")
    if not picked_selection_id:
        return jsonify({"error": "picked_deck_selection_id is required"}), 400

    pm = match.matchup
    error = validate_triad_short_pick(pm, user.id, picked_selection_id)
    if error:
        return jsonify({"error": error}), 400

    pick = TriadShortPick(
        player_matchup_id=pm.id,
        picking_user_id=user.id,
        picked_deck_selection_id=picked_selection_id,
    )
    db.session.add(pick)
    db.session.commit()

    viewer_id = user.id if current_user.is_authenticated else None
    return jsonify(serialize_standalone_match(match, viewer_id))


@standalone_bp.route("/<int:match_id>/banned-house", methods=["POST"])
def submit_banned_house(match_id):
    """Submit an Oubliette banned house. Valid after both players have submitted decks."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    if match.format_type != WeekFormat.OUBLIETTE:
        return jsonify({"error": "Only for Oubliette format"}), 400
    if match.status != StandaloneMatchStatus.PUBLISHED:
        return jsonify({"error": "Match is not published"}), 400
    if not match.matchup:
        return jsonify({"error": "Match not started yet"}), 400

    user = _current_user_or_guest()
    if user is None or user.id not in (match.creator_id, match.opponent_id):
        return jsonify({"error": "You are not in this match"}), 403

    data = request.get_json(silent=True) or {}
    banned_house = (data.get("banned_house") or "").strip()
    if not banned_house:
        return jsonify({"error": "banned_house is required"}), 400

    pm = match.matchup
    is_p1 = user.id == pm.player1_id
    user_sels = PlayerDeckSelection.query.filter_by(
        standalone_match_id=match.id, user_id=user.id
    ).all()

    error = validate_oubliette_ban(pm, user.id, banned_house, user_sels)
    if error:
        return jsonify({"error": error}), 400

    if is_p1:
        pm.oubliette_p1_banned_house = banned_house
    else:
        pm.oubliette_p2_banned_house = banned_house

    db.session.flush()

    # After both bans: check for forfeits
    if pm.oubliette_p1_banned_house and pm.oubliette_p2_banned_house:
        p1_sels = PlayerDeckSelection.query.filter_by(
            standalone_match_id=match.id, user_id=pm.player1_id
        ).all()
        p2_sels = PlayerDeckSelection.query.filter_by(
            standalone_match_id=match.id, user_id=pm.player2_id
        ).all()
        eligible = get_oubliette_eligible_deck_ids(pm, p1_sels, p2_sels)
        if eligible:
            forfeit_winner_id = None
            if not eligible["p1"] and not eligible["p2"]:
                # Both forfeit — no clear winner; skip auto-resolution
                pass
            elif not eligible["p1"]:
                forfeit_winner_id = pm.player2_id
            elif not eligible["p2"]:
                forfeit_winner_id = pm.player1_id

            if forfeit_winner_id:
                from keytracker.schema import MatchGame

                forfeit_game = MatchGame(
                    player_matchup_id=pm.id,
                    game_number=1,
                    winner_id=forfeit_winner_id,
                    player1_keys=0,
                    player2_keys=0,
                    went_to_time=False,
                    loser_conceded=True,
                )
                db.session.add(forfeit_game)
                match.status = StandaloneMatchStatus.COMPLETED

    db.session.commit()
    viewer_id = user.id if current_user.is_authenticated else None
    return jsonify(serialize_standalone_match(match, viewer_id))


@standalone_bp.route("/<int:match_id>/adaptive-short-choice", methods=["POST"])
def submit_adaptive_short_choice(match_id):
    """Submit an Adaptive Short deck choice. Hidden until both players submit."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    if match.format_type not in (WeekFormat.ADAPTIVE_SHORT, WeekFormat.MOIRAI):
        return jsonify({"error": "Only for Adaptive Short or Moirai format"}), 400
    if match.status != StandaloneMatchStatus.PUBLISHED:
        return jsonify({"error": "Match is not published"}), 400
    if not match.matchup:
        return jsonify({"error": "Match not started yet"}), 400

    user = _current_user_or_guest()
    if user is None or user.id not in (match.creator_id, match.opponent_id):
        return jsonify({"error": "You are not in this match"}), 403

    data = request.get_json(silent=True) or {}
    chosen_sel_id = data.get("chosen_deck_selection_id")
    if not chosen_sel_id:
        return jsonify({"error": "chosen_deck_selection_id is required"}), 400

    pm = match.matchup
    if match.format_type == WeekFormat.MOIRAI:
        error = validate_moirai_adaptive_choice(pm, user.id, chosen_sel_id)
    else:
        error = validate_adaptive_short_choice(pm, user.id, chosen_sel_id)
    if error:
        return jsonify({"error": error}), 400

    choice = AdaptiveShortChoice(
        player_matchup_id=pm.id,
        choosing_user_id=user.id,
        chosen_deck_selection_id=chosen_sel_id,
    )
    db.session.add(choice)
    db.session.flush()
    db.session.expire(pm, ["adaptive_short_choices"])

    # After both choices: check if same deck was chosen
    choices = pm.adaptive_short_choices
    if len(choices) == 2:
        c1, c2 = choices[0], choices[1]
        if c1.chosen_deck_selection_id == c2.chosen_deck_selection_id:
            init_adaptive_short_bidding(pm, c1.chosen_deck_selection_id)

    db.session.commit()
    viewer_id = user.id if current_user.is_authenticated else None
    return jsonify(serialize_standalone_match(match, viewer_id))


@standalone_bp.route("/<int:match_id>/adaptive-short-bid", methods=["POST"])
def submit_adaptive_short_bid(match_id):
    """Submit an Adaptive Short bid or concede."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    if match.format_type not in (WeekFormat.ADAPTIVE_SHORT, WeekFormat.MOIRAI):
        return jsonify({"error": "Only for Adaptive Short or Moirai format"}), 400
    if match.status != StandaloneMatchStatus.PUBLISHED:
        return jsonify({"error": "Match is not published"}), 400
    if not match.matchup:
        return jsonify({"error": "Match not started yet"}), 400

    user = _current_user_or_guest()
    if user is None or user.id not in (match.creator_id, match.opponent_id):
        return jsonify({"error": "You are not in this match"}), 403

    data = request.get_json(silent=True) or {}
    chains = data.get("chains")
    concede = bool(data.get("concede", False))

    pm = match.matchup
    success, error = validate_adaptive_short_bid(
        pm, user.id, chains=chains, concede=concede
    )
    if not success:
        return jsonify({"error": error}), 400

    db.session.commit()
    viewer_id = user.id if current_user.is_authenticated else None
    return jsonify(serialize_standalone_match(match, viewer_id))


@standalone_bp.route("/<int:match_id>/exchange-borrow", methods=["POST"])
def submit_exchange_borrow(match_id):
    """Submit an Exchange borrow — secretly choose one of the opponent's decks to borrow."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    if match.format_type != WeekFormat.EXCHANGE:
        return jsonify({"error": "Only for Exchange format"}), 400
    if match.status != StandaloneMatchStatus.PUBLISHED:
        return jsonify({"error": "Match is not published"}), 400
    if not match.matchup:
        return jsonify({"error": "Match not started yet"}), 400

    user = _current_user_or_guest()
    if user is None or user.id not in (match.creator_id, match.opponent_id):
        return jsonify({"error": "You are not in this match"}), 403

    data = request.get_json(silent=True) or {}
    borrowed_deck_selection_id = data.get("borrowed_deck_selection_id")
    if not isinstance(borrowed_deck_selection_id, int):
        return jsonify({"error": "borrowed_deck_selection_id is required"}), 400

    pm = match.matchup
    error = validate_exchange_borrow(pm, user.id, borrowed_deck_selection_id)
    if error:
        return jsonify({"error": error}), 400

    borrow = ExchangeBorrow(
        player_matchup_id=pm.id,
        borrowing_user_id=user.id,
        borrowed_deck_selection_id=borrowed_deck_selection_id,
    )
    db.session.add(borrow)
    db.session.commit()
    viewer_id = user.id if current_user.is_authenticated else None
    return jsonify(serialize_standalone_match(match, viewer_id))


@standalone_bp.route("/<int:match_id>/nordic-action", methods=["POST"])
def submit_nordic_action(match_id):
    """Submit a Nordic Hexad ban or protect action."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    if match.format_type != WeekFormat.NORDIC_HEXAD:
        return jsonify({"error": "Only for Nordic Hexad format"}), 400
    if match.status != StandaloneMatchStatus.PUBLISHED:
        return jsonify({"error": "Match is not published"}), 400
    if not match.matchup:
        return jsonify({"error": "Match not started yet"}), 400

    user = _current_user_or_guest()
    if user is None or user.id not in (match.creator_id, match.opponent_id):
        return jsonify({"error": "You are not in this match"}), 403

    data = request.get_json(silent=True) or {}
    phase = data.get("phase")
    target_deck_selection_id = data.get("target_deck_selection_id")
    if not isinstance(phase, int) or not isinstance(target_deck_selection_id, int):
        return (
            jsonify({"error": "phase and target_deck_selection_id are required"}),
            400,
        )

    pm = match.matchup
    error = validate_nordic_action(pm, user.id, phase, target_deck_selection_id)
    if error:
        return jsonify({"error": error}), 400

    action = NordicHexadAction(
        player_matchup_id=pm.id,
        player_id=user.id,
        phase=phase,
        target_deck_selection_id=target_deck_selection_id,
    )
    db.session.add(action)
    db.session.flush()
    advance_nordic_phase(pm)
    db.session.commit()
    viewer_id = user.id if current_user.is_authenticated else None
    return jsonify(serialize_standalone_match(match, viewer_id))


@standalone_bp.route("/<int:match_id>/moirai-assignments", methods=["POST"])
def submit_moirai_assignments(match_id):
    """Submit Moirai game-slot assignments (all 3 of the opponent's decks at once)."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    if match.format_type != WeekFormat.MOIRAI:
        return jsonify({"error": "Only for Moirai format"}), 400
    if match.status != StandaloneMatchStatus.PUBLISHED:
        return jsonify({"error": "Match is not published"}), 400
    if not match.matchup:
        return jsonify({"error": "Match not started yet"}), 400

    user = _current_user_or_guest()
    if user is None or user.id not in (match.creator_id, match.opponent_id):
        return jsonify({"error": "You are not in this match"}), 403

    data = request.get_json(silent=True) or {}
    assignments = data.get("assignments")
    if not isinstance(assignments, list):
        return jsonify({"error": "assignments must be a list"}), 400

    pm = match.matchup
    new_assignments, error = validate_moirai_assignments(pm, user.id, assignments)
    if error:
        return jsonify({"error": error}), 400

    for a in new_assignments:
        db.session.add(a)

    db.session.commit()
    viewer_id = user.id if current_user.is_authenticated else None
    return jsonify(serialize_standalone_match(match, viewer_id))


@standalone_bp.route("/<int:match_id>/adaptive-bid", methods=["POST"])
def submit_adaptive_bid(match_id):
    """Submit an adaptive bid or concede. Valid after a 1-1 tie in an Adaptive match."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    if match.format_type != WeekFormat.ADAPTIVE:
        return jsonify({"error": "Only for Adaptive format"}), 400
    if match.status != StandaloneMatchStatus.PUBLISHED:
        return jsonify({"error": "Match is not published"}), 400
    if not match.matchup:
        return jsonify({"error": "Match not started yet"}), 400

    user = _current_user_or_guest()
    if user is None or user.id not in (match.creator_id, match.opponent_id):
        return jsonify({"error": "You are not in this match"}), 403

    data = request.get_json(silent=True) or {}
    chains = data.get("chains")
    concede = bool(data.get("concede", False))

    pm = match.matchup
    success, error = validate_adaptive_bid(pm, user.id, chains=chains, concede=concede)
    if not success:
        return jsonify({"error": error}), 400

    db.session.commit()
    viewer_id = user.id if current_user.is_authenticated else None
    return jsonify(serialize_standalone_match(match, viewer_id))


@standalone_bp.route("/<int:match_id>/games", methods=["POST"])
def report_game(match_id):
    """Report a game result."""
    match, err = _get_match_or_404(match_id)
    if err:
        return err

    if match.status != StandaloneMatchStatus.PUBLISHED:
        return jsonify({"error": "Match is not in published status"}), 400
    if not match.matchup:
        return jsonify({"error": "Match not started yet"}), 400

    pm = match.matchup
    if not pm.player1_started or not pm.player2_started:
        return jsonify({"error": "Both players must start before reporting games"}), 400

    user = _current_user_or_guest()
    if user is None or user.id not in (match.creator_id, match.opponent_id):
        return jsonify({"error": "You are not in this match"}), 403

    data = request.get_json(silent=True) or {}
    game, error = validate_and_record_game(
        pm, user.id, data, match.best_of_n, match.format_type
    )
    if error:
        db.session.rollback()
        return jsonify({"error": error}), 400

    # Optionally attach an uploaded game log
    log_text = data.get("log", "").strip()
    if log_text:
        from keytracker.match_helpers import attach_log_to_match_game

        _, log_err = attach_log_to_match_game(log_text, game)
        if log_err:
            logger.warning(
                "Failed to parse game log for match_game %s: %s", game.id, log_err
            )

    # Check if match is now complete
    db.session.expire(pm, ["games"])
    if match.format_type == WeekFormat.EXCHANGE:
        _p1_sels, _p2_sels = _get_exchange_selections(pm)
        if check_exchange_win_condition(pm, _p1_sels, _p2_sels):
            match.status = StandaloneMatchStatus.COMPLETED
    else:
        wins_needed = math.ceil(match.best_of_n / 2)
        all_games = sorted(pm.games, key=lambda g: g.game_number)
        p1_total = sum(1 for g in all_games if g.winner_id == pm.player1_id)
        p2_total = sum(1 for g in all_games if g.winner_id == pm.player2_id)
        if p1_total >= wins_needed or p2_total >= wins_needed:
            match.status = StandaloneMatchStatus.COMPLETED

    db.session.commit()
    return jsonify(serialize_match_game(game)), 201
