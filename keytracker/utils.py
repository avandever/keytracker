from collections import Counter, defaultdict
import configparser
import datetime
from keytracker.schema import db, Card, Deck, Game
import os
from typing import Dict, Iterable, Tuple
import requests
import re
import sqlalchemy
from sqlalchemy import and_, or_
from sqlalchemy.orm import Query


PLAYER_DECK_MATCHER = re.compile(r"^(.*) brings (.*) to The Crucible")
FIRST_PLAYER_MATCHER = re.compile(r"^(.*) (won the flip|chooses to go first)")
SHUFFLE_MATCHER = re.compile(r"^(.*) is shuffling their deck")
HOUSE_CHOICE_MATCHER = re.compile(r"^(.*) chooses (.*) as their active house")
FORGE_MATCHER = re.compile(r"^(.*) forges the (.*) key *, paying ([0-9]+) Æmber")
WIN_MATCHER = re.compile(r"\s*([^ ].*) has won the game")

MV_API_BASE = "http://www.keyforgegame.com/api/decks"


DOK_HEADERS = {"Api-Key": os.environ.get("DOK_API_KEY")}
DOK_DECK_BASE = "https://decksofkeyforge.com/public-api/v3/decks"
LATEST_SAS_VERSION = 42


class BadLog(Exception):
    pass


class UnknownDBDriverException(Exception):
    pass


class DeckNotFoundError(Exception):
    pass


class DuplicateGameError(Exception):
    pass


class MissingInput(Exception):
    pass


def load_config() -> Dict[str, str]:
    config = {}
    config_path = os.environ.get("TRACKER_CONFIG_PATH", "config.ini")
    if config_path == "ENV":
        config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
        config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "placeholder")
    else:
        cparser = configparser.ConfigParser()
        cparser.read(config_path)
        config["SQLALCHEMY_DATABASE_URI"] = config_to_uri(**cparser["db"])
        config["SECRET_KEY"] = cparser["app"]["secret_key"]
    assert config["SQLALCHEMY_DATABASE_URI"] is not None
    assert config["SECRET_KEY"] != "placeholder"
    return config


def config_to_uri(
    driver: str = "sqlite",
    path: str = "keyforge_cards.sqlite",
    host: str = "localhost",
    port: int = None,
    user: str = None,
    password: str = None,
    database: str = "keyforge_decks",
    **connect_query,
) -> str:
    return sqlalchemy.engine.url.URL.create(
        drivername=driver,
        username=user,
        password=password,
        database=database,
        # If unix_socket is passed in, we us that in connect_query, and leave off
        # host/port args
        host=None if connect_query else host,
        port=None if connect_query else port,
        query=connect_query,
    )


def render_log(log: str) -> str:
    return log.message


class PlayerInfo:
    def __init__(self):
        self.player_name = "UNSET"
        self.deck_name = "UNSET"
        self.first_player = False
        self.shuffles = 0
        self.house_counts = defaultdict(int)
        self.keys_forged = 0
        self.key_costs = []
        self.winner = False

    def __repr__(self) -> str:
        return "PlayerInfo(player_name={self.player_name}, deck_name={self.deck_name})"


def log_to_game(log: str) -> Game:
    lines = log.split("\n")
    print(f"Starting to parse log with {len(lines)} lines.")
    cursor = iter(lines)
    player_infos = {}
    try:
        print("Looking for players!")
        count = 1
        while len(player_infos) < 2:
            line = next(cursor)
            count += 1
            m = PLAYER_DECK_MATCHER.match(line)
            if m:
                print(f"Found player {m.group(1)} with deck {m.group(2)}")
                player_infos[m.group(1)] = PlayerInfo()
                player_infos[m.group(1)].deck_name = m.group(2)
                player_infos[m.group(1)].player_name = m.group(1)
    except StopIteration:
        raise BadLog("Did not find two players in log")
    try:
        while not any(pi.first_player for pi in player_infos.values()):
            line = next(cursor)
            m = FIRST_PLAYER_MATCHER.match(line)
            if m:
                print(f"Found first player: {m.group(1)}")
                player_infos[m.group(1)].first_player = True
    except StopIteration:
        raise BadLog("Could not determine first player from log")
    try:
        while not line.startswith("Key phase"):
            line = next(cursor)
            m = SHUFFLE_MATCHER.match(line)
            if m:
                print("Found first turn")
                player_infos[m.group(1)].shuffles += 1
    except StopIteration:
        raise BadLog("Could not find first turn start")
    try:
        while True:
            line = next(cursor)
            m = HOUSE_CHOICE_MATCHER.match(line)
            if m:
                print(f"{m.group(1)} picked {m.group(2)}")
                player_infos[m.group(1)].house_counts[m.group(2)] += 1
                continue
            m = FORGE_MATCHER.match(line)
            if m:
                print(f"{m.group(1)} forged for {m.group(3)}")
                player_infos[m.group(1)].keys_forged += 1
                player_infos[m.group(1)].key_costs.append(int(m.group(3)))
                continue
            m = WIN_MATCHER.match(line)
            if m:
                print(f"{m.group(1)} won")
                player_infos[m.group(1)].winner = True
                break
    except StopIteration:
        raise BadLog("Could not determine game winner from log")
    for player in player_infos.values():
        if player.winner:
            winner = player
        else:
            loser = player
    winner_deck = get_deck_by_name_with_zeal(winner.deck_name)
    loser_deck = get_deck_by_name_with_zeal(loser.deck_name)
    print(f"Winning deck: {winner_deck.name}")
    print(f"Losing deck: {loser_deck.name}")
    game = Game(
        winner=winner.player_name,
        winner_deck_id=deck_name_to_id(winner.deck_name),
        winner_deck_name=winner.deck_name,
        winner_keys=winner.keys_forged,
        loser=loser.player_name,
        loser_deck_id=deck_name_to_id(loser.deck_name),
        loser_deck_name=loser.deck_name,
        loser_keys=loser.keys_forged,
    )
    return game


