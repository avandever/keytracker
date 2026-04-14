"""
Auction routes.

Players pool their decks and bid on each other using chains as currency.
Each player brings one deck; the winner of each bid receives that deck to play,
at the cost of the chains they bid.
"""

import random
from datetime import datetime

from xkcdpass import xkcd_password as xp

from flask import Blueprint, jsonify, request
from flask_login import current_user
from keytracker.response_helpers import etag_response
from sqlalchemy.orm import joinedload

from keytracker.routes.auth import member_required
from keytracker.schema import (
    Auction,
    AuctionBid,
    AuctionDeck,
    AuctionParticipant,
    AuctionStatus,
    db,
)
from keytracker.serializers import serialize_auction_detail
from keytracker.utils import get_deck_by_id_with_zeal

auction_bp = Blueprint("auction_bp", __name__, url_prefix="/api/v2/auctions")


def _parse_deck_url(url_str: str):
    """Extract kf_id from a deck URL or raw UUID."""
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


def _load_auction(auction_id):
    return (
        db.session.query(Auction)
        .options(
            joinedload(Auction.participants).joinedload(AuctionParticipant.user),
            joinedload(Auction.decks).joinedload(AuctionDeck.deck),
            joinedload(Auction.decks)
            .joinedload(AuctionDeck.bids)
            .joinedload(AuctionBid.user),
            joinedload(Auction.active_deck),
        )
        .filter(Auction.id == auction_id)
        .first()
    )


def _get_current_picker(auction):
    assigned_ids = {d.assigned_to_user_id for d in auction.decks if d.assigned_to_user_id}
    order = auction.player_order or [p.user_id for p in auction.participants]
    for uid in order:
        if uid not in assigned_ids:
            return uid
    return None


def _get_current_bidder(auction):
    if not auction.active_deck_id:
        return None
    picker_id = _get_current_picker(auction)
    active_deck = next((d for d in auction.decks if d.id == auction.active_deck_id), None)
    if not active_deck:
        return None
    bid_user_ids = {b.user_id for b in active_deck.bids}
    order = auction.player_order or [p.user_id for p in auction.participants]
    for uid in order:
        if uid == picker_id:
            continue
        if uid not in bid_user_ids:
            return uid
    return None


def _bidding_complete(auction):
    if not auction.active_deck_id:
        return False
    active_deck = next((d for d in auction.decks if d.id == auction.active_deck_id), None)
    if not active_deck:
        return False
    bids = active_deck.bids
    # Max bid reached
    if any(b.chains is not None and b.chains >= 24 for b in bids):
        return True
    # All non-pickers have bid (pass or chains)
    picker_id = _get_current_picker(auction)
    non_pickers = [p.user_id for p in auction.participants if p.user_id != picker_id]
    bid_user_ids = {b.user_id for b in bids}
    return all(uid in bid_user_ids for uid in non_pickers)


def _assign_active_deck(auction):
    active_deck = next((d for d in auction.decks if d.id == auction.active_deck_id), None)
    if not active_deck:
        return
    bids = [b for b in active_deck.bids if b.chains is not None]
    picker_id = _get_current_picker(auction)
    if bids:
        winner_bid = max(bids, key=lambda b: b.chains)
        active_deck.assigned_to_user_id = winner_bid.user_id
        active_deck.chains_bid = winner_bid.chains
    else:
        # All passed — picker gets it at 0 chains
        active_deck.assigned_to_user_id = picker_id
        active_deck.chains_bid = 0
    auction.active_deck_id = None


