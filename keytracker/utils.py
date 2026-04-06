import csv
from collections import Counter, defaultdict
import configparser
import copy
from dataclasses import dataclass
import datetime
import difflib
import io
from keytracker.schema import (
    db,
    AllianceDeck,
    Card,
    CardInDeck,
    Deck,
    DeckLanguage,
    DokDeck,
    Enhancements,
    Game,
    GlobalVariable,
    HouseEnhancement,
    HouseTurnCounts,
    KeyforgeCardType,
    KeyforgeHouse,
    KeyforgeSet,
    KeyforgeRarity,
    PlatonicCard,
    PlatonicCardInSet,
    Player,
    PodStats,
    POSSIBLE_LANGUAGES,
    Trait,
    UserAllianceCollection,
    UserDeckCollection,
)
import operator
import os
from typing import Any, Dict, IO, Iterable, List, Optional, Tuple
import random
import requests

# from aiohttp_requests import requests as arequests
# from aiohttp.client_exceptions import ContentTypeError
import re
import sqlalchemy
from sqlalchemy import and_, or_
from sqlalchemy.exc import (
    OperationalError,
    PendingRollbackError,
)
from sqlalchemy.orm import Query
from flask import current_app
import json
import time
import threading

# from lingua import LanguageDetectorBuilder


@dataclass
class CardSetHouseOverride:
    """Class for representing an override for cards whose natural house is different in
    a newer set
    """

    card_title: str
    expansion: int
    house: str


CARD_SET_HOUSE_OVERRIDES = [
    CardSetHouseOverride("Armageddon Cloak", 855, "Redemption"),
    CardSetHouseOverride("Avenging Aura", 855, "Redemption"),
    CardSetHouseOverride("Book of Malefaction", 855, "Redemption"),
    CardSetHouseOverride("Eye of Judgment", 855, "Redemption"),
    CardSetHouseOverride("Hymn to Duma", 855, "Redemption"),
    CardSetHouseOverride("Johnny Longfingers", 855, "Redemption"),
    CardSetHouseOverride("Lord Golgotha", 855, "Redemption"),
    CardSetHouseOverride("Mantle of the Zealot", 855, "Redemption"),
    CardSetHouseOverride("Martyr's End", 855, "Redemption"),
    CardSetHouseOverride("Master of the Grey", 855, "Redemption"),
    CardSetHouseOverride("Mighty Lance", 855, "Redemption"),
    CardSetHouseOverride("One Stood Against Many", 855, "Redemption"),
    CardSetHouseOverride("Rogue Ogre", 855, "Redemption"),
    CardSetHouseOverride("The Promised Blade", 855, "Redemption"),
    CardSetHouseOverride("Champion Tabris", 855, "Redemption"),
    CardSetHouseOverride("Dark Centurion", 855, "Redemption"),
    CardSetHouseOverride("First or Last", 855, "Redemption"),
    CardSetHouseOverride("Francus", 855, "Redemption"),
    CardSetHouseOverride("Glorious Few", 855, "Redemption"),
    CardSetHouseOverride("Gorm of Omm", 855, "Redemption"),
    CardSetHouseOverride("Grey Abbess", 855, "Redemption"),
    CardSetHouseOverride("Professor Terato", 855, "Redemption"),
    CardSetHouseOverride("Scrivener Favian", 855, "Redemption"),
    CardSetHouseOverride("Bordan the Redeemed", 855, "Redemption"),
    CardSetHouseOverride("Bull-Wark", 855, "Redemption"),
    CardSetHouseOverride("Burning Glare", 855, "Redemption"),
    CardSetHouseOverride("Citizen Shrix", 855, "Redemption"),
    CardSetHouseOverride("Retribution", 855, "Redemption"),
    CardSetHouseOverride("Shifting Battlefield", 855, "Redemption"),
    CardSetHouseOverride("Snarette", 855, "Redemption"),
    CardSetHouseOverride("Subtle Otto", 855, "Redemption"),
    CardSetHouseOverride("Even Ivan", 855, "Redemption"),
    CardSetHouseOverride("Odd Clawde", 855, "Redemption"),
    CardSetHouseOverride("Sacro-Alien", 855, "Redemption"),
    CardSetHouseOverride("Sacro-Beast", 855, "Redemption"),
    CardSetHouseOverride("Sacro-Bot", 855, "Redemption"),
    CardSetHouseOverride("Sacro-Fiend", 855, "Redemption"),
    CardSetHouseOverride("Sacro-Saurus", 855, "Redemption"),
    CardSetHouseOverride("Sacro-Thief", 855, "Redemption"),
]
CARD_EXP_TO_OVERRIDE = {
    (x.card_title, x.expansion): x for x in CARD_SET_HOUSE_OVERRIDES
}


VALID_HOUSE_ENHANCEMENTS = [
    "brobnar",
    "dis",
    "ekwidon",
    "geistoid",
    "logos",
    "mars",
    "redemption",
    "sanctum",
    "saurian",
    "shadows",
    "skyborn",
    "star alliance",
    "unfathomable",
    "untamed",
]
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
CONNECTED_MATCHER = re.compile(r"^(.*) has connected to the game server")
CARD_PLAY_MATCHER = re.compile(r"^(\S+) plays (.+)$")
ATTACHING_SUFFIX_RE = re.compile(r"\s+attaching\s+it\s+to\s+.+$")

# Log house names may differ from DB house names (e.g. no spaces)
LOG_HOUSE_NAME_MAP = {
    "staralliance": "star alliance",
}


def _normalize_log_house(name: str) -> str:
    return LOG_HOUSE_NAME_MAP.get(name.lower(), name.lower())


MV_API_BASE = "https://www.keyforgegame.com/api/decks"
# Base URL for single-deck fetches. Override with MV_SINGLE_DECK_BASE to use a
# caching proxy (e.g. http://mvproxy.us-west-2.elasticbeanstalk.com/api/master-vault/decks).
# The collector page-scraping always uses MV_API_BASE directly.
MV_SINGLE_DECK_BASE = os.environ.get("MV_SINGLE_DECK_BASE", MV_API_BASE)

DOK_HEADERS = {"Api-Key": os.environ.get("DOK_API_KEY")}
PROD_DOK_BASE = "https://decksofkeyforge.com"
_DOK_BASE = os.environ.get("DOK_BASE_URL", PROD_DOK_BASE)
DOK_DECK_BASE = f"{_DOK_BASE}/public-api/v3/decks"
DOK_ALLIANCE_BASE = f"{_DOK_BASE}/api/alliance-decks/with-synergies"
TRY_LOCAL_DOK_FOR_DECK_BASE_DATA = os.environ.get(
    "TRY_LOCAL_DOK_FOR_DECK_BASE_DATA", ""
).lower() in ("1", "true", "yes")
LOCAL_DOK_URL = os.environ.get("LOCAL_DOK_URL", "http://localhost:5000")

# Maps DoK expansion enum name → MV integer expansion ID
_DOK_EXPANSION_TO_INT = {
    "CALL_OF_THE_ARCHONS": 341,
    "AGE_OF_ASCENSION": 435,
    "WORLDS_COLLIDE": 452,
    "ANOMALY_EXPANSION": 453,
    "MASS_MUTATION": 479,
    "DARK_TIDINGS": 496,
    "WINDS_OF_EXCHANGE": 600,
    "UNCHAINED_2022": 601,
    "VAULT_MASTERS_2023": 609,
    "GRIM_REMINDERS": 700,
    "MENAGERIE_2024": 722,
    "VAULT_MASTERS_2024": 737,
    "AEMBER_SKIES": 800,
    "TOKENS_OF_CHANGE": 855,
    "MORE_MUTATION": 874,
    "PROPHETIC_VISIONS": 886,
    "MARTIAN_CIVIL_WAR": 892,
    "DISCOVERY": 907,
    "CRUCIBLE_CLASH": 918,
    "VAULT_MASTERS_2025": 939,
}
LATEST_SAS_VERSION = 44  # bumped to backfill per-pod SAS
SAS_MAX_AGE_DAYS = 60
SAS_TD = datetime.timedelta(days=SAS_MAX_AGE_DAYS)
SEARCH_PARAMS = {
    "page_size": 25,
    "ordering": "-date",
}

