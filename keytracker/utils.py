from collections import Counter, defaultdict
import configparser
import copy
import datetime
from keytracker.schema import (
    db,
    Card,
    CardInDeck,
    CardType,
    Deck,
    DokDeck,
    Enhancements,
    Game,
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
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple
import random
import requests

# from aiohttp_requests import requests as arequests
# from aiohttp.client_exceptions import ContentTypeError
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

MV_API_BASE = "http://www.keyforgegame.com/api/decks"

DOK_HEADERS = {"Api-Key": os.environ.get("DOK_API_KEY")}
DOK_DECK_BASE = "https://decksofkeyforge.com/public-api/v3/decks"
LATEST_SAS_VERSION = 43
SAS_MAX_AGE_DAYS = 90
SAS_TD = datetime.timedelta(days=SAS_MAX_AGE_DAYS)
SEARCH_PARAMS = {
    "page_size": 25,
    "search": "",
    "power_level": "0,11",
    "chains": "0,24",
    "ordering": "-date",
}

language_detector = LanguageDetectorBuilder.from_languages(*POSSIBLE_LANGUAGES).build()


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


def refresh_deck_from_mv(deck: Deck, card_cache: Dict = None) -> None:
    if card_cache is None:
        card_cache = {}
    deck_url = os.path.join(MV_API_BASE, deck.kf_id)
    response = mv_api.callMVSync(
        deck_url,
        params={"links": "cards, notes"},
        headers={"X-Forwarded-For": randip()},
    )
    all_data = response.json()
    data = all_data["data"]
    deck.name = data["name"]
    deck.expansion = data["expansion"]
    card_data_by_id = {c["id"]: c for c in all_data["_linked"]["cards"]}
    cards = []
    for card_id in data["_links"]["cards"]:
        card = card_cache.get(card_id)
        if card is None:
            card = Card.query.filter_by(kf_id=card_id).first()
            card_cache[card_id] = card
        if card is None:
            card_dict = card_data_by_id[card_id].copy()
            current_app.logger.debug(f"Adding card {card_dict['card_title']}")
            card_dict.pop("id")
            card_dict["kf_id"] = card_id
            card = Card(**card_dict)
            db.session.add(card)
            db.session.commit()
            db.session.refresh(card)
            card_cache[card_id] = card
        cards.append(card)
    bonus_icons = all_data["data"]["bonus_icons"]
    kf_id_to_card = {card.kf_id: card for card in cards}
    enhancements_list = []
    for spec in bonus_icons:
        card = kf_id_to_card[spec["card_id"]]
        icons = Counter(spec["bonus_icons"])
        enhancements = Enhancements(card=card, deck=deck, **icons)
        enhancements_list.append(enhancements)
    populate_enhanced_cards(deck, cards, enhancements_list)
    db.session.commit()


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


def populate_enhanced_cards(
    deck: Deck,
    cards: List[Card],
    enhancements: List[Enhancements],
    platonic_card_cache=None,
) -> None:
    deck.cards_from_assoc.clear()
    platonic_card_cache = platonic_card_cache or {}
    for card in cards:
        platonic_card = platonic_card_cache.get(card.card_title)
        if platonic_card is None:
            platonic_card = PlatonicCard.query.filter_by(
                card_title=card.card_title
            ).first()
            platonic_card_cache[card.card_title] = platonic_card
        if platonic_card is None:
            platonic_card = create_platonic_card(card)
            platonic_card_cache[card.card_title] = platonic_card
        card_in_deck = CardInDeck(
            platonic_card=platonic_card,
            deck=deck,
            house=house_str_to_enum[card.house],
            is_enhanced=card.is_enhanced,
        )
        db.session.add(card_in_deck)
        if card_in_deck.is_enhanced:
            for (idx, bling) in enumerate(enhancements):
                if bling.card_id == card.id:
                    card_in_deck.enhanced_amber = bling.amber
                    card_in_deck.enhanced_capture = bling.capture
                    card_in_deck.enhanced_draw = bling.draw
                    card_in_deck.enhanced_damage = bling.damage
                    enhancements.pop(idx)
                    break
            else:
                raise MissingEnhancements(
                    f"Could not successfully pair enhancements in {deck.id}"
                )
    db.session.commit()


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
    current_app.logger.debug(data)
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