def _try_auto_complete(auction):
    """Check if auction is done; auto-assign last deck if only 1 player left to pick."""
    unassigned = [
        d for d in auction.decks if d.assigned_to_user_id is None and d.deck_id is not None
    ]
    if len(unassigned) == 0:
        auction.status = AuctionStatus.COMPLETED
        return True
    if len(unassigned) == 1:
        assigned_ids = {d.assigned_to_user_id for d in auction.decks if d.assigned_to_user_id}
        order = auction.player_order or [p.user_id for p in auction.participants]
        remaining_pickers = [uid for uid in order if uid not in assigned_ids]
        if len(remaining_pickers) == 1:
            unassigned[0].assigned_to_user_id = remaining_pickers[0]
            unassigned[0].chains_bid = 0
            auction.active_deck_id = None
            auction.status = AuctionStatus.COMPLETED
            return True
    return False


@auction_bp.route("/", methods=["POST"])
@member_required
def create_auction():
    """Create a new auction. Creator auto-joins."""
    wordfile = xp.locate_wordfile()
    words = xp.generate_wordlist(wordfile=wordfile, min_length=4, max_length=8)
    passphrase = xp.generate_xkcdpassword(words, numwords=3, delimiter="-")
    auction = Auction(
        creator_id=current_user.id,
        passphrase=passphrase,
        status=AuctionStatus.SETUP,
    )
    db.session.add(auction)
    db.session.flush()
    participant = AuctionParticipant(auction_id=auction.id, user_id=current_user.id)
    db.session.add(participant)
    auction_deck = AuctionDeck(
        auction_id=auction.id, brought_by_user_id=current_user.id
    )
    db.session.add(auction_deck)
    db.session.commit()
    auction = _load_auction(auction.id)
    return jsonify(serialize_auction_detail(auction, viewer_id=current_user.id)), 201


