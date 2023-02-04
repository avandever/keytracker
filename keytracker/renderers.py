from keytracker.schema import Card, Game
from flask import url_for
import re
from typing import Dict
import logging


logger = logging.getLogger(__name__)


MV_BROWSER_BASE = "https://www.keyforgegame.com/deck-details"

DOK_BROWSER_BASE = "https://decksofkeyforge.com/decks"
DOK_COMPARE_TEMPLATE = "https://decksofkeyforge.com/compare-decks?decks={}&decks={}"

CARD_PLAY_BASIC = re.compile(r".* plays (.*)")
CARD_PLAY_UPGRADE = re.compile(r".* plays (.*) attaching it to (.*)")


def render_log(log: str) -> str:
    message = log.message.strip('\r')
    message = insert_card_images(message)
    return f"{message}"


def insert_card_images(message: str) -> str:
    for matcher in [
        CARD_PLAY_UPGRADE,
        CARD_PLAY_BASIC,
    ]:
        m = matcher.match(message)
        if m:
            print(f"Matches: {m.groups()}")
            for card_title in m.groups():
                message = message.replace(card_title, dress_up_card(card_title))
            # Don't try remaining matchers
            break
    return f'<div class="cardplay">{message}</div>'


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
