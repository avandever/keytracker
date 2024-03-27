from keytracker.schema import Card, Game
from flask import url_for
import re
from typing import Dict
import logging
from keytracker.utils import CsvPod


logger = logging.getLogger(__name__)


MV_BROWSER_BASE = "https://www.keyforgegame.com/deck-details"

DOK_BROWSER_BASE = "https://decksofkeyforge.com/decks"
DOK_COMPARE_TEMPLATE = "https://decksofkeyforge.com/compare-decks?decks={}&decks={}"

CARD_PLAY_MATCHERS = [
    re.compile(r".* plays (.*)"),
    re.compile(r".* plays (.*) attaching it to (.*)"),
]

SYSTEM_TEXT_MATCHERS = [
    re.compile(r".* brings .* to The Crucible"),
    re.compile(r"Compare Decks"),
    re.compile(r".* has connected to the game server"),
    re.compile(r"(\w+) phase - (\w+)"),
]

UPKEEP_MATCHERS = [
    re.compile(r".* chooses to randomize the first player"),
    re.compile(r".* won the flip and is first player"),
    re.compile(r".* draws [0-9]+ card ?s to their maximum of [0-9]+"),
    re.compile(r".* is shuffling their deck"),
    re.compile(r".* draws [0-9]+ cards?"),
    re.compile(r".* does not forge a key.*"),
    re.compile(r".* readies their cards"),
    re.compile(r"End of turn [0-9]+"),
    re.compile(r".* chooses (.*) as their active house this turn"),
    re.compile(r"(\w+): [0-9]+ [aÆ]mber .*keys?.*(\w+): [0-9]+ [aÆ]mber.*keys?.*"),
    re.compile(r".*in their archives to their hand.*"),
    re.compile(r".* declares Check!"),
]

MANUAL_MODE_MATCHERS = [
    re.compile(r".* is attempting to switch manual mode on"),
    re.compile(r".* allows enabling manual mode"),
    re.compile(r".* switches manual mode o(n|ff)"),
    re.compile(r".* manually.*"),
]

TURN_START_MATCHERS = [
    re.compile(r"TURN [0-9]+ - .*"),
]

FORGED_KEY_MATCHERS = [
    re.compile(r".* forges the (.*) key.*"),
]


def render_log(log: str) -> str:
    message = log.message.strip("\r")
    for formatter in [
        hide_system_messages,
        format_turn_start,
        format_card_plays,
        format_game_upkeep,
        format_key_forging,
        mark_uncategorized,
    ]:
        message = formatter(message)
        if "div" in message:
            return message


def format_key_forging(message: str) -> str:
    for matcher in FORGED_KEY_MATCHERS:
        if matcher.match(message):
            return f'<div class="forged_key_message">{message}</div>'
    return message


def format_turn_start(message: str) -> str:
    for matcher in TURN_START_MATCHERS:
        if matcher.match(message):
            return f'<div class="turn_start_message">{message}</div>'
    return message


def format_game_upkeep(message: str) -> str:
    for matcher in UPKEEP_MATCHERS:
        if matcher.match(message):
            return f'<div class="game_upkeep_message">{message}</div>'
    return message


def mark_uncategorized(message: str) -> str:
    return f'<div class="message-uncategorized">{message}</div>'


def hide_system_messages(message: str) -> str:
    for matcher in SYSTEM_TEXT_MATCHERS:
        if matcher.match(message):
            return f'<div class="system_message">{message}</div>'
    return message


def format_card_plays(message: str) -> str:
    any_match = False
    for matcher in CARD_PLAY_MATCHERS:
        m = matcher.match(message)
        if m:
            any_match = True
            for card_title in m.groups():
                message = message.replace(card_title, dress_up_card(card_title))
            # Don't try remaining matchers
            return f'<div class="cardplay">{message}</div>'
    return message


def dress_up_card(title: str) -> str:
    card = Card.query.filter_by(card_title=title).first()
    if card is None:
        logger.error(f"Could not find card in db: '{repr(title)}'")
        return title
    else:
        card_img = f'<img src="{card.front_image}"/>'
        span = f'<span class="hoverable_card">{title}{card_img}</span>'
        return span


def render_game_listing(game: Game, username: str = None, deck_id: str = None):
    output = ""
    players = []
    if game.winner == game.insist_first_player:
        player_order = [game.winner, game.loser]
        deck_order = [game.winner_deck, game.loser_deck]
    else:
        player_order = [game.loser, game.winner]
        deck_order = [game.loser_deck, game.winner_deck]
    for player in player_order:
        if player == username:
            players.append(player)
        else:
            url = url_for("ui.user", username=player)
            players.append(f'<a href="{url}">{player}</a>')
    decks = []
    for deck in deck_order:
        deck_summary = f"{deck.sas_rating} SAS, {deck.aerc_score} AERC"
        if deck.kf_id == deck_id:
            decks.append(f"{deck.name} - {deck_summary}")
        else:
            deck_url = url_for("ui.deck", deck_id=deck.kf_id)
            mv_url = f'<a href="{MV_BROWSER_BASE}/{deck.kf_id}">MV</a>'
            dok_url = f'<a href="{DOK_BROWSER_BASE}/{deck.kf_id}">DoK</a>'
            decks.append(
                f'<a href="{deck_url}">{deck.name}</a> - {deck_summary} '
                f"({mv_url}) ({dok_url})"
            )
    game_url = url_for("ui.game", crucible_game_id=game.crucible_game_id)
    game_link = f'<a href="{game_url}">Game Details</a>'
    compare_url = DOK_COMPARE_TEMPLATE.format(
        game.winner_deck.kf_id,
        game.loser_deck.kf_id,
    )
    compare_link = f'<a href="{compare_url}">DoK Compare</a>'
    return (
        f'<div class="game_players">{" vs. ".join(players)}&nbsp&nbsp&nbsp&nbsp{game_link}</div>'
        f'<div class="game_decks">{" vs. ".join(decks)}&nbsp&nbsp&nbsp&nbsp{compare_link}</div>'
    )


def render_dropdown(name: str, options: Dict[str, str], selected: str = None) -> str:
    output = f'<select id="{name}" name="{name}">\n'
    for key, description in options.items():
        option = f'<option value="{key}"'
        if selected == key:
            option += " selected"
        option += f">{description}</option>\n"
        output += option
    output += "</select>"
    return output


def render_input_number(
    name: str, label: str, lower: int, upper: int, current_value: int = None
) -> str:
    output = '<p class="form_element">'
    output += f'<label for="{name}">{label}</label>'
    bits = {
        "type": "number",
        "id": name,
        "name": name,
        "min": lower,
        "max": upper,
        "size": len(str(upper)),
    }
    if current_value is not None:
        bits["value"] = current_value
    bits_str = " ".join([f'{k}="{v}"' for k, v in bits.items()])
    output += f"<input {bits_str}></p>"
    return output
