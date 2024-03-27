import csv
from collections import Counter, defaultdict
import configparser
import copy
import datetime
import difflib
import io
from keytracker.schema import (
    db,
    Card,
    CardInDeck,
    CardType,
    Deck,
    DokDeck,
    Enhancements,
    Game,
    GlobalVariable,
    House,
    HouseTurnCounts,
    PlatonicCard,
    PlatonicCardInSet,
    Player,
    PodStats,
    POSSIBLE_LANGUAGES,
    Trait,
    house_str_to_enum,
    card_type_str_to_enum,
    rarity_str_to_enum,
)
import operator
import os
from typing import Any, Dict, IO, Iterable, List, Optional, Tuple
import random
import requests

from aiohttp_requests import requests as arequests
from aiohttp.client_exceptions import ContentTypeError
import asyncio
import re
import sqlalchemy
from sqlalchemy import and_, or_
from sqlalchemy.exc import (
    OperationalError,
    PendingRollbackError,
)
from sqlalchemy.orm import Query
from flask import current_app
import logging
import json
import time
import threading
from lingua import LanguageDetectorBuilder


PLAYER_DECK_MATCHER = re.compile(r"^(.*) brings (.*) to The Crucible")
FIRST_PLAYER_MATCHER = re.compile(r"^(.*) (won the flip|chooses to go first)")
SHUFFLE_MATCHER = re.compile(r"^(.*) is shuffling their deck")
HOUSE_CHOICE_MATCHER = re.compile(
    r"^([^ ]*) +chooses ([^ ]*) +as their active house this turn"
)
HOUSE_MANUAL_MATCHER = re.compile(
    r"^([^ ]*) +manually changed their active house to ([^ ]*)"
)
FORGE_MATCHER = re.compile(r"^(.*) forges the (.*) key *, paying ([0-9]+) Æmber")
WIN_MATCHER = re.compile(r"\s*([^ ].*) has won the game")

MV_API_BASE = "https://www.keyforgegame.com/api/decks"

DOK_HEADERS = {"Api-Key": os.environ.get("DOK_API_KEY")}
DOK_DECK_BASE = "https://decksofkeyforge.com/public-api/v3/decks"
LATEST_SAS_VERSION = 43
SAS_MAX_AGE_DAYS = 90
SAS_TD = datetime.timedelta(days=SAS_MAX_AGE_DAYS)
SEARCH_PARAMS = {
    "page_size": 25,
    "ordering": "-date",
}

language_detector = LanguageDetectorBuilder.from_languages(*POSSIBLE_LANGUAGES).build()

MM_UNHOUSED_CARDS = [
    "It’s Coming...",
    "Dark Æmber Vault",
]
REVENANTS = [
    "Ghostly Dr. Verokter",
    "Portalmonster",
    "Revived Ză-Orhă",
    "Xenos Darkshadow",
    "Immortal Greking",
    "Duma the Returned",
    "Spectral Ruth",
    "Qyxxlyxx Grave Master",
    "Cincinnatus Resurrexit",
    "Phantom Drummernaut",
    "Encounter Golem",
]


class CsvPod:
    __slots__ = ("name", "sas", "expansion", "house", "cards", "link", "on_market", "price")

    def __init__(self, name, expansion, link, house, sas, cards, for_sale, for_auction, for_trade, price) -> None:
        self.name = name
        self.expansion = expansion
        self.house = house
        self.link = link
        self.sas = float(sas)
        self.cards = cards
        self.on_market = "true" in (for_sale, for_trade, for_auction)
        self.price = price

    def headers(self) -> List[str]:
        return list(self.__slots__)

    def as_row(self) -> List:
        return [getattr(self, attr) for attr in self.__slots__]


class DeckFromCsv:
    __slots__ = ("name", "house1", "house2", "house3", "set_string", "house1_sas",
                 "house2_sas", "house3_sas", "house1_cards", "house2_cards",
                 "house3_cards", "link", "for_sale", "for_auction", "for_trade",
                 "price")
    ROWS_TO_READ = ('\ufeff"Name"', "Houses", "Expansion", "House 1 SAS", "House 2 SAS",
                    "House 3 SAS", "House 1 Cards", "House 2 Cards", "House 3 Cards",
                    "DoK Link", "For Sale", "For Auction", "For Trade", "Price")

    def __init__(
        self,
        name,
        house_string,
        set_string,
        house1_sas,
        house2_sas,
        house3_sas,
        house1_cards,
        house2_cards,
        house3_cards,
        link,
        for_sale,
        for_auction,
        for_trade,
        price
    ):
        self.name = name
        houses = house_string.split(" | ")
        self.house1, self.house2, self.house3 = houses
        self.set_string = set_string
        self.house1_sas = house1_sas
        self.house2_sas = house2_sas
        self.house3_sas = house3_sas
        self.house1_cards = house1_cards
        self.house2_cards = house2_cards
        self.house3_cards = house3_cards
        self.link = link
        self.for_sale = for_sale
        self.for_auction = for_auction
        self.for_trade = for_trade
        self.price = price

    def __repr__(self) -> str:
        return (f"{self.name} - {self.house1}: {self.house1_sas}, "
                f"{self.house2}: {self.house2_sas}, {self.house3}: {self.house3_sas}")

    def as_pods(self) -> List[CsvPod]:
        return [
            CsvPod(self.name, self.set_string, self.link, self.house1, self.house1_sas,
                self.house1_cards, self.for_sale, self.for_auction, self.for_trade,
                self.price),
            CsvPod(self.name, self.set_string, self.link, self.house2, self.house2_sas,
                self.house2_cards, self.for_sale, self.for_auction, self.for_trade,
                self.price),
            CsvPod(self.name, self.set_string, self.link, self.house3, self.house3_sas,
                self.house3_cards, self.for_sale, self.for_auction, self.for_trade,
                self.price),
        ]


