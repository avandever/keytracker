"""
Shared business logic for match validation and game reporting.
Used by both leagues.py (league week matches) and standalone.py (one-off matches).

Supported formats: archon_standard, triad, sealed_archon, sealed_alliance.
NOT supported for standalone matches: thief (team-based mechanics).

When adding new format logic to leagues.py, extract it here.
When adding a new format, also update standalone.py.
See keytracker/routes/FORMATS.md for full details.
"""

import json
import logging
import math
import random

from keytracker.schema import (
    db,
    Deck,
    CardInDeck,
    PlatonicCard,
    MatchGame,
    PlayerDeckSelection,
    SealedPoolDeck,
    AlliancePodSelection,
    AllianceRestrictedListVersion,
    AllianceRestrictedEntry,
    PodStats,
    WeekFormat,
    TOKEN_EXPANSION_IDS,
    PROPHECY_EXPANSION_ID,
)
from sqlalchemy import or_

logger = logging.getLogger(__name__)

KEYCHEAT_PHRASES = ["Forge a key", "Take another turn after this one"]


def deck_has_keycheat(deck_id: int) -> bool:
    """Return True if the deck contains any card with keycheat text."""
    result = (
        db.session.query(CardInDeck)
        .join(PlatonicCard, CardInDeck.platonic_card_id == PlatonicCard.id)
        .filter(
            CardInDeck.deck_id == deck_id,
            or_(
                *[
                    PlatonicCard.card_text.ilike(f"%{phrase}%")
                    for phrase in KEYCHEAT_PHRASES
                ]
            ),
        )
        .first()
    )
    return result is not None


def validate_deck_for_standalone(
    match, user_id, deck, slot_number, existing_selections
):
    """
    Validate a deck submission for a standalone match context.

    match: StandaloneMatch instance (has format_type, max_sas, combined_max_sas,
           set_diversity, house_diversity, allowed_sets, best_of_n)
    user_id: int
    deck: Deck instance
    slot_number: int
    existing_selections: list of PlayerDeckSelection for this user+match (before adding new)

    Returns list of error strings (empty = valid).
    """
    errors = []

    # Validate allowed sets
    if match.allowed_sets:
        allowed = match.allowed_sets
        if deck.expansion not in allowed:
            from keytracker.schema import KeyforgeSet

            kf_set = db.session.get(KeyforgeSet, deck.expansion)
            set_name = kf_set.name if kf_set else str(deck.expansion)
            errors.append(f"Decks from {set_name} are not allowed in this match")
            return errors  # Stop early

    # Validate no_keycheat
    if getattr(match, "no_keycheat", False):
        if deck_has_keycheat(deck.id):
            errors.append("Deck contains a keycheat card (prohibited in this match)")
            return errors

    # Validate max SAS
    if match.max_sas is not None:
        sas = deck.sas_rating
        if sas and sas > match.max_sas:
            errors.append(f"Deck SAS ({sas}) exceeds max SAS ({match.max_sas})")
            return errors

    # For Triad: multi-deck validation (combined SAS, set/house diversity)
    if match.format_type == WeekFormat.TRIAD:
        # Build what the full selection would look like
        all_selections_with_new = list(existing_selections)
        # We do not add the new deck here — caller must flush first and re-query,
        # or pass in a virtual list. For simplicity, we validate after the fact.
        # The caller should call this before flushing, passing existing + new.
        all_decks = [db.session.get(Deck, s.deck_id) for s in all_selections_with_new]
        all_decks = [d for d in all_decks if d is not None]
        all_decks.append(deck)

        if len(all_decks) >= 2:
            # Combined max SAS (only enforce when all 3 slots filled)
            if len(all_decks) == 3 and match.combined_max_sas is not None:
                total_sas = sum(d.sas_rating or 0 for d in all_decks)
                if total_sas > match.combined_max_sas:
                    errors.append(
                        f"Combined SAS ({total_sas}) exceeds limit ({match.combined_max_sas})"
                    )
                    return errors

            # Set diversity: no two decks share an expansion
            if match.set_diversity:
                expansions = [d.expansion for d in all_decks]
                if len(set(expansions)) != len(expansions):
                    errors.append(
                        "Set diversity required: no two decks can share an expansion"
                    )
                    return errors

            # House diversity: no two decks share any house
            if match.house_diversity:
                all_houses = []
                for d in all_decks:
                    houses = {
                        ps.house for ps in d.pod_stats if ps.house != "Archon Power"
                    }
                    all_houses.append(houses)
                for i in range(len(all_houses)):
                    for j in range(i + 1, len(all_houses)):
                        shared = all_houses[i] & all_houses[j]
                        if shared:
                            errors.append(
                                f"House diversity required: decks share house(s): {', '.join(shared)}"
                            )
                            return errors

    return errors


