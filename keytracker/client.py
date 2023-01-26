#!/usr/bin/env python3
# from aiohttp_requests import requests
import requests
import json
import click
import csv
import os
from schema import db
import time


def game_to_api(path: str, site_root: str) -> None:
    """
    Given a path to a directory containing files game.json and log.json, upload the game
    summary and logs to the tracker api
    """
    uri = f"{site_root}/api/upload/v1"
    game_path = os.path.join(path, "game.json")
    log_path = os.path.join(path, "log.json")
    post_data = {}
    with open(game_path, "r") as fh:
        game_data = json.load(fh)
    with open(log_path, "r") as fh:
        log_data = json.load(fh)
    post_data["crucible_game_id"] = game_data["crucible_game_id"]
    post_data["date"] = game_data["date"]
    post_data["winner"] = game_data["winner"]
    post_data["winner_deck_id"] = game_data["winner_deck_id"]
    post_data["winner_deck_name"] = game_data["winner_deck_name"]
    post_data["winner_keys"] = game_data["winner_keys"]
    post_data["loser"] = game_data["loser"]
    post_data["loser_deck_id"] = game_data["loser_deck_id"]
    post_data["loser_deck_name"] = game_data["loser_deck_name"]
    post_data["loser_keys"] = game_data["loser_keys"]
    post_data["log"] = "\n".join(log_data)
    requests.post(uri, post_data)


@click.group()
def cli():
    pass


@cli.command()
@click.argument("game_path", type=str)
@click.option("--host", type=str, default="127.0.0.1")
@click.option("--port", type=int, default=5000)
def upload(game_path: str, host: str, port: int) -> None:
    site_root = f"http://{host}:{port}"
    game_to_api(game_path, site_root)


@cli.command()
@click.argument("log", type=click.File("r"))
@click.option("--host", type=str, default="127.0.0.1")
@click.option("--port", type=int, default=5000)
def upload_log(log, host, port):
    site_root = f"http://{host}:{port}"
    uri = f"{site_root}/api/upload_log/v1"
    requests.post(uri, {"log": log.read()})


@cli.command()
@click.argument("user_file", type=click.File("r"))
@click.option("--host", type=str, default="127.0.0.1")
@click.option("--port", type=int, default=5000)
def simple_upload_user_games(user_file, host, port):
    site_root = f"http://{host}:{port}"
    uri = f"{site_root}/api/simple_upload/v1"
    data = json.load(user_file)
    for game in data:
        requests.post(uri, game)


@cli.command()
@click.argument("game_id", type=str)
@click.option("--host", type=str, default="127.0.0.1")
@click.option("--port", type=int, default=5000)
def delete_game(game_id, host, port):
    site_root = f"http://{host}:{port}"
    uri = f"{site_root}/api/delete_game/v1/{game_id}"
    requests.get(uri)


@cli.command()
@click.argument("dok_csv", type=click.File("r"))
@click.option("--host", type=str, default="127.0.0.1")
@click.option("--port", type=int, default=5000)
@click.option("--sleep", type=float, default=0.0)
def load_decks_from_dok_csv(dok_csv, host, port, sleep):
    site_root = f"https://{host}:{port}"
    base_uri = f"{site_root}/api/load_deck_with_dok_data/v1"
    reader = csv.reader(dok_csv)
    first_row = next(reader)
    id_idx = first_row.index("keyforge_id")
    sas_idx = first_row.index("sas_rating")
    aerc_idx = first_row.index("aerc_score")
    for row in reader:
        keyforge_id = row[id_idx]
        sas_rating = row[sas_idx]
        aerc_score = row[aerc_idx]
        print(f"Submitting {keyforge_id}")
        response = requests.post(
            f"{base_uri}/{keyforge_id}",
            params={"sas_rating": sas_rating, "aerc_score": aerc_score},
        )
        print(response.text)
        time.sleep(sleep)


if __name__ == "__main__":
    cli()
