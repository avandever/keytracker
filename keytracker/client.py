#!/usr/bin/env python3
# from aiohttp_requests import requests
import requests
import json
import click
import os
from schema import db


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


if __name__ == "__main__":
    cli()