def generate_sealed_pools_for_standalone(match, player1_id, player2_id):
    """
    Generate sealed pools for a standalone match.

    match: StandaloneMatch instance (needs allowed_sets, decks_per_player, id)
    player1_id, player2_id: int

    Returns list of error strings (empty = success). On success, creates SealedPoolDeck
    records and sets match.sealed_pools_generated = True. Does NOT commit.
    """
    from sqlalchemy.sql.expression import func

    decks_per_player = match.decks_per_player or 3
    total_needed = decks_per_player * 2

    query = Deck.query
    if match.allowed_sets:
        query = query.filter(Deck.expansion.in_(match.allowed_sets))

    decks = query.order_by(func.rand()).limit(total_needed).all()
    if len(decks) < total_needed:
        return [
            f"Not enough decks in database ({len(decks)} available, {total_needed} needed)"
        ]

    random.shuffle(decks)
    players = [player1_id, player2_id]
    for i, player_id in enumerate(players):
        player_decks = decks[i * decks_per_player : (i + 1) * decks_per_player]
        for d in player_decks:
            spd = SealedPoolDeck(
                standalone_match_id=match.id,
                week_id=None,
                user_id=player_id,
                deck_id=d.id,
            )
            db.session.add(spd)

    match.sealed_pools_generated = True
    return []


def validate_alliance_for_standalone(
    match, user_id, pods, token_deck_id, prophecy_deck_id
):
    """
    Validate alliance pod selection for a standalone match.

    match: StandaloneMatch instance
    user_id: int
    pods: list of {"deck_id": int, "house": str}
    token_deck_id: int or None
    prophecy_deck_id: int or None

    Returns list of error strings (empty = valid).
    """
    if not isinstance(pods, list) or len(pods) != 3:
        return ["Exactly 3 pods are required"]

    # Build player's sealed pool
    pool = SealedPoolDeck.query.filter_by(
        standalone_match_id=match.id, user_id=user_id
    ).all()
    pool_deck_ids = {spd.deck_id for spd in pool}

    pod_deck_ids = []
    houses = []
    for i, pod in enumerate(pods):
        deck_id = pod.get("deck_id")
        house = pod.get("house", "")
        if not deck_id or not house:
            return [f"Pod {i + 1} requires deck_id and house"]

        if deck_id not in pool_deck_ids:
            return [f"Pod {i + 1}: deck not in your sealed pool"]

        valid_house = (
            PodStats.query.filter_by(deck_id=deck_id)
            .filter(PodStats.house == house)
            .first()
        )
        if not valid_house:
            return [f"Pod {i + 1}: {house} is not a house of the selected deck"]

        pod_deck_ids.append(deck_id)
        houses.append(house)

    if len(set(houses)) != 3:
        return ["All 3 pods must have unique houses"]

    allowed_sets = set(match.allowed_sets) if match.allowed_sets else set()
    needs_token = bool(allowed_sets & TOKEN_EXPANSION_IDS)
    needs_prophecy = PROPHECY_EXPANSION_ID in allowed_sets

    if needs_token:
        if not token_deck_id:
            return ["token_deck_id is required for this match's sets"]
        if token_deck_id not in pod_deck_ids:
            return ["token_deck_id must be one of the 3 pod decks"]

    if needs_prophecy:
        if not prophecy_deck_id:
            return ["prophecy_deck_id is required for Prophetic Visions"]
        if prophecy_deck_id not in pod_deck_ids:
            return ["prophecy_deck_id must be one of the 3 pod decks"]

    return []