# language_detector = LanguageDetectorBuilder.from_languages(*POSSIBLE_LANGUAGES).build()

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
GG_ALLIANCE_RESTRICTED_LIST = {
    "Befuddle",
    "Chronus",
    "Control the Weak",
    "Dark Æmber Vault",
    "FOF Transponder",
    "Ghostform",
    "Hallafest",
    "Infurnace",
    "Legionary Trainer",
    "Library Access",
    "Martian Generosity",
    "Stealth Mode",
    "Timetraveller",
    "United Action",
}
KEY_CHEATS_STRICT = {
    "Keyfrog",
    "Desire",
    "[REDACTED]",
    "Obsidian Forge",
    "Data Forge",
    "Forging an Alliance",
    "Epic Quest",
    "Dark Discovery",
    "Honors Keysis",
    "Imperial Forge",
    "The Colosseum",
    "Chota Hazri",
    "Nightforge",
    "Key Charge",
    "Key of Darkness",
    "Key Abduction",
    "Might Makes Right",
    "Triumph",
    "Token of Appreciation",
    "Blorb Hive",
    "Ecto-Charge",
    "Spoo-key Charge",
    "Revived Ză-Orhă",
    "Legendary Keyraken",
    "Red Æmberdrake",
    "Blue Æmberdrake",
    "Yellow Æmberdrake",
    "Freedom to Be",
    "Beta-Forge",
    "Empyrean Charge",
    "The Long Con",
}


class CsvPod:
    __slots__ = (
        "name",
        "sas",
        "expansion",
        "house",
        "cards",
        "link",
        "on_market",
        "price",
    )

    def __init__(
        self,
        name,
        expansion,
        link,
        house,
        sas,
        cards,
        for_sale,
        for_trade,
        price,
    ) -> None:
        self.name = name
        self.expansion = expansion
        self.house = house
        self.link = link
        self.sas = float(sas)
        self.cards = cards
        self.on_market = "true" in (for_sale, for_trade)
        self.price = price

    def headers(self) -> List[str]:
        return list(self.__slots__)

    def as_row(self) -> List:
        return [getattr(self, attr) for attr in self.__slots__]


class DeckFromCsv:
    __slots__ = (
        "name",
        "house1",
        "house2",
        "house3",
        "set_string",
        "house1_sas",
        "house2_sas",
        "house3_sas",
        "house1_cards",
        "house2_cards",
        "house3_cards",
        "link",
        "for_sale",
        "for_trade",
        "price",
    )
    ROWS_TO_READ = (
        '\ufeff"Name"',
        "Houses",
        "Expansion",
        "House 1 SAS",
        "House 2 SAS",
        "House 3 SAS",
        "House 1 Cards",
        "House 2 Cards",
        "House 3 Cards",
        "DoK Link",
        "For Sale",
        "For Trade",
        "Price",
    )

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
        for_trade,
        price,
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
        self.for_trade = for_trade
        self.price = price

    def __repr__(self) -> str:
        return (
            f"{self.name} - {self.house1}: {self.house1_sas}, "
            f"{self.house2}: {self.house2_sas}, {self.house3}: {self.house3_sas}"
        )

    def as_pods(self) -> List[CsvPod]:
        return [
            CsvPod(
                self.name,
                self.set_string,
                self.link,
                self.house1,
                self.house1_sas,
                self.house1_cards,
                self.for_sale,
                self.for_trade,
                self.price,
            ),
            CsvPod(
                self.name,
                self.set_string,
                self.link,
                self.house2,
                self.house2_sas,
                self.house2_cards,
                self.for_sale,
                self.for_trade,
                self.price,
            ),
            CsvPod(
                self.name,
                self.set_string,
                self.link,
                self.house3,
                self.house3_sas,
                self.house3_cards,
                self.for_sale,
                self.for_trade,
                self.price,
            ),
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
    def __init__(self, seconds_per_call: float = 5.0, domain_rates: Dict[str, float] = None):
        self.seconds_per_call = seconds_per_call
        self.domain_rates = domain_rates or {}
        self._state_lock = threading.Lock()
        self._domain_state: Dict[str, tuple] = {}  # domain -> (lock, [last_call_time])

    def _get_domain_state(self, url: str) -> tuple:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        with self._state_lock:
            if domain not in self._domain_state:
                rate = self.domain_rates.get(domain, self.seconds_per_call)
                self._domain_state[domain] = (threading.Lock(), [0.0], rate)
            return self._domain_state[domain]

    def callMVSync(self, *args, **kwargs):
        url = args[0]
        lock, last_call, rate = self._get_domain_state(url)
        with lock:
            time_since_last_call = time.time() - last_call[0]
            time_to_sleep = max(0.0, rate - time_since_last_call)
            current_app.logger.debug(f"Sleeping {time_to_sleep} before calling mv api")
            time.sleep(time_to_sleep)
            last_call[0] = time.time()
            current_app.logger.debug(f"Calling {args}, {kwargs}")
            response = requests.get(*args, **kwargs)
            return response


mv_api = MVApi(
    seconds_per_call=20.0,
    domain_rates={
        # Our own proxy and the AWS caching proxy have no meaningful rate limit
        "localhost:3001": 0.0,
        "mvproxy.us-west-2.elasticbeanstalk.com": 0.0,
    },
)


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
    # Session cookie settings. Secure=False so localhost:3001 dev still works;
    # the production path (HTTPS via Gunicorn 3443) sets the secure flag
    # correctly on its own because Werkzeug sees an HTTPS connection.
    config["SESSION_COOKIE_HTTPONLY"] = True
    config["SESSION_COOKIE_SAMESITE"] = "Lax"
    config["REMEMBER_COOKIE_HTTPONLY"] = True
    config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
    # 30-day session lifetime prevents sessions from accumulating indefinitely
    # across browsers/devices. Users re-authenticate after 30 days of inactivity.
    config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=30)
    config_path = os.environ.get("TRACKER_CONFIG_PATH", "config.ini")
    if config_path == "ENV":
        config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
        config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "placeholder")
        config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID", "")
        config["GOOGLE_CLIENT_SECRET"] = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        config["PATREON_CLIENT_ID"] = os.environ.get("PATREON_CLIENT_ID", "")
        config["PATREON_CLIENT_SECRET"] = os.environ.get("PATREON_CLIENT_SECRET", "")
        config["PATREON_CAMPAIGN_ID"] = os.environ.get("PATREON_CAMPAIGN_ID", "")
        config["DISCORD_CLIENT_ID"] = os.environ.get("DISCORD_CLIENT_ID", "")
        config["DISCORD_CLIENT_SECRET"] = os.environ.get("DISCORD_CLIENT_SECRET", "")
        config["DISCORD_GUILD_ID"] = os.environ.get(
            "DISCORD_GUILD_ID", "698635177248948316"
        )
        config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "")
        config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", "587"))
        config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "true").lower() in (
            "1",
            "true",
            "yes",
        )
        config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
        config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
        config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", "")
        config["APP_BASE_URL"] = os.environ.get("APP_BASE_URL", "")
        config["RECAPTCHA_SECRET_KEY"] = os.environ.get("RECAPTCHA_SECRET_KEY", "")
    else:
        cparser = configparser.ConfigParser()
        cparser.read(config_path)
        config["SQLALCHEMY_DATABASE_URI"] = config_to_uri(**cparser["db"])
        config["SECRET_KEY"] = cparser["app"]["secret_key"]
        if "google" in cparser:
            config["GOOGLE_CLIENT_ID"] = cparser["google"].get("client_id", "")
            config["GOOGLE_CLIENT_SECRET"] = cparser["google"].get("client_secret", "")
        if "patreon" in cparser:
            config["PATREON_CLIENT_ID"] = cparser["patreon"].get("client_id", "")
            config["PATREON_CLIENT_SECRET"] = cparser["patreon"].get(
                "client_secret", ""
            )
            config["PATREON_CAMPAIGN_ID"] = cparser["patreon"].get("campaign_id", "")
        if "discord" in cparser:
            config["DISCORD_CLIENT_ID"] = cparser["discord"].get("client_id", "")
            config["DISCORD_CLIENT_SECRET"] = cparser["discord"].get(
                "client_secret", ""
            )
            config["DISCORD_GUILD_ID"] = cparser["discord"].get(
                "guild_id", "698635177248948316"
            )
        if "email" in cparser:
            config["MAIL_SERVER"] = cparser["email"].get("mail_server", "")
            config["MAIL_PORT"] = int(cparser["email"].get("mail_port", "587"))
            config["MAIL_USE_TLS"] = cparser["email"].get(
                "mail_use_tls", "true"
            ).lower() in ("1", "true", "yes")
            config["MAIL_USERNAME"] = cparser["email"].get("mail_username", "")
            config["MAIL_PASSWORD"] = cparser["email"].get("mail_password", "")
            config["MAIL_DEFAULT_SENDER"] = cparser["email"].get(
                "mail_default_sender", ""
            )
            config["APP_BASE_URL"] = cparser["email"].get("app_base_url", "")
        if "recaptcha" in cparser:
            config["RECAPTCHA_SECRET_KEY"] = cparser["recaptcha"].get("secret_key", "")
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