def add_card_to_deck(card_dict: Dict, deck: Deck):
    card_id = card_dict.pop("id")
    card = Card.query.filter_by(kf_id=card_id).first()
    if card is None:
        card_dict["kf_id"] = card_id
        card = Card(**card_dict)
        db.session.add(card)
        db.session.commit()
        db.session.refresh(card)
    deck.card_id_list.append(card.id)


def get_deck_by_id_with_zeal(deck_id: str) -> Deck:
    deck = Deck.query.filter_by(kf_id=deck_id).first()
    if deck is None:
        deck_url = os.path.join(MV_API_BASE, deck_id)
        response = requests.get(deck_url, params={"links": "cards, notes"})
        data = response.json()
        deck = Deck(
            kf_id=data["data"]["id"],
            name=data["data"]["name"],
            expansion=data["data"]["expansion"],
        )
        update_sas_scores(deck)
        deck.card_id_list = []
        for card in data["_linked"]["cards"]:
            add_card_to_deck(card, deck)
        db.session.add(deck)
        db.session.commit()
        return deck
    return deck


def get_deck_by_name_with_zeal(deck_name: str) -> Deck:
    deck = Deck.query.filter_by(name=deck_name).first()
    if deck is None:
        deck_id = deck_name_to_id(deck_name)
        deck = get_deck_by_id_with_zeal(deck_id)
    return deck


def update_sas_scores(deck: Deck) -> bool:
    """Returns True if update occurred."""
    if (deck.sas_version or 0) >= LATEST_SAS_VERSION:
        return False
    url = os.path.join(DOK_DECK_BASE, deck.kf_id)
    response = requests.get(url, headers=DOK_HEADERS)
    data = response.json()
    deck.sas_rating = data["deck"]["sasRating"]
    deck.aerc_score = data["deck"]["aercScore"]
    deck.sas_version = data["sasVersion"]
    return True


def deck_name_to_id(deck_name: str) -> str:
    search_params = {"search": deck_name}
    response = requests.get(MV_API_BASE, params=search_params)
    data = response.json()
    if not data["data"]:
        raise DeckNotFoundError(f"Found no decks with name {deck_name}")
    if len(data["data"]) > 1:
        raise DeckNotFoundError(f"Found multiple decks matching {deck_name}")
    return data["data"][0]["id"]


def deck_id_to_name(deck_id: str) -> str:
    deck = get_deck_by_id_with_zeal(deck_id)
    return deck.name


def basic_stats_to_game(**kwargs) -> Game:
    crucible_game_id = kwargs.get("crucible_game_id")
    datestr = kwargs.get("date")
    if not datestr:
        game_start = datetime.datetime.now()
    else:
        date = datetime.datetime.fromisoformat(datestr.rstrip("Z"))
    turns = kwargs.get("turns")
    winner = kwargs.get("winner")
    winner_deck_id = kwargs.get("winner_deck_id")
    winner_deck_name = kwargs.get("winner_deck_name")
    loser = kwargs.get("loser")
    loser_deck_id = kwargs.get("loser_deck_id")
    loser_deck_name = kwargs.get("loser_deck_name")
    if not winner_deck_id:
        if not winner_deck_name:
            raise MissingInput("Need name or id of winning deck")
        winner_deck_id = deck_name_to_id(winner_deck_name)
    if not loser_deck_id:
        if not loser_deck_name:
            raise MissingInput("Need name or id of losing deck")
        loser_deck_id = deck_name_to_id(loser_deck_name)
    # If urls were passed in, fix that now
    winner_deck_id = winner_deck_id.split("/")[-1]
    loser_deck_id = loser_deck_id.split("/")[-1]
    if not winner_deck_name:
        winner_deck_name = deck_id_to_name(winner_deck_id)
    if not loser_deck_name:
        loser_deck_name = deck_id_to_name(loser_deck_id)
    game = Game(
        crucible_game_id=crucible_game_id,
        date=date,
        winner=winner,
        winner_deck_id=winner_deck_id,
        winner_deck_name=winner_deck_name,
        winner_keys=kwargs.get("winner_keys", 3),
        loser=loser,
        loser_deck_id=loser_deck_id,
        loser_deck_name=loser_deck_name,
        loser_keys=kwargs.get("loser_keys"),
    )
    return game


def add_user_filters(
    query: Query,
    user_filters: Iterable[str],
) -> Query:
    for user_string in user_filters:
        if "|" in user_string:
            query = query.filter(
                or_(
                    Game.winner.in_(user_string.split("|")),
                    Game.loser.in_(user_string.split("|")),
                )
            )
        else:
            query = query.filter(
                or_(
                    Game.winner == user_string,
                    Game.loser == user_string,
                )
            )
    return query


def add_deck_filters(
    query: Query,
    deck_filters: Iterable[str],
) -> Query:
    for deck in deck_filters:
        query = query.filter(
            or_(
                Game.winner_deck_id == deck,
                Game.loser_deck_id == deck,
            )
        )
    return query


def add_game_sort(
    query: Query,
    sort_specs: Iterable[Tuple[str, str]],
) -> Query:
    for (col, direction) in sort_specs:
        query = query.order_by(getattr(getattr(Game, col), direction)())
    return query
