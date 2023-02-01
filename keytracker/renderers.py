from keytracker.schema import Game
from flask import url_for
from typing import Dict


MV_BROWSER_BASE = "https://www.keyforgegame.com/deck-details"

DOK_BROWSER_BASE = "https://decksofkeyforge.com/decks"
DOK_COMPARE_TEMPLATE = "https://decksofkeyforge.com/compare-decks?decks={}&decks={}"


def render_log(log: str) -> str:
    return log.message


def render_game_listing(game: Game, username: str = None, deck_id: str = None):
    output = ""
    players = []
    for player in [game.winner, game.loser]:
        if player == username:
            players.append(player)
        else:
            url = url_for("ui.user", username=player)
            players.append(f'<a href="{url}">{player}</a>')
    decks = []
    for deck in [game.winner_deck, game.loser_deck]:
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