@auction_bp.route("/", methods=["GET"])
@member_required
def list_auctions():
    """List all auctions the current user participates in."""
    rows = (
        db.session.query(Auction)
        .join(AuctionParticipant, AuctionParticipant.auction_id == Auction.id)
        .filter(AuctionParticipant.user_id == current_user.id)
        .options(joinedload(Auction.participants))
        .order_by(Auction.created_at.desc())
        .all()
    )
    result = []
    for a in rows:
        result.append(
            {
                "id": a.id,
                "status": a.status.value,
                "creator_id": a.creator_id,
                "player_count": len(a.participants),
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
        )
    return jsonify(result)


@auction_bp.route("/<int:auction_id>", methods=["GET"])
def get_auction(auction_id):
    """Get auction detail. Public endpoint; passphrase only returned to creator."""
    auction = _load_auction(auction_id)
    if not auction:
        return jsonify({"error": "Not found"}), 404
    viewer_id = current_user.id if current_user.is_authenticated else None
    return etag_response(serialize_auction_detail(auction, viewer_id=viewer_id))


@auction_bp.route("/<int:auction_id>/join", methods=["POST"])
@member_required
def join_auction(auction_id):
    """Join an existing auction using its passphrase."""
    data = request.get_json() or {}
    passphrase = data.get("passphrase", "")
    auction = _load_auction(auction_id)
    if not auction:
        return jsonify({"error": "Not found"}), 404
    if auction.status != AuctionStatus.SETUP:
        return jsonify({"error": "Auction is not in setup phase"}), 400
    if auction.passphrase != passphrase:
        return jsonify({"error": "Invalid passphrase"}), 403
    existing = next(
        (p for p in auction.participants if p.user_id == current_user.id), None
    )
    if existing:
        return jsonify(serialize_auction_detail(auction, viewer_id=current_user.id))
    participant = AuctionParticipant(auction_id=auction_id, user_id=current_user.id)
    db.session.add(participant)
    auction_deck = AuctionDeck(
        auction_id=auction_id, brought_by_user_id=current_user.id
    )
    db.session.add(auction_deck)
    db.session.commit()
    auction = _load_auction(auction_id)
    return jsonify(serialize_auction_detail(auction, viewer_id=current_user.id))


@auction_bp.route("/<int:auction_id>/start", methods=["POST"])
@member_required
def start_auction(auction_id):
    """Advance auction from setup to deck_submission. Creator only."""
    auction = _load_auction(auction_id)
    if not auction:
        return jsonify({"error": "Not found"}), 404
    if auction.creator_id != current_user.id:
        return jsonify({"error": "Only the creator can start"}), 403
    if auction.status != AuctionStatus.SETUP:
        return jsonify({"error": "Auction is not in setup phase"}), 400
    if len(auction.participants) < 2:
        return jsonify({"error": "Need at least 2 players"}), 400
    auction.status = AuctionStatus.DECK_SUBMISSION
    db.session.commit()
    auction = _load_auction(auction_id)
    return jsonify(serialize_auction_detail(auction, viewer_id=current_user.id))


@auction_bp.route("/<int:auction_id>/deck", methods=["POST"])
@member_required
def submit_deck(auction_id):
    """Submit a deck for the auction. Advances to auction phase when all decks submitted."""
    auction = _load_auction(auction_id)
    if not auction:
        return jsonify({"error": "Not found"}), 404
    if auction.status != AuctionStatus.DECK_SUBMISSION:
        return jsonify({"error": "Auction is not in deck submission phase"}), 400
    participant = next(
        (p for p in auction.participants if p.user_id == current_user.id), None
    )
    if not participant:
        return jsonify({"error": "You are not in this auction"}), 403
    my_deck_slot = next(
        (d for d in auction.decks if d.brought_by_user_id == current_user.id), None
    )
    if not my_deck_slot:
        return jsonify({"error": "No deck slot found"}), 500
    if my_deck_slot.deck_id is not None:
        return jsonify({"error": "You have already submitted a deck"}), 400

    data = request.get_json() or {}
    deck_url = data.get("deck_url")
    deck_id_str = data.get("deck_id")

    deck = None
    if deck_url:
        kf_id = _parse_deck_url(deck_url)
        if not kf_id:
            return jsonify({"error": "Invalid deck URL"}), 400
        deck = get_deck_by_id_with_zeal(kf_id)
    elif deck_id_str:
        deck = get_deck_by_id_with_zeal(str(deck_id_str))
    else:
        return jsonify({"error": "deck_url or deck_id required"}), 400

    if not deck:
        return jsonify({"error": "Deck not found"}), 404

    my_deck_slot.deck_id = deck.id
    db.session.flush()

    # Check if all players have submitted
    all_decks = db.session.query(AuctionDeck).filter_by(auction_id=auction_id).all()
    submitted = [d for d in all_decks if d.deck_id is not None]
    if len(submitted) == len(auction.participants):
        order = [p.user_id for p in auction.participants]
        random.shuffle(order)
        auction.player_order = order
        auction.status = AuctionStatus.AUCTION

    db.session.commit()
    auction = _load_auction(auction_id)
    return jsonify(serialize_auction_detail(auction, viewer_id=current_user.id))


@auction_bp.route("/<int:auction_id>/pick", methods=["POST"])
@member_required
def pick_deck(auction_id):
    """Current picker selects a deck to put up for bid."""
    auction = _load_auction(auction_id)
    if not auction:
        return jsonify({"error": "Not found"}), 404
    if auction.status != AuctionStatus.AUCTION:
        return jsonify({"error": "Auction is not in auction phase"}), 400
    if auction.active_deck_id is not None:
        return jsonify({"error": "There is already an active deck being bid on"}), 400
    picker_id = _get_current_picker(auction)
    if current_user.id != picker_id:
        return jsonify({"error": "It is not your turn to pick"}), 403

    data = request.get_json() or {}
    auction_deck_id = data.get("auction_deck_id")
    if not auction_deck_id:
        return jsonify({"error": "auction_deck_id required"}), 400

    target_deck = next((d for d in auction.decks if d.id == auction_deck_id), None)
    if not target_deck:
        return jsonify({"error": "Deck not found in this auction"}), 404
    if target_deck.assigned_to_user_id is not None:
        return jsonify({"error": "Deck is already assigned"}), 400

    auction.active_deck_id = auction_deck_id
    db.session.commit()

    # Handle edge case: only 1 participant (picker is the only one; auto-assign)
    auction = _load_auction(auction_id)
    non_pickers = [p for p in auction.participants if p.user_id != picker_id]
    if len(non_pickers) == 0:
        _assign_active_deck(auction)
        _try_auto_complete(auction)
        db.session.commit()
        auction = _load_auction(auction_id)

    return jsonify(serialize_auction_detail(auction, viewer_id=current_user.id))


@auction_bp.route("/<int:auction_id>/bid", methods=["POST"])
@member_required
def place_bid(auction_id):
    """Place a chains bid on the active deck."""
    auction = _load_auction(auction_id)
    if not auction:
        return jsonify({"error": "Not found"}), 404
    if auction.status != AuctionStatus.AUCTION:
        return jsonify({"error": "Auction is not in auction phase"}), 400
    if not auction.active_deck_id:
        return jsonify({"error": "No active deck to bid on"}), 400

    current_bidder = _get_current_bidder(auction)
    if current_user.id != current_bidder:
        return jsonify({"error": "It is not your turn to bid"}), 403

    data = request.get_json() or {}
    chains = data.get("chains")
    if chains is None:
        return jsonify({"error": "chains required"}), 400
    try:
        chains = int(chains)
    except (ValueError, TypeError):
        return jsonify({"error": "chains must be an integer"}), 400
    if chains < 1 or chains > 24:
        return jsonify({"error": "chains must be between 1 and 24"}), 400

    active_deck = next((d for d in auction.decks if d.id == auction.active_deck_id), None)
    current_high = max(
        (b.chains for b in active_deck.bids if b.chains is not None), default=0
    )
    if chains <= current_high:
        return jsonify({"error": f"Must bid more than current high of {current_high}"}), 400

    existing_bid = next(
        (b for b in active_deck.bids if b.user_id == current_user.id), None
    )
    if existing_bid:
        existing_bid.chains = chains
        existing_bid.created_at = datetime.utcnow()
    else:
        bid = AuctionBid(
            auction_deck_id=auction.active_deck_id,
            user_id=current_user.id,
            chains=chains,
        )
        db.session.add(bid)
    db.session.flush()

    auction = _load_auction(auction_id)
    if _bidding_complete(auction):
        _assign_active_deck(auction)
        _try_auto_complete(auction)

    db.session.commit()
    auction = _load_auction(auction_id)
    return jsonify(serialize_auction_detail(auction, viewer_id=current_user.id))


@auction_bp.route("/<int:auction_id>/pass", methods=["POST"])
@member_required
def pass_bid(auction_id):
    """Pass on the current active deck bid."""
    auction = _load_auction(auction_id)
    if not auction:
        return jsonify({"error": "Not found"}), 404
    if auction.status != AuctionStatus.AUCTION:
        return jsonify({"error": "Auction is not in auction phase"}), 400
    if not auction.active_deck_id:
        return jsonify({"error": "No active deck to bid on"}), 400

    current_bidder = _get_current_bidder(auction)
    if current_user.id != current_bidder:
        return jsonify({"error": "It is not your turn to bid"}), 403

    active_deck = next((d for d in auction.decks if d.id == auction.active_deck_id), None)
    existing_bid = next(
        (b for b in active_deck.bids if b.user_id == current_user.id), None
    )
    if existing_bid:
        existing_bid.chains = None
        existing_bid.created_at = datetime.utcnow()
    else:
        bid = AuctionBid(
            auction_deck_id=auction.active_deck_id,
            user_id=current_user.id,
            chains=None,
        )
        db.session.add(bid)
    db.session.flush()

    auction = _load_auction(auction_id)
    if _bidding_complete(auction):
        _assign_active_deck(auction)
        _try_auto_complete(auction)

    db.session.commit()
    auction = _load_auction(auction_id)
    return jsonify(serialize_auction_detail(auction, viewer_id=current_user.id))