def get_deck_platonic_card_ids(deck) -> list:
    """Return a list of platonic_card_id values (with duplicates) from a deck's cards."""
    return [cid.platonic_card_id for cid in deck.cards_from_assoc if cid.platonic_card_id]


def validate_alliance_open(match_or_week, user_id, pods, token_deck_id, prophecy_deck_id):
    """
    Validate open Alliance pod selection (not sealed — players choose any decks).

    match_or_week: StandaloneMatch or LeagueWeek instance
    user_id: int
    pods: list of {"deck_id": int, "house": str}
    token_deck_id: int or None
    prophecy_deck_id: int or None

    Returns list of error strings (empty = valid).
    """
    if not isinstance(pods, list) or len(pods) != 3:
        return ["Exactly 3 pods are required"]

    pod_deck_ids = []
    pod_expansions = []
    houses = []
    for i, pod in enumerate(pods):
        deck_id = pod.get("deck_id")
        house = pod.get("house", "")
        if not deck_id or not house:
            return [f"Pod {i + 1} requires deck_id and house"]

        deck = db.session.get(Deck, deck_id)
        if not deck:
            return [f"Pod {i + 1}: deck not found"]

        valid_house = (
            PodStats.query.filter_by(deck_id=deck_id)
            .filter(PodStats.house == house)
            .first()
        )
        if not valid_house:
            return [f"Pod {i + 1}: {house} is not a house of the selected deck"]

        pod_deck_ids.append(deck_id)
        pod_expansions.append(deck.expansion)
        houses.append(house)

    if len(set(houses)) != 3:
        return ["All 3 pods must have unique houses"]

    # All 3 pods must be from the same set
    if len(set(pod_expansions)) != 1:
        return ["All 3 pods must be from the same set"]

    common_expansion = pod_expansions[0]

    # If allowed_sets is set on match/week, common expansion must be in it
    allowed_sets = getattr(match_or_week, "allowed_sets", None)
    if allowed_sets:
        if isinstance(allowed_sets, str):
            import json as _json

            try:
                allowed_sets = _json.loads(allowed_sets)
            except Exception:
                allowed_sets = []
        if common_expansion not in allowed_sets:
            from keytracker.schema import KeyforgeSet

            kf_set = db.session.get(KeyforgeSet, common_expansion)
            set_name = kf_set.name if kf_set else str(common_expansion)
            return [f"Pods from {set_name} are not allowed in this match/week"]

    # Token/prophecy: derive from actual deck expansions
    pod_expansion_set = set(pod_expansions)
    needs_token = bool(pod_expansion_set & TOKEN_EXPANSION_IDS)
    needs_prophecy = PROPHECY_EXPANSION_ID in pod_expansion_set

    if needs_token:
        if not token_deck_id:
            return ["token_deck_id is required for the selected pod sets"]
        if token_deck_id not in pod_deck_ids:
            return ["token_deck_id must be one of the 3 pod decks"]

    if needs_prophecy:
        if not prophecy_deck_id:
            return ["prophecy_deck_id is required for Prophetic Visions pods"]
        if prophecy_deck_id not in pod_deck_ids:
            return ["prophecy_deck_id must be one of the 3 pod decks"]

    # Restricted list check — skip if all 3 pod decks are the same physical deck
    if len(set(pod_deck_ids)) > 1:
        rl_version_id = getattr(match_or_week, "alliance_restricted_list_version_id", None)
        if rl_version_id:
            rl_version = db.session.get(AllianceRestrictedListVersion, rl_version_id)
        else:
            rl_version = (
                AllianceRestrictedListVersion.query.order_by(
                    AllianceRestrictedListVersion.version.desc()
                ).first()
            )

        if rl_version and rl_version.entries:
            # Collect all platonic card ids from all pod decks (with duplicates)
            all_card_ids = []
            for deck_id in pod_deck_ids:
                deck = db.session.get(Deck, deck_id)
                if deck:
                    all_card_ids.extend(get_deck_platonic_card_ids(deck))

            # Count restricted entries present
            restricted_entries_found = 0
            for entry in rl_version.entries:
                count = all_card_ids.count(entry.platonic_card_id)
                if count > 0:
                    restricted_entries_found += 1
                    if (
                        entry.max_copies_per_alliance is not None
                        and count > entry.max_copies_per_alliance
                    ):
                        card_name = (
                            entry.platonic_card.card_title
                            if entry.platonic_card
                            else f"card #{entry.platonic_card_id}"
                        )
                        return [
                            f"Alliance Restricted List: {card_name} appears {count} times "
                            f"(max {entry.max_copies_per_alliance})"
                        ]

            if restricted_entries_found > 1:
                return [
                    "Alliance Restricted List: alliance may only contain cards from at most "
                    "1 restricted list entry"
                ]

    return []


