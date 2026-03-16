"""
Regression test for the MV API proxy endpoint.

The stored fixture (tests/fixtures/mv_deck_6e477f65.json) is a real response
from the Master Vault API captured at the time the proxy was implemented.
The test builds a mock Deck from that fixture, calls the proxy, and asserts
that the response matches the fixture on all fields that DoK uses for scoring.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

DECK_ID = "6e477f65-c9f9-4e52-a3ec-6d5e15936de6"
FIXTURE = "tests/fixtures/mv_deck_6e477f65.json"

_CREATURE_TYPES = {
    "Creature",
    "Token Creature",
    "Gigantic Creature Art",
    "Gigantic Creature Base",
}


@pytest.fixture(scope="module")
def mv_fixture():
    with open(FIXTURE) as f:
        return json.load(f)


def _build_mock_deck(mv_data):
    """
    Construct a mock Deck (with mock CardInDeck children) whose data matches
    the given MV fixture.  Power/armor are stored as ints internally (0 for
    non-creatures); traits are a list of SimpleNamespace(name=...) objects.
    """
    deck_data = mv_data["data"]
    cards_by_id = {c["id"]: c for c in mv_data["_linked"]["cards"]}
    card_id_list = deck_data["_links"]["cards"]
    bi_lookup = {
        b["card_id"]: b["bonus_icons"] for b in deck_data.get("bonus_icons", [])
    }

    mock_deck = MagicMock()
    mock_deck.kf_id = deck_data["id"]
    mock_deck.name = deck_data["name"]
    mock_deck.expansion = deck_data["expansion"]

    mock_cards = []
    for card_id in card_id_list:
        card_data = cards_by_id[card_id]
        mc = MagicMock()
        mc.card_kf_id = card_id
        mc.card_title = card_data["card_title"]
        mc.house = card_data["house"]
        mc.card_type = card_data["card_type"]
        mc.front_image = card_data.get("front_image", "")
        mc.card_text = card_data.get("card_text", "")
        mc.amber = card_data.get("amber", 0)
        # Stored as int internally; null in MV means non-creature → store as 0
        power_str = card_data.get("power")
        armor_str = card_data.get("armor")
        mc.power = int(power_str) if power_str is not None else 0
        mc.armor = int(armor_str) if armor_str is not None else 0
        mc.rarity = card_data.get("rarity", "")
        mc.flavor_text = card_data.get("flavor_text")
        mc.card_number = card_data.get("card_number", "")
        mc.expansion = card_data.get("expansion")
        mc.is_maverick = card_data.get("is_maverick", False)
        mc.is_anomaly = card_data.get("is_anomaly", False)
        mc.is_enhanced = card_data.get("is_enhanced", False)
        mc.is_non_deck = card_data.get("is_non_deck", False)

        traits_str = card_data.get("traits")
        mc.traits = (
            [SimpleNamespace(name=t) for t in traits_str.split(" • ")]
            if traits_str
            else []
        )

        icons = bi_lookup.get(card_id, [])
        mc.enhanced_amber = icons.count("amber")
        mc.enhanced_capture = icons.count("capture")
        mc.enhanced_draw = icons.count("draw")
        mc.enhanced_damage = icons.count("damage")
        mc.enhanced_discard = icons.count("discard")

        mock_cards.append(mc)

    mock_deck.cards_from_assoc = mock_cards
    return mock_deck


def test_mv_proxy_matches_fixture(client, mv_fixture):
    mock_deck = _build_mock_deck(mv_fixture)

    with patch("keytracker.routes.mv_proxy.Deck") as MockDeck:
        MockDeck.query.filter_by.return_value.first.return_value = mock_deck
        resp = client.get(f"/api/master-vault/decks/{DECK_ID}")

    assert resp.status_code == 200
    result = resp.get_json()
    mv = mv_fixture

    # --- deck-level fields ---
    assert result["data"]["id"] == mv["data"]["id"]
    assert result["data"]["name"] == mv["data"]["name"]
    assert result["data"]["expansion"] == mv["data"]["expansion"]

    # --- card ID lists match (order-insensitive) ---
    assert sorted(result["data"]["_links"]["cards"]) == sorted(
        mv["data"]["_links"]["cards"]
    )

    # --- per-card fields ---
    result_cards = {c["id"]: c for c in result["_linked"]["cards"]}
    mv_cards = {c["id"]: c for c in mv["_linked"]["cards"]}
    assert set(result_cards) == set(mv_cards), "card ID sets differ"

    for card_id, mv_card in mv_cards.items():
        r = result_cards[card_id]
        assert r["card_title"] == mv_card["card_title"], f"{card_id}: card_title"
        assert r["house"] == mv_card["house"], f"{card_id}: house"
        assert r["card_type"] == mv_card["card_type"], f"{card_id}: card_type"
        assert r["amber"] == mv_card["amber"], f"{card_id}: amber"
        assert r["power"] == mv_card["power"], f"{card_id}: power"
        assert r["armor"] == mv_card["armor"], f"{card_id}: armor"
        assert r["rarity"] == mv_card["rarity"], f"{card_id}: rarity"
        assert r["card_number"] == mv_card["card_number"], f"{card_id}: card_number"
        assert r["expansion"] == mv_card["expansion"], f"{card_id}: expansion"
        assert r["is_maverick"] == mv_card["is_maverick"], f"{card_id}: is_maverick"
        assert r["is_anomaly"] == mv_card["is_anomaly"], f"{card_id}: is_anomaly"
        assert r["is_enhanced"] == mv_card["is_enhanced"], f"{card_id}: is_enhanced"
        assert r["is_non_deck"] == mv_card["is_non_deck"], f"{card_id}: is_non_deck"
        # Traits compared as sets to ignore ordering differences
        r_traits = set(r["traits"].split(" • ")) if r.get("traits") else set()
        mv_traits = (
            set(mv_card["traits"].split(" • ")) if mv_card.get("traits") else set()
        )
        assert r_traits == mv_traits, f"{card_id}: traits"

    # --- bonus icons ---
    result_bi = {
        b["card_id"]: sorted(b["bonus_icons"])
        for b in result["data"].get("bonus_icons", [])
    }
    mv_bi = {
        b["card_id"]: sorted(b["bonus_icons"])
        for b in mv["data"].get("bonus_icons", [])
    }
    assert result_bi == mv_bi, "bonus_icons mismatch"

    # --- houses ---
    result_house_names = {h["name"] for h in result["_linked"]["houses"]}
    mv_house_names = {h["name"] for h in mv["_linked"]["houses"]}
    assert result_house_names == mv_house_names, "house names mismatch"


def test_mv_proxy_returns_404_for_unknown_deck(client):
    with patch("keytracker.routes.mv_proxy.Deck") as MockDeck:
        MockDeck.query.filter_by.return_value.first.return_value = None
        resp = client.get("/api/master-vault/decks/00000000-0000-0000-0000-000000000000")

    assert resp.status_code == 404
