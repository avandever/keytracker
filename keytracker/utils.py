from collections import Counter, defaultdict
from keytracker.schema import Game
from typing import Dict
import re


PLAYER_DECK_MATCHER = re.compile(r"^(.*) brings (.*) to The Crucible$")
FIRST_PLAYER_MATCHER = re.compile(r"^(.*) won the flip")
SHUFFLE_MATCHER = re.compile(r"^(.*) is shuffling their deck$")
HOUSE_CHOICE_MATCHER = re.compile(r"^(.*) chooses (.*) as their active house")
FORGE_MATCHER = re.compile(r"^(.*) forges the (.*) key ?, paying [0-9]+ Æmber$")
WIN_MATCHER = re.compile(r"^ ?(.*) has won the game$")


class BadLog(Exception):
    pass


class UnknownDBDriverException(Exception):
    pass


def config_to_uri(
    driver: str = "sqlite",
    path: str = "keyforge_cards.sqlite",
    host: str = "localhost",
    port: int = None,
    user: str = None,
    password: str = None,
    database: str = "keyforge_decks",
) -> str:
    uri_bits = [driver, "://"]
    if driver == "sqlite":
        uri_bits.append("/")
        uri_bits.append(path)
    elif driver in ["postgresql", "mysql"]:
        if user is not None:
            uri_bits.append(user)
            if password is not None:
                uri_bits.append(":")
                uri_bits.append(password)
        uri_bits.append("@")
        uri_bits.append(host)
        if port is not None:
            uri_bits.append(":")
            uri_bits.append(port)
        uri_bits.append("/")
        uri_bits.append(database)
    else:
        raise UnknownDBDriverException(f"Unrecognized DB Driver: {driver}")
    return "".join(uri_bits)


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
    print(f"Winning deck: {winner.deck_name}")
    print(f"Losing deck: {loser.deck_name}")
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


def deck_name_to_id(deck_name: str) -> str:
    return "Not Implemented"