def log_to_game(log: str, is_alliance: bool = False) -> Game:
    lines = log.split("\n")
    current_app.logger.debug(f"Starting to parse log with {len(lines)} lines.")
    player_infos = {}
    first_player = None

    # Phase 1: pre-scan to find players and first player
    for line in lines:
        m = PLAYER_DECK_MATCHER.match(line)
        if m:
            name = m.group(1)
            current_app.logger.debug(f"Found player {name} with deck {m.group(2)}")
            if name not in player_infos:
                player_infos[name] = PlayerInfo()
                player_infos[name].player_name = name
            player_infos[name].deck_name = m.group(2)
            continue
        m = CONNECTED_MATCHER.match(line)
        if m:
            name = m.group(1)
            if name not in player_infos:
                current_app.logger.debug(f"Found player (connected): {name}")
                player_infos[name] = PlayerInfo()
                player_infos[name].player_name = name
            continue
        m = FIRST_PLAYER_MATCHER.match(line)
        if m:
            name = m.group(1)
            first_player = name
            if name not in player_infos:
                player_infos[name] = PlayerInfo()
                player_infos[name].player_name = name
            current_app.logger.debug(f"Found first player: {name}")
            continue
        if len(player_infos) >= 2 and first_player:
            break

    if len(player_infos) < 2:
        raise BadLog("Did not find two players in log")
    if first_player is None:
        raise BadLog("Could not determine first player from log")

    # Phase 2: full scan for house choices, forges, and winner
    for line in lines:
        m = HOUSE_CHOICE_MATCHER.match(line)
        if m and m.group(1) in player_infos:
            current_app.logger.debug(f"{m.group(1)} picked {m.group(2)}")
            player_infos[m.group(1)].house_counts[m.group(2)] += 1
            continue
        m = HOUSE_MANUAL_MATCHER.match(line)
        if m and m.group(1) in player_infos:
            player_infos[m.group(1)].house_counts[m.group(2)] += 1
            continue
        m = FORGE_MATCHER.match(line)
        if m and m.group(1) in player_infos:
            current_app.logger.debug(f"{m.group(1)} forged for {m.group(3)}")
            player_infos[m.group(1)].keys_forged += 1
            player_infos[m.group(1)].key_costs.append(int(m.group(3)))
            continue
        m = SHUFFLE_MATCHER.match(line)
        if m and m.group(1) in player_infos:
            player_infos[m.group(1)].shuffles += 1
            continue
        m = WIN_MATCHER.match(line)
        if m and m.group(1) in player_infos:
            current_app.logger.debug(f"{m.group(1)} won")
            player_infos[m.group(1)].winner = True

    if not any(pi.winner for pi in player_infos.values()):
        raise BadLog("Could not determine game winner from log")

    for player in player_infos.values():
        if player.winner:
            winner_info = player
        else:
            loser_info = player

    winner_name = winner_info.player_name
    loser_name = loser_info.player_name

    # Resolve decks: use name lookup if available, otherwise infer from cards played
    winner_deck = None
    loser_deck = None
    if winner_info.deck_name and winner_info.deck_name != "UNSET":
        try:
            winner_deck = get_deck_by_name_with_zeal(winner_info.deck_name)
        except Exception:
            current_app.logger.debug(
                f"Could not resolve winner deck by name: {winner_info.deck_name}"
            )
            winner_deck = _infer_deck_from_log(lines, winner_name)
    else:
        winner_deck = _infer_deck_from_log(lines, winner_name)
        if winner_deck:
            current_app.logger.debug(f"Inferred winner deck: {winner_deck.name}")
    if loser_info.deck_name and loser_info.deck_name != "UNSET":
        try:
            loser_deck = get_deck_by_name_with_zeal(loser_info.deck_name)
        except Exception:
            current_app.logger.debug(
                f"Could not resolve loser deck by name: {loser_info.deck_name}"
            )
            loser_deck = _infer_deck_from_log(lines, loser_name)
    else:
        loser_deck = _infer_deck_from_log(lines, loser_name)
        if loser_deck:
            current_app.logger.debug(f"Inferred loser deck: {loser_deck.name}")

    if winner_deck:
        current_app.logger.debug(f"Winning deck: {winner_deck.name}")
    if loser_deck:
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
        winner_deck_id=winner_deck.kf_id if winner_deck else None,
        winner_deck_name=winner_deck.name if winner_deck else None,
        winner_keys=winner_info.keys_forged,
        loser=loser_name,
        loser_id=loser.id,
        loser_deck=loser_deck,
        loser_deck_id=loser_deck.kf_id if loser_deck else None,
        loser_deck_name=loser_deck.name if loser_deck else None,
        loser_keys=loser_info.keys_forged,
    )
    return game


def _extract_cards_played(lines: list, player_name: str) -> set:
    """Return set of card names played by player_name in the log."""
    cards = set()
    for line in lines:
        m = CARD_PLAY_MATCHER.match(line)
        if m and m.group(1) == player_name:
            raw = m.group(2)
            card = ATTACHING_SUFFIX_RE.sub("", raw).strip()
            cards.add(card)
    return cards


def _find_deck_by_cards(card_names: set) -> Optional["Deck"]:
    """Find the unique deck containing all given card names. Returns None if ambiguous."""
    matching_ids = None
    for name in card_names:
        ids = set(
            row[0]
            for row in db.session.query(CardInDeck.deck_id)
            .join(PlatonicCard, CardInDeck.platonic_card_id == PlatonicCard.id)
            .filter(PlatonicCard.card_title == name)
            .all()
        )
        if not ids:
            continue  # token or unknown card — skip
        matching_ids = ids if matching_ids is None else matching_ids & ids
        if matching_ids is not None and len(matching_ids) == 1:
            break
    if matching_ids and len(matching_ids) == 1:
        return Deck.query.get(next(iter(matching_ids)))
    return None


def _infer_deck_from_log(lines: list, player_name: str) -> Optional["Deck"]:
    """Infer a player's deck from the cards they played."""
    card_names = _extract_cards_played(lines, player_name)
    return _find_deck_by_cards(card_names)


def _infer_deck_from_snapshots(turn_snapshots: list, player_name: str) -> Optional["Deck"]:
    """Infer a player's deck from card names seen on their board/hand across turn snapshots."""
    card_names: set = set()
    for snap in turn_snapshots:
        boards = snap.get("boards", {}) if isinstance(snap, dict) else {}
        player_board = boards.get(player_name, [])
        if isinstance(player_board, list):
            for card in player_board:
                if isinstance(card, dict) and card.get("name"):
                    card_names.add(card["name"])
        if snap.get("player") == player_name:
            for card in snap.get("local_hand", []):
                if isinstance(card, dict) and card.get("name"):
                    card_names.add(card["name"])
    return _find_deck_by_cards(card_names) if card_names else None


def _find_deck_for_pod(card_names: list, house_name: str) -> Optional["Deck"]:
    """Find the unique deck containing cards from house_name that match card_names."""
    matching_ids = None
    for name in card_names:
        ids = set(
            row[0]
            for row in db.session.query(CardInDeck.deck_id)
            .join(PlatonicCard, CardInDeck.platonic_card_id == PlatonicCard.id)
            .join(PlatonicCardInSet, CardInDeck.card_in_set_id == PlatonicCardInSet.id)
            .join(KeyforgeHouse, PlatonicCardInSet.kf_house_id == KeyforgeHouse.id)
            .filter(
                PlatonicCard.card_title == name,
                KeyforgeHouse.name == house_name,
            )
            .all()
        )
        if not ids:
            continue
        matching_ids = ids if matching_ids is None else matching_ids & ids
        if matching_ids is not None and len(matching_ids) == 1:
            break
    if matching_ids and len(matching_ids) == 1:
        return Deck.query.get(next(iter(matching_ids)))
    return None


def _extract_cards_per_player_house(lines: list, player_names: set) -> dict:
    """Return {player_name: {house_name: [card_name, ...]}} from log lines."""
    current_house = {}
    result = {p: defaultdict(list) for p in player_names}

    for line in lines:
        m = HOUSE_CHOICE_MATCHER.match(line)
        if m:
            player = m.group(1)
            if player in player_names:
                current_house[player] = _normalize_log_house(m.group(2))
            continue
        m = HOUSE_MANUAL_MATCHER.match(line)
        if m:
            player = m.group(1)
            if player in player_names:
                current_house[player] = _normalize_log_house(m.group(2))
            continue
        m = CARD_PLAY_MATCHER.match(line)
        if m:
            player = m.group(1)
            if player in player_names and player in current_house:
                raw = m.group(2)
                card = ATTACHING_SUFFIX_RE.sub("", raw).strip()
                result[player][current_house[player]].append(card)
    return result