def validate_strike_standalone(matchup, striking_user_id, struck_deck_selection_id):
    """
    Validate a strike submission for a standalone Triad match.

    matchup: PlayerMatchup instance
    striking_user_id: int
    struck_deck_selection_id: int

    Returns error string or None (None = valid).
    """
    from keytracker.schema import StrikeSelection

    if striking_user_id not in (matchup.player1_id, matchup.player2_id):
        return "You are not in this matchup"

    if not matchup.player1_started or not matchup.player2_started:
        return "Both players must start before striking"

    existing_strike = StrikeSelection.query.filter_by(
        player_matchup_id=matchup.id, striking_user_id=striking_user_id
    ).first()
    if existing_strike:
        return "You have already submitted a strike"

    opponent_id = (
        matchup.player2_id
        if striking_user_id == matchup.player1_id
        else matchup.player1_id
    )
    struck_sel = db.session.get(PlayerDeckSelection, struck_deck_selection_id)
    if not struck_sel or struck_sel.user_id != opponent_id:
        return "Invalid deck selection to strike"

    # Must belong to this standalone match
    if struck_sel.standalone_match_id != matchup.standalone_match_id:
        return "Invalid deck selection to strike"

    return None


def get_adaptive_winning_deck_player_id(pm):
    """
    Return the player_id whose deck is the 'winning deck' (won both G1 and G2),
    or None if conditions are not met (not exactly 2 games, or same winner both games).

    In Adaptive: G1 = own decks, G2 = swapped decks.
    The winning deck is the deck that won G1 (played by its owner) and G2 (played by
    the opponent). So the winning deck owner is game1.winner_id.
    """
    games = sorted(pm.games, key=lambda g: g.game_number)
    if len(games) != 2:
        return None
    g1, g2 = games[0], games[1]
    if g1.winner_id == g2.winner_id:
        return None  # Same player won both — match is already decided, no tie
    return g1.winner_id


def init_adaptive_bidding(pm):
    """
    Initialize adaptive bidding after a 1-1 tie in game 2.
    Sets bid_chains=0, bidder_id=winning_deck_player_id, bidding_complete=False.
    Does NOT commit.
    """
    winning_deck_player_id = get_adaptive_winning_deck_player_id(pm)
    pm.adaptive_bid_chains = 0
    pm.adaptive_bidder_id = winning_deck_player_id
    pm.adaptive_bidding_complete = False


def validate_adaptive_bid(pm, requesting_user_id, chains=None, concede=False):
    """
    Validate and process an adaptive bid or concede.

    pm: PlayerMatchup instance
    requesting_user_id: int — the user submitting the action
    chains: int or None — number of chains to bid (must be > current bid)
    concede: bool — if True, accept the current bid and complete bidding

    Returns (success: bool, error: str or None).
    """
    # Must be a 1-1 tie situation with bidding initialized
    if pm.adaptive_bid_chains is None:
        return False, "Adaptive bidding has not been initialized"
    if pm.adaptive_bidding_complete:
        return False, "Adaptive bidding is already complete"
    if requesting_user_id not in (pm.player1_id, pm.player2_id):
        return False, "You are not in this matchup"

    # It must be the non-bidder's turn to act
    current_bidder_id = pm.adaptive_bidder_id
    if requesting_user_id == current_bidder_id:
        return False, "It is not your turn — waiting for your opponent to respond"

    if concede:
        pm.adaptive_bidding_complete = True
        return True, None

    if chains is None:
        return False, "chains or concede is required"
    if not isinstance(chains, int):
        return False, "chains must be an integer"
    if chains <= pm.adaptive_bid_chains:
        return (
            False,
            f"chains must be greater than current bid ({pm.adaptive_bid_chains})",
        )

    # Raise: update bid and flip bidder
    pm.adaptive_bid_chains = chains
    pm.adaptive_bidder_id = requesting_user_id
    return True, None


