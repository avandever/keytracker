"""
MV (Master Vault) API proxy.

Exposes a subset of the Master Vault API format using locally-stored deck data,
so that a local DoK instance can fetch deck data from Tracker instead of hitting
the real Master Vault API.  DoK is configured to point its mvProxyBaseUrl at
http://localhost:3001/api/master-vault.
"""

from flask import Blueprint, jsonify

from keytracker.schema import Deck

_CREATURE_TYPES = {"Creature", "Token Creature", "Gigantic Creature Art", "Gigantic Creature Base"}

mv_proxy_bp = Blueprint("mv_proxy_bp", __name__)


@mv_proxy_bp.route("/decks/<kf_id>")
def mv_deck_proxy(kf_id):
    deck = Deck.query.filter_by(kf_id=kf_id).first()
    if deck is None:
        return jsonify({"error": f"Deck {kf_id} not found in local database"}), 404

    cards = deck.cards_from_assoc

    # Deduplicate houses, preserving order; use lowercased name as a stable fake ID.
    seen_houses = {}
    for card in cards:
        h = card.house
        if h and h not in seen_houses:
            seen_houses[h] = h.lower().replace(" ", "-")

    houses_linked = [
        {"id": house_id, "name": house_name, "image": ""}
        for house_name, house_id in seen_houses.items()
    ]

    # Build bonus_icons from per-card enhancement data.
    bonus_icons = []
    for card in cards:
        icons = (
            ["amber"] * (card.enhanced_amber or 0)
            + ["capture"] * (card.enhanced_capture or 0)
            + ["draw"] * (card.enhanced_draw or 0)
            + ["damage"] * (card.enhanced_damage or 0)
            + ["discard"] * (card.enhanced_discard or 0)
        )
        if icons:
            bonus_icons.append({"card_id": card.card_kf_id, "bonus_icons": icons})

    cards_linked = []
    for card in cards:
        trait_names = [t.name for t in (card.traits or [])]
        cards_linked.append(
            {
                "id": card.card_kf_id,
                "card_title": card.card_title,
                "house": card.house,
                "card_type": card.card_type,
                "front_image": card.front_image or "",
                "card_text": card.card_text or "",
                "amber": card.amber or 0,
                "power": str(card.power) if card.card_type in _CREATURE_TYPES else None,
                "armor": str(card.armor) if card.card_type in _CREATURE_TYPES else None,
                "rarity": card.rarity or "",
                "flavor_text": card.flavor_text,
                "card_number": card.card_number or "",
                "expansion": card.expansion,
                "is_maverick": bool(card.is_maverick),
                "is_anomaly": bool(card.is_anomaly),
                "is_enhanced": bool(card.is_enhanced),
                "is_non_deck": bool(card.is_non_deck),
                "traits": " • ".join(trait_names) if trait_names else None,
            }
        )

    response = {
        "data": {
            "id": deck.kf_id,
            "name": deck.name,
            "expansion": deck.expansion,
            "power_level": 0,
            "chains": 0,
            "wins": 0,
            "losses": 0,
            "bonus_icons": bonus_icons,
            "_links": {
                "houses": list(seen_houses.values()),
                "cards": [c["id"] for c in cards_linked],
            },
        },
        "_linked": {
            "houses": houses_linked,
            "cards": cards_linked,
        },
    }

    return jsonify(response)