def parse_house_stats(decks_csv: IO, max_decks: int = 10) -> List[CsvPod]:
    csv_str = decks_csv.read().decode()
    decks_csv = io.StringIO(csv_str)
    reader = csv.reader(decks_csv, skipinitialspace=True)
    header = next(reader)
    rows_to_read = [header.index(title) for title in DeckFromCsv.ROWS_TO_READ]
    decks_done = 0
    pods = []
    for row in reader:
        deck = DeckFromCsv(*[row[x] for x in rows_to_read])
        pods.extend(deck.as_pods())
        decks_done += 1
        if decks_done >= max_decks:
            break
    sorted_pods = sorted(pods, key=operator.attrgetter("sas"), reverse=True)
    return sorted_pods


def house_stats_to_csv(pods: List[CsvPod]) -> IO:
    f = io.StringIO()
    writer = csv.writer(f)
    writer.writerow(pods[0].headers())
    for pod in pods:
        writer.writerow(pod.as_row())
    return io.BytesIO(f.getvalue().encode())


class MVApi:
    def __init__(self, seconds_per_call: float = 5.0):
        self.lock = asyncio.Lock()
        self.lock_sync = threading.Lock()
        self.last_call_time = 0.0
        self.seconds_per_call = seconds_per_call

    def callMVSync(self, *args, **kwargs):
        with self.lock_sync:
            time_since_last_call = time.time() - self.last_call_time
            time_to_sleep = max(0.0, self.seconds_per_call - time_since_last_call)
            time.sleep(time_to_sleep)
            self.last_call_time = time.time()
            response = requests.get(*args, **kwargs)
            return response

    async def callMV(self, *args, **kwargs):
        async with self.lock:
            time_since_last_call = time.time() - self.last_call_time
            time_to_sleep = max(0.0, self.seconds_per_call - time_since_last_call)
            await asyncio.sleep(time_to_sleep)
            self.last_call_time = time.time()
            response = await arequests.get(*args, **kwargs)
            return response


mv_api = MVApi(1.0)


class CantAnonymize(Exception):
    pass


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


class MissingEnhancements(Exception):
    pass


class RequestThrottled(Exception):
    pass


class InternalServerError(Exception):
    pass