def validate_and_record_game(matchup, reporter_id, game_data, best_of_n, format_type):
    """
    Validate and record a game result for a PlayerMatchup.

    matchup: PlayerMatchup instance
    reporter_id: int
    game_data: dict with game_number, winner_id, player1_keys, player2_keys, etc.
    best_of_n: int
    format_type: WeekFormat enum value

    Returns (MatchGame or None, error_string or None).
    """
    game_number = game_data.get("game_number")
    winner_id = game_data.get("winner_id")

    if not isinstance(game_number, int) or game_number < 1:
        return None, "game_number must be a positive integer"
    if winner_id not in (matchup.player1_id, matchup.player2_id):
        return None, "winner_id must be one of the players"

    existing_games = sorted(matchup.games, key=lambda g: g.game_number)
    expected_next = len(existing_games) + 1
    if game_number != expected_next:
        return None, f"Expected game_number {expected_next}"

    wins_needed = math.ceil(best_of_n / 2)
    p1_wins = sum(1 for g in existing_games if g.winner_id == matchup.player1_id)
    p2_wins = sum(1 for g in existing_games if g.winner_id == matchup.player2_id)
    if p1_wins >= wins_needed or p2_wins >= wins_needed:
        return None, "Match is already decided"

    p1_keys = game_data.get("player1_keys", 0)
    p2_keys = game_data.get("player2_keys", 0)
    if not isinstance(p1_keys, int) or p1_keys < 0 or p1_keys > 3:
        return None, "player1_keys must be 0-3"
    if not isinstance(p2_keys, int) or p2_keys < 0 or p2_keys > 3:
        return None, "player2_keys must be 0-3"

    p1_deck_id = game_data.get("player1_deck_id")
    p2_deck_id = game_data.get("player2_deck_id")

    if format_type == WeekFormat.TRIAD:
        if not p1_deck_id or not p2_deck_id:
            return None, "player1_deck_id and player2_deck_id required for Triad"

        stricken_sel_ids = {s.struck_deck_selection_id for s in matchup.strikes}
        stricken_deck_ids = set()
        for sel_id in stricken_sel_ids:
            sel = db.session.get(PlayerDeckSelection, sel_id)
            if sel:
                stricken_deck_ids.add(sel.deck_id)

        if p1_deck_id in stricken_deck_ids:
            return None, "Player 1's selected deck has been stricken"
        if p2_deck_id in stricken_deck_ids:
            return None, "Player 2's selected deck has been stricken"

        for g in existing_games:
            if g.winner_id == matchup.player1_id and g.player1_deck_id == p1_deck_id:
                return None, "Player 1's deck already won a game and cannot be reused"
            if g.winner_id == matchup.player2_id and g.player2_deck_id == p2_deck_id:
                return None, "Player 2's deck already won a game and cannot be reused"

    if format_type == WeekFormat.ADAPTIVE and game_number == 3:
        if not matchup.adaptive_bidding_complete:
            return (
                None,
                "Adaptive bidding must be completed before game 3 can be played",
            )

    game = MatchGame(
        player_matchup_id=matchup.id,
        game_number=game_number,
        winner_id=winner_id,
        player1_keys=p1_keys,
        player2_keys=p2_keys,
        went_to_time=bool(game_data.get("went_to_time", False)),
        loser_conceded=bool(game_data.get("loser_conceded", False)),
        player1_deck_id=p1_deck_id,
        player2_deck_id=p2_deck_id,
        reported_by_id=reporter_id,
    )
    db.session.add(game)
    db.session.flush()
    db.session.expire(matchup, ["games"])

    # After recording game 2 for Adaptive: if it creates a 1-1 tie, init bidding
    if format_type == WeekFormat.ADAPTIVE and game_number == 2:
        winning_deck_player_id = get_adaptive_winning_deck_player_id(matchup)
        if winning_deck_player_id is not None:
            init_adaptive_bidding(matchup)

    return game, None