def infer_alliance_pods(log: str, game: Game) -> dict:
    """Infer which pod decks were used by each player in an alliance game.

    Returns:
        {player_name: [{"house": str, "deck_id": str|None, "deck_name": str|None}, ...]}
    """
    lines = log.split("\n")
    player_names = set()
    if game.winner:
        player_names.add(game.winner)
    if game.loser:
        player_names.add(game.loser)

    cards_per_player_house = _extract_cards_per_player_house(lines, player_names)

    result = {}
    for player_name, house_cards in cards_per_player_house.items():
        pods = []
        for house_name, cards in house_cards.items():
            deck = _find_deck_for_pod(cards, house_name)
            pods.append(
                {
                    "house": house_name,
                    "deck_id": deck.kf_id if deck else None,
                    "deck_name": deck.name if deck else None,
                }
            )
        result[player_name] = pods
    return result


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


def parse_deck_url(url: str):
    """
    Extract deck UUID from a Master Vault or DoK URL, or accept a raw UUID.
    Returns the UUID string, or None if not recognized.
    """
    import re

    url = url.strip()
    # keyforgegame.com deck-details or deck URL variants
    m = re.search(r"keyforgegame\.com/(?:en-us/)?deck(?:-details)?/([a-f0-9-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"decksofkeyforge\.com/decks/([a-f0-9-]+)", url)
    if m:
        return m.group(1)
    m = re.match(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", url)
    if m:
        return url
    return None


def fetch_dok_alliance(uuid: str) -> dict:
    """
    Fetch a DoK alliance deck by UUID.  Returns structured pod data.

    Returns dict:
      {
        "pods": [{"deck_id": int, "deck_name": str, "house": str}, ...],
        "token_deck_id": int | None,
        "prophecy_deck_id": int | None,
        "valid_alliance": bool,
      }
    """
    url = f"{DOK_ALLIANCE_BASE}/{uuid}"
    response = requests.get(url, headers=DOK_HEADERS)
    response.raise_for_status()
    data = response.json()
    deck_data = data.get("deck", {})
    alliance_houses = deck_data.get("allianceHouses", [])
    token_info = deck_data.get("tokenInfo") or {}
    prophecies = deck_data.get("prophecies") or []
    valid_alliance = bool(deck_data.get("validAlliance", False))

    pods = []
    for house_entry in alliance_houses:
        kf_id = house_entry.get("keyforgeId")
        house_name = house_entry.get("house")
        if not kf_id or not house_name:
            continue
        deck = get_deck_by_id_with_zeal(kf_id)
        deck_houses = [ps.house for ps in deck.pod_stats if ps.house != "Archon Power"]
        pods.append(
            {
                "deck_id": deck.id,
                "kf_id": deck.kf_id,
                "deck_name": deck.name,
                "house": house_name,
                "expansion": deck.expansion,
                "houses": deck_houses,
                "sas_rating": deck.sas_rating,
            }
        )

    token_deck_id = None
    if token_info and token_info.get("house"):
        token_house = token_info["house"]
        for pod in pods:
            if pod["house"] == token_house:
                token_deck_id = pod["deck_id"]
                break

    prophecy_deck_id = None
    if prophecies and pods:
        prophecy_deck_id = pods[0]["deck_id"]

    return {
        "pods": pods,
        "token_deck_id": token_deck_id,
        "prophecy_deck_id": prophecy_deck_id,
        "valid_alliance": valid_alliance,
    }


def get_deck_by_id_with_zeal(deck_id: str, sas_rating=None, aerc_score=None) -> Deck:
    current_app.logger.debug("Checking for deck in db")
    deck = Deck.query.filter_by(kf_id=deck_id).first()
    if deck is None:
        deck = Deck(kf_id=deck_id)
        db.session.add(deck)
        refresh_deck_from_mv(deck)
        if sas_rating and aerc_score:
            deck.sas_rating = sas_rating
            deck.aerc_score = aerc_score
            deck.sas_version = LATEST_SAS_VERSION
        else:
            update_sas_scores(deck)
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


def get_or_create_deck_for_collection(
    kf_id: str, sas_rating=None, aerc_score=None
) -> Deck:
    """Lightweight deck lookup for collection sync.

    Only fetches from Master Vault when the deck is not in the DB yet.
    Never refreshes SAS scores or card data for existing decks — the
    caller already has fresh DoK data to store on the collection row.
    """
    deck = Deck.query.filter_by(kf_id=kf_id).first()
    if deck is None:
        deck = Deck(kf_id=kf_id)
        refresh_deck_from_mv(deck)
        if sas_rating is not None and aerc_score is not None:
            deck.sas_rating = sas_rating
            deck.aerc_score = aerc_score
            deck.sas_version = LATEST_SAS_VERSION
        db.session.add(deck)
        db.session.commit()
        db.session.refresh(deck)
    return deck


def loop_loading_missed_sas(batch_size: int, max_set_id: int = 700) -> None:
    q = Deck.query.filter(and_(Deck.expansion < max_set_id, Deck.dok == None))
    query_times = []
    while q.count() > 0:
        current_app.logger.info(
            f"{q.count()} decks left. Fetching {batch_size} to process."
        )
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


def _try_add_deck_from_local_dok(deck: Deck) -> bool:
    """Try to populate deck card data from local DoK's search-result-with-cards endpoint.

    Looks up each card's PlatonicCardInSet by (card_title, expansion, house).
    Returns True on success; False if the caller should fall back to the MV proxy.
    """
    try:
        url = f"{LOCAL_DOK_URL}/api/decks/search-result-with-cards/{deck.kf_id}"
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            current_app.logger.debug(
                f"Local DoK search-result-with-cards returned {resp.status_code} "
                f"for {deck.kf_id}"
            )
            return False
        data = resp.json()
    except Exception as e:
        current_app.logger.warning(
            f"Local DoK request failed for deck {deck.kf_id}: {e}"
        )
        return False

    expansion_str = data.get("expansion")
    expansion_int = _DOK_EXPANSION_TO_INT.get(expansion_str)
    if expansion_int is None:
        current_app.logger.warning(
            f"Unknown DoK expansion {expansion_str!r} for deck {deck.kf_id}"
        )
        return False

    # Resolve all cards before mutating anything (fail-fast before any DB writes).
    cards_to_create = []
    for house_entry in data.get("housesAndCards", []):
        house_name = house_entry["house"]
        for card_data in house_entry["cards"]:
            title = card_data["cardTitle"]
            # Find matching PlatonicCardInSet by title + expansion, preferring the
            # record whose house matches the deck house (handles mavericks correctly).
            candidates = (
                PlatonicCardInSet.query.join(
                    PlatonicCard, PlatonicCardInSet.card_id == PlatonicCard.id
                )
                .filter(
                    PlatonicCard.card_title == title,
                    PlatonicCardInSet.expansion == expansion_int,
                )
                .all()
            )
            pcis = next((p for p in candidates if p.house == house_name), None)
            if pcis is None and len(candidates) == 1:
                pcis = candidates[0]
            if pcis is None:
                current_app.logger.debug(
                    f"PlatonicCardInSet not found for {title!r} "
                    f"exp={expansion_int} house={house_name}; "
                    f"falling back to MV proxy for {deck.kf_id}"
                )
                return False
            cards_to_create.append((pcis, card_data))

    deck.name = data["name"]
    deck.expansion = expansion_int

    for pcis, card_data in cards_to_create:
        is_enhanced = card_data.get("enhanced", False)
        card = CardInDeck(
            platonic_card=pcis.card,
            card_in_set=pcis,
            deck=deck,
            is_enhanced=is_enhanced,
            enhanced_amber=card_data.get("bonusAember", 0) if is_enhanced else 0,
            enhanced_capture=card_data.get("bonusCapture", 0) if is_enhanced else 0,
            enhanced_draw=card_data.get("bonusDraw", 0) if is_enhanced else 0,
            enhanced_damage=card_data.get("bonusDamage", 0) if is_enhanced else 0,
            enhanced_discard=card_data.get("bonusDiscard", 0) if is_enhanced else 0,
            enhanced_houses=len(card_data.get("bonusHouses", [])) if is_enhanced else 0,
            is_legacy=check_is_legacy(pcis.card, deck),
        )
        db.session.add(card)
        for bonus_house in (card_data.get("bonusHouses", []) if is_enhanced else []):
            db.session.add(
                HouseEnhancement(
                    card=card,
                    kf_house=get_house_for_enhancement(bonus_house.lower()),
                )
            )

    db.session.commit()
    current_app.logger.info(
        f"Populated deck {deck.kf_id!r} ({data['name']!r}) from local DoK"
    )
    return True


def refresh_deck_from_mv(deck: Deck, card_cache: Dict = None) -> None:
    if card_cache is None:
        card_cache = {}
    if TRY_LOCAL_DOK_FOR_DECK_BASE_DATA and _try_add_deck_from_local_dok(deck):
        return
    mv_fallback = TRY_LOCAL_DOK_FOR_DECK_BASE_DATA
    deck_url = os.path.join(MV_SINGLE_DECK_BASE, deck.kf_id)
    if "keyforgegame.com" in MV_SINGLE_DECK_BASE:
        params = {"links": "cards,notes"}
    else:
        params = {}
    response = mv_api.callMVSync(deck_url, params=params)
    all_data = response.json()
    deck_payload = all_data.get("deck") or all_data
    if "data" not in deck_payload:
        current_app.logger.error(
            f"No data in response from mv on {deck_url}: {all_data}"
        )
    data = deck_payload["data"]
    card_json = deck_payload["_linked"]["cards"]
    card_details = {c["id"]: c for c in card_json}
    add_one_deck_v2(data, card_details, deck=deck)
    if mv_fallback:
        time.sleep(15)


def get_deck_by_name_with_zeal(deck_name: str) -> Deck:
    deck = Deck.query.filter_by(name=deck_name).first()
    if deck is None:
        deck_id = deck_name_to_id(deck_name)
        deck = get_deck_by_id_with_zeal(deck_id)
    return deck


def update_sas_scores(deck: Deck, dok_api_key: str = None, force: bool = False) -> bool:
    """Returns True if update occurred. Pass force=True to bypass cache and always fetch from DoK."""
    if not force and (
        (deck.sas_version or 0) >= LATEST_SAS_VERSION
        and deck.dok
        and deck.dok.last_refresh is not None
        and datetime.datetime.utcnow() - deck.dok.last_refresh < SAS_TD
    ):
        return False
    if len(deck.cards_from_assoc) < 36:
        current_app.logger.info(
            f"Deck {deck.kf_id} has only {len(deck.cards_from_assoc)} cards — refreshing from MV before DoK update"
        )
        refresh_deck_from_mv(deck)
    url = os.path.join(DOK_DECK_BASE, deck.kf_id)
    headers = {"Api-Key": dok_api_key} if dok_api_key else DOK_HEADERS
    response = requests.get(url, headers=headers)
    data = response.json()
    try:
        deck.sas_rating = data["deck"]["sasRating"]
        deck.aerc_score = data["deck"]["aercScore"]
        deck.sas_version = data["sasVersion"]
        add_dok_deck_from_dict(save_prod_id=(_DOK_BASE == PROD_DOK_BASE), **data["deck"])
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
    for col, direction in sort_specs:
        query = query.order_by(getattr(getattr(Game, col), direction)())
    return query


def randip() -> str:
    third = random.randint(1, 253)
    fourth = random.randint(1, 253)
    return f"192.168.{third}.{fourth}"


def get_house_for_enhancement(name: str) -> KeyforgeHouse:
    house = KeyforgeHouse.query.filter(KeyforgeHouse.name.ilike(name)).first()
    assert house is not None, f"Can't find house for {name}"
    return house


def get_or_create_house(name: str) -> KeyforgeHouse:
    house = KeyforgeHouse.query.filter_by(name=name).first()
    if house is None:
        house = KeyforgeHouse(name=name)
        db.session.add(house)
        db.session.commit()
    return house


def turn_counts_from_logs(game: Game) -> None:
    counts = defaultdict(dict)
    for i, log in enumerate(game.logs):
        m = HOUSE_CHOICE_MATCHER.match(log.message)
        if m:
            username = m.group(1)
            house = _normalize_log_house(m.group(2))
            player = username_to_player(username)
            count = counts[username].get(house)
            if count is None:
                count = HouseTurnCounts(
                    game=game,
                    player=player,
                    kf_house=get_or_create_house(house),
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
            house = _normalize_log_house(n.group(2))
            player = username_to_player(username)
            count = counts[username].get(house)
            if count is None:
                count = HouseTurnCounts(
                    game=game,
                    player=player,
                    kf_house=get_or_create_house(house),
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
    card_type_obj = KeyforgeCardType.query.filter_by(name=card.card_type).first()
    if card_type_obj is None:
        card_type_obj = KeyforgeCardType(name=card.card_type)
        db.session.add(card_type_obj)
    platonic_card = PlatonicCard(
        card_title=card.card_title,
        kf_card_type=card_type_obj,
        front_image=card.front_image,
        card_text=card.card_text,
        amber=card.amber,
        power=card.power,
        armor=card.armor,
        flavor_text=card.flavor_text,
        is_non_deck=card.is_non_deck,
        kf_house=get_or_create_house(card.house),
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
        rarity = KeyforgeRarity.query.filter_by(name=card.rarity).one()
        assert rarity is not None, f"Unrecognized rarity {card.rarity}"
        pc_in_set = PlatonicCardInSet(
            card=platonic_card,
            expansion=card.expansion,
            kf_rarity=rarity,
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


def add_dok_deck_from_dict(skip_commit: bool = False, save_prod_id: bool = False, **data: Dict) -> None:
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
    if save_prod_id:
        prod_id = data.get("id")
        if prod_id is not None:
            dok.prod_dok_id = int(prod_id)
    synergy_details = get_snake_or_camel(data, "synergy_details")
    if synergy_details:
        _update_pod_sas_from_synergy_details(deck, synergy_details)
    if not skip_commit:
        db.session.commit()


def _update_pod_sas_from_synergy_details(deck: Deck, synergy_details: list) -> None:
    """Populate PodStats.sas_rating from synergyDetails returned by the local DoK API."""
    house_sas: dict[str, float] = {}
    for item in synergy_details:
        house = item.get("house")
        if not house:
            continue
        house_sas[house] = house_sas.get(house, 0.0) + item.get("aercScore", 0.0) * item.get("copies", 1)
    for pod in deck.pod_stats:
        if pod.house in house_sas:
            pod.sas_rating = round(house_sas[pod.house])


def calculate_pod_stats(deck: Deck) -> None:
    house_to_cards = defaultdict(list)
    for card in deck.cards_from_assoc:
        house_to_cards[card.kf_house].append(card)
    for kf_house, cards in house_to_cards.items():
        if kf_house is None or kf_house.name in [
            "The Tide",
            "Prophecy",
        ]:
            continue
        enhancements, amber, capture, draw, damage = 0, 0, 0, 0, 0
        mutants, creatures, raw_amber = 0, 0, 0
        for card in cards:
            if any(trait.name == "mutant" for trait in card.traits):
                mutants += 1
            if card.card_type == "Creature":
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
            if pod.kf_house == kf_house:
                break
        else:
            pod = PodStats(deck=deck, kf_house=kf_house)
            db.session.add(pod)
        pod.enhanced_amber = amber
        pod.enhanced_capture = capture
        pod.enhanced_draw = draw
        pod.enhanced_damage = damage
        pod.num_enhancements = enhancements
        pod.num_mutants = mutants
        pod.creatures = creatures
        pod.raw_amber = raw_amber
        pod.total_amber = raw_amber + amber


# def guess_deck_language(deck: Deck) -> None:
#     guess = language_detector.detect_language_of(deck.name)
#     if guess is None:
#         deck.language = None
#     else:
#         deck.language = guess.name
#         language = DeckLanguage.query.filter_by(name=guess.name).first()
#         if language is None:
#             language = DeckLanguage(name=guess.name)
#             db.session.add(language)
#         deck.deck_language = language


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
    response = mv_api.callMVSync(
        MV_API_BASE,
        params=params,
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
                current_app.logger.error(
                    f"Got error, retrying: {data['message'] + data['detail']}"
                )
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
    gvar_name: str = "highest_mv_page_scraped",
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
    response = mv_api.callMVSync(
        MV_API_BASE,
        params=params,
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
                current_app.logger.error(
                    f"Got error, retrying: {data['message'] + data['detail']}"
                )
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
    if update_highest_page and reverse:
        highest_page = GlobalVariable.query.filter_by(
            name=gvar_name
        ).first()
        if page > highest_page.value_int:
            highest_page.value_int = page
            db.session.commit()
    return new_decks


def add_one_deck_v2(
    deck_json, card_details, add_decks_cache=None, deck: Deck = None
) -> int:
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
            for card in deck.cards_from_assoc:
                db.session.delete(card)
            deck.cards_from_assoc.clear()
            add_cards_v2_new(
                deck, deck_card_ids, card_details, bonus_icons, add_decks_cache
            )
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
            or card.power
            != int(0 if card_json["power"] in ("X", None) else card_json["power"])
            or card.armor
            != int(0 if card_json["armor"] in ("X", None) else card_json["armor"])
            or card.flavor_text != card_json["flavor_text"]
            or card.card_number != card_json["card_number"]
            or card.expansion != card_json["expansion"]
            or card.is_maverick != card_json["is_maverick"]
            or card.is_anomaly != card_json["is_anomaly"]
            or card.is_enhanced != card_json["is_enhanced"]
            or card.is_non_deck != card_json["is_non_deck"]
            or card.rarity != card_json["rarity"]
            or card.card_type != card_json["card_type"]
            or card.house != card_json["house"]
        ):
            current_app.logger.debug("Found mismatch in simple strings")
            if card.card_title != card_json["card_title"]:
                current_app.logger.debug(
                    f"card_title: {diff_strings(card.card_title, card_json['card_title'])}"
                )
            if card.front_image != card_json["front_image"]:
                current_app.logger.debug(
                    f"front_image: {diff_strings(card.front_image, card_json['front_image'])}"
                )
            if card.card_text != card_json["card_text"]:
                current_app.logger.debug(
                    f"card_text: {diff_strings(card.card_text, card_json['card_text'])}"
                )
            if card.amber != card_json["amber"]:
                current_app.logger.debug(f"amber: {card.amber} vs {card_json['amber']}")
            if card.power != normalize_stat(card_json["power"]):
                current_app.logger.debug(f"power: {card.power} vs {card_json['power']}")
            if card.armor != normalize_stat(card_json["armor"]):
                current_app.logger.debug(f"armor: {card.armor} vs {card_json['armor']}")
            if card.flavor_text != card_json["flavor_text"]:
                current_app.logger.debug(
                    f"flavor_text: {card.flavor_text} vs {card_json['flavor_text']}"
                )
            if card.card_number != card_json["card_number"]:
                current_app.logger.debug(
                    f"card_number: {card.card_number} vs {card_json['card_number']}"
                )
            if card.expansion != card_json["expansion"]:
                current_app.logger.debug(
                    f"expansion: {card.expansion} vs {card_json['expansion']}"
                )
            if card.is_maverick != card_json["is_maverick"]:
                current_app.logger.debug(
                    f"is_maverick: {card.is_maverick} vs {card_json['is_maverick']}"
                )
            if card.is_anomaly != card_json["is_anomaly"]:
                current_app.logger.debug(
                    f"is_anomaly: {card.is_anomaly} vs {card_json['is_anomaly']}"
                )
            if card.is_enhanced != card_json["is_enhanced"]:
                current_app.logger.debug(
                    f"is_enhanced: {card.is_enhanced} vs {card_json['is_enhanced']}"
                )
            if card.is_non_deck != card_json["is_non_deck"]:
                current_app.logger.debug(
                    f"is_non_deck: {card.is_non_deck} vs {card_json['is_non_deck']}"
                )
            if card.rarity != card_json["rarity"]:
                current_app.logger.debug(
                    f"rarity: {card.rarity} vs {card_json['rarity']}"
                )
            if card.card_type != card_json["card_type"]:
                current_app.logger.debug(
                    f"card_type: {card.card_type} vs {card_json['card_type']}"
                )
            if card.house != card_json["house"]:
                current_app.logger.debug(f"house: {card.house} vs {card_json['house']}")
            return False
        # Check traits
        if card_json["traits"] and {t.name for t in card.traits} != set(
            card_json["traits"].split(" • ")
        ):
            current_app.logger.debug("Found mismatch in traits")
            return False
    return True


def diff_strings(a: str, b: str) -> str:
    msg = [f"{a} => {b}"]
    for i, s in enumerate(difflib.ndiff(a, b)):
        if s[0] == " ":
            continue
        elif s[0] == "0":
            msg.append(f'Delete "{s[-1]}" from position {i}')
        elif s[0] == "+":
            msg.append(f'Add "{s[-1]}" to position {i}')
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
        override = CARD_EXP_TO_OVERRIDE.get(
            (card_json["card_title"], card_json["expansion"])
        )
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
                if override is None:
                    pc = PlatonicCard.query.filter_by(
                        card_title=card_json["card_title"]
                    ).first()
                else:
                    pc = PlatonicCard.query.filter_by(
                        card_title=card_json["card_title"],
                        house=override.house,
                    ).first()
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
        update_platonic_info(pc, pcis, card_json, override)
        card = CardInDeck(
            platonic_card=pc,
            card_in_set=pcis,
            deck=deck,
            is_enhanced=card_json["is_enhanced"],
            enhanced_amber=0,
            enhanced_capture=0,
            enhanced_draw=0,
            enhanced_damage=0,
            enhanced_discard=0,
            enhanced_houses=0,
            is_legacy=check_is_legacy(pc, deck),
        )
        db.session.add(card)
        if card.is_enhanced:
            bling = copy.deepcopy(bonus_icons)
            for idx, enh in enumerate(bling):
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
                        elif icon in VALID_HOUSE_ENHANCEMENTS:
                            card.enhanced_houses += 1
                            house_enhancement = HouseEnhancement(
                                card=card,
                                kf_house=get_house_for_enhancement(icon),
                            )
                            db.session.add(house_enhancement)
                        else:
                            raise MissingEnhancements(
                                f"Could not pair enhancements in {deck.kf_id}"
                            )
                    break
            else:
                raise MissingEnhancements(
                    f"Could not pair enhancements in {deck.kf_id}"
                )


def check_is_legacy(pc: PlatonicCard, deck: Deck) -> bool:
    # Originally, I thought of having this as the easiest, cheapest check, but then
    # again I've come to distrust MV data.
    # if card_json["expansion"] = deck.expansion:
    #     return False
    # Trust sqlalchemy to cache this reasonably
    platonic_card_ids_in_expansion = {
        pcis.card_id
        for pcis in PlatonicCardInSet.query.with_entities(PlatonicCardInSet.card_id)
        .filter_by(expansion=deck.expansion)
        .all()
    }
    # If the platonic card id matches, great
    if pc.id in platonic_card_ids_in_expansion:
        return False
    # apostrophe in the card title is handled inconsistently across sets, special case
    # it
    if (
        "'" in pc.card_title
        and PlatonicCardInSet.query.filter_by(
            expansion=deck.expansion, card_title=pc.card_title.replace("'", "’")
        ).count()
        > 0
    ):
        return False
    if (
        "’" in pc.card_title
        and PlatonicCardInSet.query.filter_by(
            expansion=deck.expansion, card_title=pc.card_title.replace("’", "'")
        ).count()
        > 0
    ):
        return False
    # Need to catch anomalies?
    # Otherwise, we're dealing with a legacy!
    return True


def normalize_stat(stat: Optional[str]) -> int:
    if stat in ("X", None):
        return 0
    else:
        return int(stat)


def update_platonic_info(
    platonic_card: PlatonicCard,
    card_in_set: PlatonicCardInSet,
    card_json,
    override: CardSetHouseOverride = None,
) -> None:
    incoming_expansion = card_json["expansion"]
    house = get_or_create_house(card_json["house"])

    # Always update card-in-set fields (they are set-specific)
    card_in_set.kf_house = house
    card_in_set.expansion = incoming_expansion
    card_in_set.card_number = card_json["card_number"]
    card_in_set.is_anomaly = card_json["is_anomaly"]
    card_in_set.front_image = card_json["front_image"]
    if (
        card_in_set.kf_rarity is None
        or card_in_set.kf_rarity.name != card_json["rarity"]
    ):
        rarity = KeyforgeRarity.query.filter_by(name=card_json["rarity"]).first()
        if rarity is None:
            rarity = KeyforgeRarity(name=card_json["rarity"])
            db.session.add(rarity)
        card_in_set.kf_rarity = rarity

    # Only overwrite PlatonicCard fields if this set is at least as new as what
    # we previously wrote (higher expansion number = newer set).
    if (
        platonic_card.source_expansion is not None
        and incoming_expansion < platonic_card.source_expansion
    ):
        return

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
    if (
        platonic_card.kf_card_type is None
        or platonic_card.kf_card_type.name != card_json["card_type"]
    ):
        card_type = KeyforgeCardType.query.filter_by(
            name=card_json["card_type"]
        ).first()
        if card_type is None:
            card_type = KeyforgeCardType(name=card_json["card_type"])
            db.session.add(card_type)
        platonic_card.kf_card_type = card_type
    platonic_card.front_image = card_json["front_image"]
    platonic_card.card_text = card_json["card_text"]
    platonic_card.amber = int(card_json["amber"])
    platonic_card.power = normalize_stat(card_json["power"])
    platonic_card.armor = normalize_stat(card_json["armor"])
    platonic_card.flavor_text = card_json["flavor_text"]
    # Don't set platonic card house for mavericks, anomalies, or revenants
    if not any(
        [
            card_json["is_maverick"],
            card_json["is_anomaly"],
            # This actuall should cover all revenants
            card_json["card_number"].startswith("R"),
            card_json["card_title"] in MM_UNHOUSED_CARDS + REVENANTS,
        ]
    ):
        if override is None:
            platonic_card.kf_house = house
        else:
            platonic_card.kf_house = get_or_create_house(override.house)
    platonic_card.is_non_deck = card_json["is_non_deck"]
    platonic_card.source_expansion = incoming_expansion


def fix_mavericks(expansion: int) -> int:
    """Look for pcis with broken is_maverick attribute, fix them. Returns number of
    fixed pcis."""
    pciss = PlatonicCardInSet.query.filter_by(expansion=expansion).all()
    fixed = 0
    for pcis in pciss:
        should_be_maverick = pcis.house != pcis.card.house
        if should_be_maverick != pcis.is_maverick:
            fixed += 1
            pcis.is_maverick = should_be_maverick
    db.session.commit()
    return fixed


def fix_pcis_house(pcis: PlatonicCardInSet) -> None:
    card = CardInDeck.query.filter_by(card_in_set_id=pcis.id).first()
    refresh_deck_from_mv(card.deck)
    db.session.commit()


def run_background_collector(
    app,
    stop_event=None,
    gvar_name: str = "highest_mv_page_scraped",
    lock_name: str = "\0keytracker_collector_lock",
    caught_up_sleep: int = 300,
    exit_near_gvar: str = None,
    exit_near_margin: int = 10,
):
    """Background thread that continuously scrapes deck pages from Master Vault."""
    import socket

    logger = app.logger
    CAUGHT_UP_SLEEP = caught_up_sleep

    # Use an abstract Unix socket as a cross-process lock so only one
    # gunicorn worker runs the collector. The socket is automatically
    # released when the process exits.
    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        lock_socket.bind(lock_name)
    except OSError:
        logger.info("Another process already running the collector, skipping")
        return

    add_decks_cache = {
        "seen_deck_ids": set(),
        "card_in_set": {},
        "platonic_card": {},
    }

    logger.info("Background collector started")

    while stop_event is None or not stop_event.is_set():
        try:
            with app.app_context():
                highest_page_var = GlobalVariable.query.filter_by(
                    name=gvar_name
                ).first()
                if highest_page_var is None:
                    highest_page_var = GlobalVariable(name=gvar_name, value_int=0)
                    db.session.add(highest_page_var)
                    db.session.commit()
                    logger.info(f"Created GlobalVariable '{gvar_name}' at 0")

                if exit_near_gvar is not None:
                    ref_var = GlobalVariable.query.filter_by(
                        name=exit_near_gvar
                    ).first()
                    if ref_var is not None and highest_page_var.value_int >= ref_var.value_int - exit_near_margin:
                        logger.info(
                            f"Collector '{gvar_name}' reached within "
                            f"{exit_near_margin} of '{exit_near_gvar}' "
                            f"({highest_page_var.value_int} >= "
                            f"{ref_var.value_int} - {exit_near_margin}), exiting"
                        )
                        return

                page = highest_page_var.value_int + 1
                logger.info(f"Fetching page {page}")

                new_decks = get_decks_from_page_v2(
                    page,
                    reverse=True,
                    add_decks_cache=add_decks_cache,
                    update_highest_page=True,
                    gvar_name=gvar_name,
                )

                if new_decks == 0:
                    logger.info(
                        f"Page {page} returned 0 new decks, sleeping "
                        f"{CAUGHT_UP_SLEEP}s"
                    )
                    time.sleep(CAUGHT_UP_SLEEP)
                else:
                    logger.info(f"Page {page}: {new_decks} new decks")

        except InternalServerError:
            logger.info(
                f"Page beyond last page (InternalServerError), sleeping "
                f"{CAUGHT_UP_SLEEP}s"
            )
            time.sleep(CAUGHT_UP_SLEEP)
        except Exception:
            logger.exception("Background collector error, sleeping 60s")
            time.sleep(60)


def _expected_card_count(expansion_id):
    """Return the (min, max) inclusive card count for a given expansion ID."""
    if expansion_id == 892:  # Martian Civil War
        return (13, 13)
    if expansion_id == 886:  # Prophetic Visions
        return (40, 40)
    if expansion_id in (496, 600, 855, 918):  # DT, WoE, ToC, CC
        return (37, 37)
    if expansion_id == 601:  # Unchained 2022 — 36 base, 37 with token
        return (36, 37)
    return (36, 36)  # all other sets


def run_background_card_refresher(app, stop_event=None):
    """One-time forward scan through all decks, fixing incorrect card counts and
    missing pod stats.

    Uses GlobalVariable 'one_time_scan_last_id' as a persistent cursor so the
    scan survives server restarts. Once no deck is found above the cursor the
    scan is considered complete and the thread exits.
    """
    import socket

    logger = app.logger
    GVAR_NAME = "one_time_scan_last_id"

    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        lock_socket.bind("\0keytracker_card_refresher_lock")
    except OSError:
        logger.info("Another process already running the card refresher, skipping")
        return

    logger.info("Background card refresher started (one-time scan)")
    good_decks_in_a_row = 0

    while stop_event is None or not stop_event.is_set():
        try:
            with app.app_context():
                gvar = GlobalVariable.query.filter_by(name=GVAR_NAME).first()
                if gvar is None:
                    gvar = GlobalVariable(name=GVAR_NAME, value_int=0)
                    db.session.add(gvar)
                    db.session.commit()

                last_id = gvar.value_int or 0
                deck = Deck.query.filter(Deck.id > last_id).order_by(Deck.id).first()

                if deck is None:
                    logger.info(
                        f"One-time card scan complete (last_id={last_id}). "
                        "Thread exiting."
                    )
                    return

                card_count = len(deck.cards_from_assoc)
                min_cards, max_cards = _expected_card_count(deck.expansion)
                needs_mv_refresh = not (min_cards <= card_count <= max_cards)

                if needs_mv_refresh:
                    logger.info(
                        f"Deck {deck.kf_id} ({deck.name}) has {card_count} cards "
                        f"(expected {min_cards}-{max_cards}), trying local DoK"
                        f" after {good_decks_in_a_row} good decks in a row"
                    )
                    good_decks_in_a_row = 0
                    try:
                        ok = _try_add_deck_from_local_dok(deck)
                        if not ok:
                            logger.debug(
                                f"Local DoK has no data for {deck.kf_id}, skipping"
                            )
                        else:
                            db.session.flush()
                    except Exception:
                        logger.exception(
                            "Local DoK refresh failed for deck %s, skipping",
                            deck.kf_id,
                        )
                        db.session.rollback()
                else:
                    good_decks_in_a_row += 1
                    if good_decks_in_a_row % 100 == 0:
                        logger.info(
                            f"background_deck_refresher has seen {good_decks_in_a_row} good decks in a row."
                        )

                if len(deck.pod_stats) == 0 and len(deck.cards_from_assoc) >= min_cards:
                    calculate_pod_stats(deck)

                gvar.value_int = deck.id
                db.session.commit()

        except Exception:
            logger.exception("Background card refresher error, sleeping 60s")
            time.sleep(60)




def _log_mail_config() -> None:
    """Log the active Flask-Mail config (password redacted)."""
    from flask import current_app

    cfg = current_app.config
    current_app.logger.info(
        "SMTP config — server=%s port=%s use_tls=%s username=%s sender=%s",
        cfg.get("MAIL_SERVER"),
        cfg.get("MAIL_PORT"),
        cfg.get("MAIL_USE_TLS"),
        cfg.get("MAIL_USERNAME"),
        cfg.get("MAIL_DEFAULT_SENDER"),
    )


def send_verification_email(user, app_base_url: str) -> None:
    """Send email verification link to user. Token must already be set on user."""
    from flask_mail import Message
    from flask import current_app

    _log_mail_config()
    mail = current_app.extensions["mail"]
    verify_url = (
        f"{app_base_url.rstrip('/')}/auth/verify-email/{user.email_verification_token}"
    )
    current_app.logger.info("Sending verification email to %s", user.email)
    msg = Message(
        subject="Verify your Bear Tracks email",
        recipients=[user.email],
        body=(
            f"Hi {user.name or 'there'},\n\n"
            f"Please verify your email address by clicking the link below:\n\n"
            f"{verify_url}\n\n"
            f"This link expires in 24 hours.\n\n"
            f"If you didn't create an account, you can ignore this email.\n\n"
            f"— Bear Tracks"
        ),
    )
    mail.send(msg)
    current_app.logger.info("Verification email sent to %s", user.email)


def send_password_reset_email(user, app_base_url: str) -> None:
    """Send password reset link to user. Token must already be set on user."""
    from flask_mail import Message
    from flask import current_app

    _log_mail_config()
    mail = current_app.extensions["mail"]
    reset_url = (
        f"{app_base_url.rstrip('/')}/reset-password?token={user.password_reset_token}"
    )
    current_app.logger.info("Sending password reset email to %s", user.email)
    msg = Message(
        subject="Reset your Bear Tracks password",
        recipients=[user.email],
        body=(
            f"Hi {user.name or 'there'},\n\n"
            f"Click the link below to reset your password:\n\n"
            f"{reset_url}\n\n"
            f"This link expires in 1 hour.\n\n"
            f"If you didn't request a password reset, you can ignore this email.\n\n"
            f"— Bear Tracks"
        ),
    )
    mail.send(msg)
    current_app.logger.info("Password reset email sent to %s", user.email)


DOK_MY_DECKS_BASE = f"{PROD_DOK_BASE}/public-api/v1/my-decks"
DOK_MY_ALLIANCES_URL = f"{PROD_DOK_BASE}/public-api/v1/my-alliances"


def sync_collection_from_dok(user) -> dict:
    """Sync a user's DoK collection (standard + alliance decks) into the DB.

    Uses user.dok_api_key. Returns {standard_decks: N, alliance_decks: M}.
    """
    if not user.dok_api_key:
        raise ValueError("No DoK API key set")

    headers = {"Api-Key": user.dok_api_key}
    now = datetime.datetime.utcnow()

    # --- Standard decks (paginated, 100/page) ---
    standard_count = 0
    needs_refresh = []
    page = 0
    while True:
        resp = requests.get(
            DOK_MY_DECKS_BASE, params={"page": page}, headers=headers, timeout=30
        )
        resp.raise_for_status()
        entries = resp.json()
        if not entries:
            break
        for entry in entries:
            dok_deck = entry.get("deck", {})
            kf_id = dok_deck.get("keyforgeId")
            if not kf_id:
                continue
            deck = get_or_create_deck_for_collection(
                kf_id,
                sas_rating=dok_deck.get("sasRating"),
                aerc_score=dok_deck.get("aercScore"),
            )
            row = UserDeckCollection.query.filter_by(
                user_id=user.id, deck_id=deck.id
            ).first()
            if row is None:
                row = UserDeckCollection(user_id=user.id, deck_id=deck.id)
                db.session.add(row)
            row.dok_owned = bool(entry.get("ownedByMe"))
            row.dok_wishlist = bool(entry.get("wishlist"))
            row.dok_funny = bool(entry.get("funny"))
            row.dok_notes = entry.get("notes")
            row.last_synced_at = now
            prod_id = dok_deck.get("id")
            if prod_id is not None and deck.dok is not None:
                deck.dok.prod_dok_id = int(prod_id)
            standard_count += 1
            if (
                len(deck.cards_from_assoc) < 36
                or len(deck.pod_stats) == 0
                or not deck.dok
                or deck.dok.last_refresh is None
            ):
                needs_refresh.append(deck.id)
        page += 1

    # --- Alliance decks (single call, no pagination) ---
    resp = requests.get(DOK_MY_ALLIANCES_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    alliance_entries = resp.json()
    alliance_count = 0
    for entry in alliance_entries:
        dok_deck = entry.get("deck", {})
        kf_id = dok_deck.get("keyforgeId")
        if not kf_id:
            continue
        adeck = AllianceDeck.query.filter_by(kf_id=kf_id).first()
        if adeck is None:
            adeck = AllianceDeck(kf_id=kf_id)
            db.session.add(adeck)
        adeck.name = dok_deck.get("name")
        adeck.sas_rating = dok_deck.get("sasRating")
        adeck.aerc_score = dok_deck.get("aercScore")
        adeck.synergy_rating = dok_deck.get("synergyRating")
        adeck.antisynergy_rating = dok_deck.get("antisynergyRating")
        adeck.valid_alliance = dok_deck.get("validAlliance")
        adeck.pods = [
            {
                "house": h.get("house"),
                "source_kf_id": h.get("keyforgeId"),
                "source_name": h.get("name"),
            }
            for h in dok_deck.get("allianceHouses", [])
        ]
        adeck.last_synced = now
        db.session.flush()
        arow = UserAllianceCollection.query.filter_by(
            user_id=user.id, alliance_deck_id=adeck.id
        ).first()
        if arow is None:
            arow = UserAllianceCollection(user_id=user.id, alliance_deck_id=adeck.id)
            db.session.add(arow)
        arow.dok_owned = bool(entry.get("ownedByMe"))
        arow.dok_wishlist = bool(entry.get("wishlist"))
        arow.dok_funny = bool(entry.get("funny"))
        arow.dok_notes = entry.get("notes")
        arow.last_synced_at = now
        alliance_count += 1

    db.session.commit()
    return {
        "standard_decks": standard_count,
        "alliance_decks": alliance_count,
        "refresh_deck_ids": needs_refresh,
    }


def run_background_pod_stats_backfill(app, stop_event=None, batch_sleep: float = 0.05):
    """Background thread: finds decks with cards but no pod stats and populates them.

    Uses GlobalVariable 'pod_stats_backfill_last_id' as a persistent cursor so
    the scan survives restarts. Exits once all decks have been processed.
    """
    import socket, time as _time

    logger = app.logger
    GVAR_NAME = "pod_stats_backfill_last_id"
    LOCK_NAME = "\0keytracker_pod_stats_backfill_lock"

    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        lock_socket.bind(LOCK_NAME)
    except OSError:
        logger.info("Another process already running pod stats backfill, skipping")
        return

    logger.info("Background pod stats backfill started")

    while stop_event is None or not stop_event.is_set():
        try:
            with app.app_context():
                gvar = GlobalVariable.query.filter_by(name=GVAR_NAME).first()
                if gvar is None:
                    gvar = GlobalVariable(name=GVAR_NAME, value_int=0)
                    db.session.add(gvar)
                    db.session.commit()

                last_id = gvar.value_int or 0
                deck = (
                    Deck.query
                    .filter(Deck.id > last_id)
                    .filter(~Deck.pod_stats.any())
                    .filter(Deck.cards_from_assoc.any())
                    .order_by(Deck.id)
                    .first()
                )

                if deck is None:
                    # Advance cursor to current max so future decks get picked up
                    max_id_row = db.session.execute(
                        db.select(db.func.max(Deck.id))
                    ).scalar()
                    if max_id_row and max_id_row > last_id:
                        gvar.value_int = max_id_row
                        db.session.commit()
                    logger.info("Pod stats backfill complete. Thread exiting.")
                    return

                try:
                    calculate_pod_stats(deck)
                    db.session.commit()
                except Exception:
                    logger.exception("Pod stats backfill failed for deck %s", deck.kf_id)
                    db.session.rollback()

                gvar.value_int = deck.id
                db.session.commit()
        except Exception:
            logger.exception("Pod stats backfill outer loop error")

        _time.sleep(batch_sleep)


def run_background_sas_backfill(app, stop_event=None, batch_sleep: float = 0.0):
    """Background thread: finds decks with outdated SAS data and refreshes them.

    Processes decks whose sas_version < LATEST_SAS_VERSION or that have no DokDeck
    record. Uses GlobalVariable 'sas_backfill_last_id' as a persistent cursor.
    Exits once all decks have been processed then restarts the cycle.
    """
    import socket, time as _time

    logger = app.logger
    GVAR_NAME = "sas_backfill_last_id"
    LOCK_NAME = "\0keytracker_sas_backfill_lock"

    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        lock_socket.bind(LOCK_NAME)
    except OSError:
        logger.info("Another process already running SAS backfill, skipping")
        return

    logger.info("Background SAS backfill started")

    while stop_event is None or not stop_event.is_set():
        try:
            with app.app_context():
                gvar = GlobalVariable.query.filter_by(name=GVAR_NAME).first()
                if gvar is None:
                    gvar = GlobalVariable(name=GVAR_NAME, value_int=0)
                    db.session.add(gvar)
                    db.session.commit()

                last_id = gvar.value_int or 0
                deck = (
                    Deck.query
                    .filter(Deck.id > last_id)
                    .filter(
                        db.or_(
                            Deck.sas_version < LATEST_SAS_VERSION,
                            Deck.sas_version.is_(None),
                            ~Deck.dok.has(),
                        )
                    )
                    .order_by(Deck.id)
                    .first()
                )

                if deck is None:
                    # Full cycle complete — reset cursor to 0 for next cycle
                    gvar.value_int = 0
                    db.session.commit()
                    logger.info(
                        "SAS backfill cycle complete, resetting cursor for next pass"
                    )
                    _time.sleep(3600)  # wait an hour before cycling again
                    continue

                try:
                    update_sas_scores(deck)
                except Exception:
                    logger.exception("SAS backfill failed for deck %s", deck.kf_id)

                gvar.value_int = deck.id
                db.session.commit()
        except Exception:
            logger.exception("SAS backfill outer loop error")