def load_config() -> Dict[str, str]:
    config = {"DEBUG": True}
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
    current_app.logger.debug(f"Starting to parse log with {len(lines)} lines.")
    cursor = iter(lines)
    player_infos = {}
    try:
        current_app.logger.debug("Looking for players!")
        count = 1
        while len(player_infos) < 2:
            line = next(cursor)
            count += 1
            m = PLAYER_DECK_MATCHER.match(line)
            if m:
                current_app.logger.debug(
                    f"Found player {m.group(1)} with deck {m.group(2)}"
                )
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
                current_app.logger.debug(f"Found first player: {m.group(1)}")
                player_infos[m.group(1)].first_player = True
                first_player = m.group(1)
    except StopIteration:
        raise BadLog("Could not determine first player from log")
    try:
        while not line.startswith("Key phase"):
            line = next(cursor)
            m = SHUFFLE_MATCHER.match(line)
            if m:
                current_app.logger.debug("Found first turn")
                player_infos[m.group(1)].shuffles += 1
    except StopIteration:
        raise BadLog("Could not find first turn start")
    try:
        while True:
            line = next(cursor)
            m = HOUSE_CHOICE_MATCHER.match(line)
            if m:
                current_app.logger.debug(f"{m.group(1)} picked {m.group(2)}")
                player_infos[m.group(1)].house_counts[m.group(2)] += 1
                continue
            m = FORGE_MATCHER.match(line)
            if m:
                current_app.logger.debug(f"{m.group(1)} forged for {m.group(3)}")
                player_infos[m.group(1)].keys_forged += 1
                player_infos[m.group(1)].key_costs.append(int(m.group(3)))
                continue
            m = WIN_MATCHER.match(line)
            if m:
                current_app.logger.debug(f"{m.group(1)} won")
                player_infos[m.group(1)].winner = True
                break
    except StopIteration:
        raise BadLog("Could not determine game winner from log")
    for player in player_infos.values():
        if player.winner:
            winner_info = player
        else:
            loser_info = player
    winner_name = winner_info.player_name
    loser_name = loser_info.player_name
    winner_deck = get_deck_by_name_with_zeal(winner_info.deck_name)
    loser_deck = get_deck_by_name_with_zeal(loser_info.deck_name)
    current_app.logger.debug(f"Winning deck: {winner_deck.name}")
    current_app.logger.debug(f"Losing deck: {loser_deck.name}")
    winner = username_to_player(winner_name)
    loser = username_to_player(loser_name)
    first_player_obj = winner if first_player == winner_name else loser
    game = Game(
        first_player=first_player,
        first_player_id=first_player_obj.id,
        winner=winner_name,
        winner_id=winner.id,
        winner_deck=winner_deck,
        winner_deck_id=winner_deck.kf_id,
        winner_deck_name=winner_deck.name,
        winner_keys=winner_info.keys_forged,
        loser=loser_name,
        loser_id=loser.id,
        loser_deck=loser_deck,
        loser_deck_id=loser_deck.kf_id,
        loser_deck_name=loser_deck.name,
        loser_keys=loser_info.keys_forged,
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


def get_deck_by_id_with_zeal(deck_id: str, sas_rating=None, aerc_score=None) -> Deck:
    current_app.logger.debug("Checking for deck in db")
    deck = Deck.query.filter_by(kf_id=deck_id).first()
    if deck is None:
        deck = Deck(kf_id=deck_id)
        refresh_deck_from_mv(deck)
        if sas_rating and aerc_score:
            deck.sas_rating = sas_rating
            deck.aerc_score = aerc_score
            deck.sas_version = LATEST_SAS_VERSION
        else:
            update_sas_scores(deck)
        db.session.add(deck)
        db.session.commit()
        db.session.refresh(deck)
        return deck
    if (
        not deck.dok
        or deck.dok.last_refresh is None
        or datetime.datetime.utcnow() - deck.dok.last_refresh > SAS_TD
    ):
        update_sas_scores(deck)
    if len(deck.cards_from_assoc) == 0:
        refresh_deck_from_mv(deck)
        db.session.refresh(deck)
    if len(deck.pod_stats) == 0:
        calculate_pod_stats(deck)
        db.session.commit()
        db.session.refresh(deck)
    return deck


def loop_loading_missed_sas(batch_size: int, max_set_id: int = 700) -> None:
    q = Deck.query.filter(and_(Deck.expansion<max_set_id, Deck.dok==None))
    query_times = []
    while q.count() > 0:
        current_app.logger.info(f"{q.count()} decks left. Fetching {batch_size} to process.")
        decks = q.limit(batch_size).all()
        while decks:
            deck = decks.pop()
            query_times = [qt for qt in query_times if time.time() - qt < 60]
            if len(query_times) > 45:
                oldest = min(query_times)
                to_sleep = 1 + time.time() - oldest
                current_app.logger.debug(f"Sleeping {to_sleep}")
                time.sleep(to_sleep)
            update_sas_scores(deck)
            query_times.append(time.time())
            db.session.commit()
            count = len(decks)
            if count % 25 == 0:
                current_app.logger.info(f"{count} left in this batch")


def refresh_deck_from_mv(deck: Deck, card_cache: Dict = None) -> None:
    if card_cache is None:
        card_cache = {}
    deck_url = os.path.join(MV_API_BASE, "v2", deck.kf_id)
    response = mv_api.callMVSync(
        deck_url,
        params={"links": "cards,notes"},
    )
    all_data = response.json()
    data = all_data["data"]
    card_json = all_data["_linked"]["cards"]
    card_details = {c["id"]: c for c in card_json}
    add_one_deck_v2(data, card_details, deck=deck)


def get_deck_by_name_with_zeal(deck_name: str) -> Deck:
    deck = Deck.query.filter_by(name=deck_name).first()
    if deck is None:
        deck_id = deck_name_to_id(deck_name)
        deck = get_deck_by_id_with_zeal(deck_id)
    return deck


def update_sas_scores(deck: Deck) -> bool:
    """Returns True if update occurred."""
    if (
        (deck.sas_version or 0) >= LATEST_SAS_VERSION
        and deck.dok
        and deck.dok.last_refresh is not None
        and datetime.datetime.utcnow() - deck.dok.last_refresh < SAS_TD
    ):
        return False
    url = os.path.join(DOK_DECK_BASE, deck.kf_id)
    response = requests.get(url, headers=DOK_HEADERS)
    data = response.json()
    try:
        deck.sas_rating = data["deck"]["sasRating"]
        deck.aerc_score = data["deck"]["aercScore"]
        deck.sas_version = data["sasVersion"]
        add_dok_deck_from_dict(**data["deck"])
    except KeyError:
        current_app.logger.exception(f"Failed getting dok data for {deck.kf_id}")
        current_app.logger.debug(f"Received text:\n{response.text}")
    return True


def deck_name_to_id(deck_name: str) -> str:
    search_params = {"search": deck_name}
    response = mv_api.callMVSync(MV_API_BASE, params=search_params)
    data = response.json()
    if not data["data"]:
        raise DeckNotFoundError(f"Found no decks with name {deck_name}")
    if len(data["data"]) > 1:
        for deck in data["data"]:
            if deck["name"] == deck_name:
                return deck["id"]
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
    winner_name = kwargs.get("winner")
    winner_deck_id = kwargs.get("winner_deck_id")
    winner_deck_name = kwargs.get("winner_deck_name")
    winner = username_to_player(winner_name)
    loser_name = kwargs.get("loser")
    loser_deck_id = kwargs.get("loser_deck_id")
    loser_deck_name = kwargs.get("loser_deck_name")
    loser = username_to_player(loser_name)
    first_player = kwargs.get(kwargs.get("first_player"))
    if first_player == "winner":
        first_player_name = winner_name
        first_player_obj = winner
    else:
        first_player_name = loser_name
        first_player_obj = loser
    if winner_deck_id:
        # If urls were passed in, fix that now
        winner_deck_id = winner_deck_id.split("/")[-1]
        winner_deck = get_deck_by_id_with_zeal(winner_deck_id)
    else:
        if winner_deck_name:
            winner_deck = get_deck_by_name_with_zeal(winner_deck_name)
        else:
            raise MissingInput("Need name or id of winning deck")
    if loser_deck_id:
        # If urls were passed in, fix that now
        loser_deck_id = loser_deck_id.split("/")[-1]
        loser_deck = get_deck_by_id_with_zeal(loser_deck_id)
    else:
        if loser_deck_name:
            loser_deck = get_deck_by_name_with_zeal(loser_deck_name)
        else:
            raise MissingInput("Need name or id of losing deck")
    game = Game(
        crucible_game_id=crucible_game_id,
        date=date,
        first_player=first_player_name,
        first_player_id=first_player.id,
        winner=winner_name,
        winner_id=winner.id,
        winner_deck=winner_deck,
        winner_deck_id=winner_deck.kf_id,
        winner_deck_name=winner_deck.name,
        winner_keys=kwargs.get("winner_keys", 3),
        loser=loser_name,
        loser_id=loser.id,
        loser_deck=loser_deck,
        loser_deck_id=loser_deck.kf_id,
        loser_deck_name=loser_deck.name,
        loser_keys=kwargs.get("loser_keys"),
    )
    return game


def add_player_filters(
    query: Query,
    username: str = None,
    deck_id: str = None,
    deck_dbid: int = None,
    sas_min: int = None,
    sas_max: int = None,
    aerc_min: int = None,
    aerc_max: int = None,
) -> Query:
    if not any((username, deck_id, deck_dbid, sas_min, sas_max, aerc_min, aerc_max)):
        return query
    winner_filters = []
    loser_filters = []
    if username is not None:
        if "|" in username:
            winner_filters.append(Game.winner.in_(username.split("|")))
            loser_filters.append(Game.loser.in_(username.split("|")))
        else:
            winner_filters.append(Game.winner == username)
            loser_filters.append(Game.loser == username)
    if deck_id is not None:
        # Avoid subqueries by resolving "quickly" here
        deck = get_deck_by_id_with_zeal(deck_id)
        winner_filters.append(Game.winner_deck_dbid == deck.id)
        loser_filters.append(Game.loser_deck_dbid == deck.id)
    if deck_dbid is not None:
        winner_filters.append(Game.winner_deck_dbid == deck_dbid)
        loser_filters.append(Game.loser_deck_dbid == deck_dbid)
    if sas_min is not None:
        winner_filters.append(Game.winner_deck.has(Deck.sas_rating > sas_min))
        loser_filters.append(Game.loser_deck.has(Deck.sas_rating > sas_min))
    if sas_max is not None:
        winner_filters.append(Game.winner_deck.has(Deck.sas_rating < sas_max))
        loser_filters.append(Game.loser_deck.has(Deck.sas_rating < sas_max))
    if aerc_min is not None:
        winner_filters.append(Game.winner_deck.has(Deck.aerc_score > aerc_min))
        loser_filters.append(Game.loser_deck.has(Deck.aerc_score > aerc_min))
    if aerc_max is not None:
        winner_filters.append(Game.winner_deck.has(Deck.aerc_score < aerc_max))
        loser_filters.append(Game.loser_deck.has(Deck.aerc_score < aerc_max))
    query = query.filter(
        or_(
            and_(*winner_filters),
            and_(*loser_filters),
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


def randip() -> str:
    third = random.randint(1, 253)
    fourth = random.randint(1, 253)
    return f"192.168.{third}.{fourth}"


def turn_counts_from_logs(game: Game) -> None:
    counts = defaultdict(dict)
    players = {}
    for (i, log) in enumerate(game.logs):
        m = HOUSE_CHOICE_MATCHER.match(log.message)
        if m:
            username = m.group(1)
            house = getattr(House, m.group(2).upper()).name
            player = username_to_player(username)
            count = counts[username].get(house)
            if count is None:
                count = HouseTurnCounts(
                    game=game,
                    player=player,
                    house=house,
                    turns=0,
                    winner=player.username == game.winner,
                )
                counts[username][house] = count
            count.turns += 1
            continue
        n = HOUSE_MANUAL_MATCHER.match(log.message)
        if n:
            # This should be set from last hit on HOUSE_CHOICE_MATCHER
            count.turns -= 1
            username = n.group(1)
            house = getattr(House, n.group(2).upper()).name
            player = username_to_player(username)
            count = counts[username].get(house)
            if count is None:
                count = HouseTurnCounts(
                    game=game,
                    player=player,
                    house=house,
                    turns=0,
                    winner=player.username == game.winner,
                )
                counts[username][house] = count
            count.turns += 1
    for subdict in counts.values():
        for count in subdict.values():
            if count.turns > 0:
                db.session.add(count)
    db.session.commit()


def username_to_player(username: str) -> Player:
    player = Player.query.filter_by(username=username).first()
    if player is None:
        player = Player(username=username)
        db.session.add(player)
        return player
    if player.anonymous:
        return Player.query.filter_by(username="anonymous").first()
    else:
        return player


def anonymize_game_for_player(game: Game, player: Player) -> None:
    if not player.anonymous:
        raise CantAnonymize(f"{player.username} not anonymous")
    anon_player = Player.query.filter_by(username="anonymous").first()
    if game.winner == player.username or game.winner_id == player.id:
        game.winner = anon_player.username
        game.winner_id = anon_player.id
    elif game.loser == player.username or game.loser_id == player.id:
        game.loser = anon_player.username
        game.loser_id = anon_player.id
    else:
        raise CantAnonymize(f"{player.username} not found on game {game.id}")
    for count in game.house_turn_counts:
        if count.player == player:
            count.player = anon_player
    for log in game.logs:
        log.message = log.message.replace(player.username, anon_player.username)
    db.session.commit()


def anonymize_all_games_for_player(player: Player) -> None:
    if not player.anonymous:
        raise CantAnonymize(f"{player.username} not anonymous")
    games = Game.query.filter_by(
        or_(Game.winner == player.username, Game.loser == player.username)
    ).all()
    for game in games:
        anonymize_game_for_player(game, player)


def create_platonic_card(card: Card) -> PlatonicCard:
    card_type = card.card_type
    if card_type == "Creature1":
        card_type = "Creature"
    platonic_card = PlatonicCard(
        card_title=card.card_title,
        card_type=card_type_str_to_enum[card_type],
        front_image=card.front_image,
        card_text=card.card_text,
        amber=card.amber,
        power=card.power,
        armor=card.armor,
        flavor_text=card.flavor_text,
        is_non_deck=card.is_non_deck,
        house=house_str_to_enum[card.house],
    )
    db.session.add(platonic_card)
    if card.traits:
        trait_strs = card.traits.split(" • ")
        for trait_str in trait_strs:
            trait = Trait.query.filter_by(name=trait_str).first()
            if trait is None:
                trait = Trait(name=trait_str)
                db.session.add(trait)
            platonic_card.traits.append(trait)
    if card.expansion not in {x.expansion for x in platonic_card.expansions}:
        pc_in_set = PlatonicCardInSet(
            card=platonic_card,
            expansion=card.expansion,
            rarity=rarity_str_to_enum[card.rarity],
            card_number=card.card_number,
            is_anomaly=card.is_anomaly,
        )
    db.session.add(pc_in_set)
    return platonic_card


def retry_anything_once(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            current_app.logger.exception("Caught excepting in retry_anything_once")
            db.session.rollback()
            return func(*args, **kwargs)

    return wrapper


def retry_after_mysql_disconnect(func):
    def wrapper(*args, **kwargs):
        tries = 0
        while tries < 5:
            try:
                return func(*args, **kwargs)
            except (OperationalError, PendingRollbackError):
                current_app.logger.exception("Caught mysql error")
                db.session.rollback()
                tries += 1
        return func(*args, **kwargs)

    return wrapper


def get_snake_or_camel(obj: Dict[str, Any], key: str) -> Optional[str]:
    if key in obj:
        return obj[key]
    bits = key.split("_")
    new_key = bits[0] + "".join(ele.title() for ele in bits[1:])
    return obj.get(new_key)


def add_dok_deck_from_dict(skip_commit: bool = False, **data: Dict) -> None:
    deck_id = get_snake_or_camel(data, "keyforge_id")
    deck = Deck.query.filter_by(kf_id=deck_id).first()
    # This is a bit redundant to get_deck_by_id_with_zeal, but necessary to avoid an
    # infinite loop. ;)
    if deck is None:
        deck = Deck(kf_id=deck_id)
        refresh_deck_from_mv(deck)
    current_app.logger.debug(f"Adding dok deck data for {deck.name}")
    dok = DokDeck.query.filter_by(deck_id=deck.id).first()
    if dok is None:
        dok = DokDeck(deck=deck)
        db.session.add(dok)
    dok.sas_rating = get_snake_or_camel(data, "sas_rating")
    dok.synergy_rating = get_snake_or_camel(data, "synergy_rating")
    dok.antisynergy_rating = get_snake_or_camel(data, "antisynergy_rating")
    dok.aerc_score = get_snake_or_camel(data, "aerc_score")
    dok.amber_control = get_snake_or_camel(data, "amber_control")
    dok.expected_amber = get_snake_or_camel(data, "expected_amber")
    dok.artifact_control = get_snake_or_camel(data, "artifact_control")
    dok.creature_control = get_snake_or_camel(data, "creature_control")
    dok.efficiency = get_snake_or_camel(data, "efficiency")
    dok.recursion = get_snake_or_camel(data, "recursion")
    dok.disruption = get_snake_or_camel(data, "disruption")
    dok.creature_protection = get_snake_or_camel(data, "creature_protection")
    dok.other = get_snake_or_camel(data, "other")
    dok.effective_power = get_snake_or_camel(data, "effective_power")
    dok.raw_amber = get_snake_or_camel(data, "raw_amber")
    dok.action_count = get_snake_or_camel(data, "action_count")
    dok.upgrade_count = get_snake_or_camel(data, "upgrade_count")
    dok.creature_count = get_snake_or_camel(data, "creature_count")
    if not skip_commit:
        db.session.commit()


def calculate_pod_stats(deck: Deck) -> None:
    house_to_cards = defaultdict(list)
    for card in deck.cards_from_assoc:
        house_to_cards[card.house].append(card)
    for house, cards in house_to_cards.items():
        if house == House.THETIDE:
            continue
        enhancements, amber, capture, draw, damage = 0, 0, 0, 0, 0
        mutants, creatures, raw_amber = 0, 0, 0
        for card in cards:
            if any(trait.name == "mutant" for trait in card.traits):
                mutants += 1
            if card.card_type == CardType.CREATURE:
                creatures += 1
            raw_amber += card.amber
            amber += card.enhanced_amber
            capture += card.enhanced_capture
            draw += card.enhanced_draw
            damage += card.enhanced_damage
            enhancements += sum(
                [
                    card.enhanced_amber,
                    card.enhanced_capture,
                    card.enhanced_draw,
                    card.enhanced_damage,
                ]
            )
        for pod in deck.pod_stats:
            if pod.house == house:
                break
        else:
            pod = PodStats()
            db.session.add(pod)
        pod.house = house
        pod.deck = deck
        pod.enhanced_amber = amber
        pod.enhanced_capture = capture
        pod.enhanced_draw = draw
        pod.enhanced_damage = damage
        pod.num_enhancements = enhancements
        pod.num_mutants = mutants
        pod.creatures = creatures
        pod.raw_amber = raw_amber
        pod.total_amber = raw_amber + amber


def guess_deck_language(deck: Deck) -> None:
    guess = language_detector.detect_language_of(deck.name)
    if guess is None:
        deck.language = None
    else:
        deck.language = guess.name


async def get_decks_from_page(page: int) -> Iterable[str]:
    params = SEARCH_PARAMS.copy()
    params["page"] = page
    headers = {"X-Forwarded-For": randip()}
    response = await mv_api.callMV(MV_API_BASE, params=params, headers=headers)
    try:
        data = await response.json()
    except (json.decoder.JSONDecodeError, ContentTypeError):
        current_app.logger.error(f"raw response: {response}")
        raise
    if "code" in data:
        if data["code"] == 429:
            raise RequestThrottled(data["message"] + data["detail"])
        # "Internal Server Error" - means page does not exist
        elif data["code"] == 0:
            raise InternalServerError(data["message"] + data["detail"])
        else:
            logging.error(f"Unrecognized json response {data}")
    return [deck["id"] for deck in data["data"]]


def dump_page_json_to_file(
    page: int,
    reverse: bool,
    dest: str,
    tries: int = 5,
) -> None:
    params = SEARCH_PARAMS.copy()
    params["page"] = page
    params["links"] = "cards"
    if reverse:
        params["ordering"] = "date"
    else:
        params["ordering"] = "-date"
    api_base = os.path.join(MV_API_BASE, "v2/")
    response = mv_api.callMVSync(
        api_base,
        params=params,
        headers={"X-Forwarded-For": randip()},
    )
    finished = False
    while tries and not finished:
        tries -= 1
        try:
            data = response.json()
        except (json.decoder.JSONDecodeError, ContentTypeError):
            current_app.logger.error(f"raw response: {response}")
            if tries:
                time.sleep(random.choice(range(20, 40)))
                continue
            else:
                raise
        if "code" in data:
            if tries:
                current_app.logger.error(f"Got error, retrying: {data['message'] + data['detail']}")
                time.sleep(random.choice(range(20, 40)))
                continue
            if data["code"] == 429:
                raise RequestThrottled(data["message"] + data["detail"])
            # "Internal Server Error" - means page does not exist
            elif data["code"] == 0:
                raise InternalServerError(data["message"] + data["detail"])
            else:
                current_app.logger.error(f"Unrecognized json response {data}")
                raise Exception()
        else:
            finished = True
    with open(os.path.join(dest, f"{page}.json"), "w") as fh:
        json.dump(data, fh)



def get_decks_from_page_v2(
    page: int,
    reverse: bool,
    add_decks_cache=None,
    tries: int = 5,
    update_highest_page: bool = False,
) -> int:
    # MV api will not return more than 25, so don't try
    page_size = 25
    params = SEARCH_PARAMS.copy()
    params = {
        "page": page,
        "links": "cards",
        "page_size": page_size,
    }
    if reverse:
        params["ordering"] = "date"
    else:
        params["ordering"] = "-date"
    api_base = os.path.join(MV_API_BASE, "v2/")
    response = mv_api.callMVSync(
        api_base,
        params=params,
        headers={"X-Forwarded-For": randip()},
    )
    finished = False
    while tries and not finished:
        tries -= 1
        try:
            data = response.json()
        except (json.decoder.JSONDecodeError, ContentTypeError):
            current_app.logger.error(f"raw response: {response}")
            if tries:
                time.sleep(random.choice(range(20, 40)))
                continue
            else:
                raise
        if "code" in data:
            if tries:
                current_app.logger.error(f"Got error, retrying: {data['message'] + data['detail']}")
                time.sleep(random.choice(range(20, 40)))
                continue
            if data["code"] == 429:
                raise RequestThrottled(data["message"] + data["detail"])
            # "Internal Server Error" - means page does not exist
            elif data["code"] == 0:
                raise InternalServerError(data["message"] + data["detail"])
            else:
                current_app.logger.error(f"Unrecognized json response {data}")
                raise Exception()
        else:
            finished = True
    decks = data["data"]
    cards = data["_linked"]["cards"]
    card_details = {c["id"]: c for c in cards}
    existing_decks = Deck.query.filter(Deck.kf_id.in_([d["id"] for d in decks])).all()
    id_to_existing_deck = {deck.kf_id: deck for deck in existing_decks}
    new_decks = len(decks) - len(existing_decks)
    for deck_json in decks:
        if deck_json["id"] not in add_decks_cache["seen_deck_ids"]:
            existing_deck = id_to_existing_deck.get(deck_json["id"])
            add_one_deck_v2(deck_json, card_details, add_decks_cache, existing_deck)
            add_decks_cache["seen_deck_ids"].add(deck_json["id"])
    if update_highest_page and reverse and len(decks) == page_size:
        highest_page = GlobalVariable.query.filter_by(name="highest_mv_page_scraped").first()
        if page > highest_page.value_int:
            highest_page.value_int = page
            db.session.commit()
    return new_decks


def add_one_deck_v2(deck_json, card_details, add_decks_cache=None, deck: Deck = None) -> int:
    new_deck = False
    if deck is None:
        deck = Deck(kf_id=deck_json["id"])
        db.session.add(deck)
        new_deck = True
    deck.name = deck_json["name"]
    deck.expansion = deck_json["expansion"]
    bonus_icons = deck_json["bonus_icons"]
    houses = deck_json["_links"]["houses"]
    deck_card_ids = deck_json["_links"]["cards"]
    deck_str = f"{deck.name} - https://keyforgegame.com/deck-details/{deck.kf_id}"
    if new_deck:
        current_app.logger.debug(f"Adding cards to {deck_str}")
        add_cards_v2_new(deck, deck_card_ids, card_details, bonus_icons)
    else:
        res = are_cards_okay(deck, deck_card_ids, card_details, bonus_icons)
        if res:
            current_app.logger.debug(f"Existing deck is ok: {deck_str}")
        else:
            current_app.logger.debug(f"Clearing and re-adding cards for {deck_str}")
            deck.cards_from_assoc.clear()
            add_cards_v2_new(deck, deck_card_ids, card_details, bonus_icons, add_decks_cache)
    db.session.commit()
    return 1 if new_deck else 0


def are_cards_okay(
    deck: Deck,
    deck_card_ids: List[str],
    card_details,
    bonus_icons,
) -> bool:
    cards = [c for c in deck.cards_from_assoc]
    for card_id in deck_card_ids:
        for card in cards:
            if card_id == card.card_kf_id:
                break
        else:
            current_app.logger.debug(f"Did not find card {card_id} in db deck")
            return False
        cards.remove(card)
        card_json = card_details[card_id]
        if card_json["card_type"] == "Creature1":
            card_json["card_type"] = "Creature"
        # Check straight strings
        if (
            card.card_title != card_json["card_title"]
            or card.front_image != card_json["front_image"]
            or card.card_text != card_json["card_text"]
            or card.amber != int(card_json["amber"])
            or card.power != int(0 if card_json["power"] in ("X", None) else card_json["power"])
            or card.armor != int(0 if card_json["armor"] in ("X", None) else card_json["armor"])
            or card.flavor_text != card_json["flavor_text"]
            or card.card_number != card_json["card_number"]
            or card.expansion != card_json["expansion"]
            or card.is_maverick != card_json["is_maverick"]
            or card.is_anomaly != card_json["is_anomaly"]
            or card.is_enhanced != card_json["is_enhanced"]
            or card.is_non_deck != card_json["is_non_deck"]
        ):
            current_app.logger.debug("Found mismatch in simple strings")
            if card.card_title != card_json["card_title"]:
                current_app.logger.debug(f"card_title: {diff_strings(card.card_title, card_json['card_title'])}")
            if card.front_image != card_json["front_image"]:
                current_app.logger.debug(f"front_image: {diff_strings(card.front_image, card_json['front_image'])}")
            if card.card_text != card_json["card_text"]:
                current_app.logger.debug(f"card_text: {diff_strings(card.card_text, card_json['card_text'])}")
            if card.amber != card_json["amber"]:
                current_app.logger.debug(f"amber: {card.amber} vs {card_json['amber']}")
            if card.power != normalize_stat(card_json["power"]):
                current_app.logger.debug(f"power: {card.power} vs {card_json['power']}")
            if card.armor != normalize_stat(card_json["armor"]):
                current_app.logger.debug(f"armor: {card.armor} vs {card_json['armor']}")
            if card.flavor_text != card_json["flavor_text"]:
                current_app.logger.debug(f"flavor_text: {card.flavor_text} vs {card_json['flavor_text']}")
            if card.card_number != card_json["card_number"]:
                current_app.logger.debug(f"card_number: {card.card_number} vs {card_json['card_number']}")
            if card.expansion != card_json["expansion"]:
                current_app.logger.debug(f"expansion: {card.expansion} vs {card_json['expansion']}")
            if card.is_maverick != card_json["is_maverick"]:
                current_app.logger.debug(f"is_maverick: {card.is_maverick} vs {card_json['is_maverick']}")
            if card.is_anomaly != card_json["is_anomaly"]:
                current_app.logger.debug(f"is_anomaly: {card.is_anomaly} vs {card_json['is_anomaly']}")
            if card.is_enhanced != card_json["is_enhanced"]:
                current_app.logger.debug(f"is_enhanced: {card.is_enhanced} vs {card_json['is_enhanced']}")
            if card.is_non_deck != card_json["is_non_deck"]:
                current_app.logger.debug(f"is_non_deck: {card.is_non_deck} vs {card_json['is_non_deck']}")
            return False
        # Check enums
        if (
            card.card_type != card_type_str_to_enum[card_json["card_type"]]
            or card.house != house_str_to_enum[card_json["house"]]
            or card.rarity != rarity_str_to_enum[card_json["rarity"]]
        ):
            current_app.logger.debug("Found mismatch in enums")
            return False
        # Check traits
        if card_json["traits"] and {t.name for t in card.traits} != set(card_json["traits"].split(" • ")):
            current_app.logger.debug("Found mismatch in traits")
            return False
        return True


def diff_strings(a: str, b: str) -> str:
    msg =[f"{a} => {b}"]
    for i, s in enumerate(difflib.ndiff(a, b)):
        if s[0] == " ":
            continue
        elif s[0] == "0":
            msg.append(f"Delete \"{s[-1]}\" from position {i}")
        elif s[0] == "+":
            msg.append(f"Add \"{s[-1]}\" to position {i}")
    return "\n".join(msg)


def add_cards_v2_new(
    deck: Deck,
    deck_card_ids: List[str],
    card_details,
    bonus_icons,
    add_decks_cache=None,
) -> None:
    if add_decks_cache is None:
        add_decks_cache = defaultdict(dict)
    for card_id in deck_card_ids:
        card_json = card_details[card_id]
        if card_json["card_title"] == "Archon's Callback":
            card_json["card_title"] = "Archon’s Callback"
        if card_json["card_type"] == "Creature1":
            card_json["card_type"] = "Creature"
        # Tack "Evil" onto the beginning of the card title for evil twin cards
        if card_json["rarity"] == "Evil Twin":
            card_json["card_title"] = "Evil " + card_json["card_title"]
        pcis = add_decks_cache["card_in_set"].get(card_id)
        if pcis is None:
            pcis = PlatonicCardInSet.query.filter_by(card_kf_id=card_id).first()
        if pcis is None:
            current_app.logger.info(
                f"Creating new card in set: {card_json['expansion']}:{card_json['card_title']}"
                f":{card_json['house']}:{card_json['id']}"
            )
            pc = add_decks_cache["platonic_card"].get(card_json["card_title"])
            if pc is None:
                pc = PlatonicCard.query.filter_by(card_title=card_json["card_title"]).first()
            if pc is None:
                current_app.logger.info(
                    f"Creating new platonic card: {card_json['card_title']}"
                )
                pc = PlatonicCard(
                    card_title=card_json["card_title"],
                )
                db.session.add(pc)
            pcis = PlatonicCardInSet(
                card=pc,
                card_kf_id=card_json["id"],
                expansion=card_json["expansion"],
            )
            db.session.add(pcis)
        else:
            pc = pcis.card
        add_decks_cache["card_in_set"]["card_id"] = pcis
        add_decks_cache["platonic_card"][card_json["card_title"]] = pc
        update_platonic_info(pc, pcis, card_json)
        card = CardInDeck(
            platonic_card=pc,
            card_in_set=pcis,
            deck=deck,
            house=house_str_to_enum[card_json["house"]],
            is_enhanced=card_json["is_enhanced"],
            enhanced_amber=0,
            enhanced_capture=0,
            enhanced_draw=0,
            enhanced_damage=0,
            enhanced_discard=0,
        )
        db.session.add(card)
        if card.is_enhanced:
            bling = copy.deepcopy(bonus_icons)
            for (idx, enh) in enumerate(bling):
                if enh["card_id"] == pcis.card_kf_id:
                    for icon in enh["bonus_icons"]:
                        if icon == "damage":
                            card.enhanced_damage += 1
                        elif icon == "amber":
                            card.enhanced_amber += 1
                        elif icon == "draw":
                            card.enhanced_draw += 1
                        elif icon == "capture":
                            card.enhanced_capture += 1
                        elif icon == "discard":
                            card.enhanced_discard += 1
                        else:
                            raise MissingEnhancements(f"Could not pair enhancements in {deck.kf_id}")
                    break
            else:
                raise MissingEnhancements(f"Could not pair enhancements in {deck.kf_id}")
        db.session.commit()


def normalize_stat(stat: Optional[str]) -> int:
    if stat in ("X", None):
        return 0
    else:
        return int(stat)
            

def update_platonic_info(
    platonic_card: PlatonicCard,
    card_in_set: PlatonicCardInSet,
    card_json,
) -> None:
    # Double-check that platonic card info is right
    if card_json["traits"]:
        trait_strs = card_json["traits"].split(" • ")
        if {t.name for t in platonic_card.traits} != set(trait_strs):
            platonic_card.traits.clear()
            for trait_str in trait_strs:
                trait = Trait.query.filter_by(name=trait_str).first()
                if trait is None:
                    current_app.logger.info(f"Adding new trait: {trait_str}")
                    trait = Trait(name=trait_str)
                    db.session.add(trait)
                platonic_card.traits.append(trait)
    else:
        platonic_card.traits.clear()
    platonic_card.card_type = card_type_str_to_enum[card_json["card_type"]]
    platonic_card.front_image = card_json["front_image"]
    platonic_card.card_text = card_json["card_text"]
    platonic_card.amber = int(card_json["amber"])
    platonic_card.power = normalize_stat(card_json["power"])
    platonic_card.armor = normalize_stat(card_json["armor"])
    platonic_card.flavor_text = card_json["flavor_text"]
    # Don't set platonic card house for mavericks, anomalies, or revenants
    if not any([
        card_json["is_maverick"],
        card_json["is_anomaly"],
        # This actuall should cover all revenants
        card_json["card_number"].startswith("R"),
        card_json["card_title"] in MM_UNHOUSED_CARDS + REVENANTS,
    ]):
        platonic_card.house = house_str_to_enum[card_json["house"]]
    platonic_card.is_non_deck = card_json["is_non_deck"]
    # Double-check that card in set info is right
    card_in_set.expansion = card_json["expansion"]
    card_in_set.rarity = rarity_str_to_enum[card_json["rarity"]]
    card_in_set.card_number = card_json["card_number"]
    card_in_set.is_anomaly = card_json["is_anomaly"]
    card_in_set.front_image = card_json["front_image"]
