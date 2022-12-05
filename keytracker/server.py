#!/usr/bin/env python3
from flask import Flask, request, jsonify, make_response, render_template
from flask_sqlalchemy import SQLAlchemy
import configparser
from keytracker.schema import (
    db,
    Game,
    HouseTurnCounts,
    TurnState,
    Log,
)
from keytracker.utils import (
    config_to_uri,
    render_log,
    log_to_game,
)
from sqlalchemy.orm.exc import NoResultFound
import datetime

app = Flask(__name__)
cparser = configparser.ConfigParser()
cparser.read("config.ini")
app.config["SQLALCHEMY_DATABASE_URI"] = config_to_uri(**cparser["db"])
db.app = app
db.init_app(app)
db.create_all()
app.jinja_env.globals.update(render_log=render_log)


class DuplicateGameError(Exception):
    pass


@app.route("/")
def home():
    """Landing page."""
    last_five_games = Game.query.order_by(Game.date.desc()).limit(5).all()
    return render_template(
        "home.html",
        title="Bear Tracks",
        games=last_five_games,
    )


@app.route("/fame")
def hall_of_fame():
    """Hall of fame"""
    return render_template(
        "coming_soon.html",
        title="Hall of Fame",
        description="",
    )


@app.route("/leaderboard")
def leaderboard():
    """Leaderboard"""
    return render_template(
        "coming_soon.html",
        title="Leaderboard",
        description="",
    )


@app.route("/game/<crucible_game_id>", methods=["GET"])
def game(crucible_game_id):
    game = Game.query.filter_by(crucible_game_id=crucible_game_id).first()
    return render_template(
        "game.html",
        title=f"{game.winner} vs {game.loser}",
        game=game,
    )


@app.route("/user/<username>", methods=["GET"])
def user(username):
    """User Summary Page"""
    return render_template(
        "coming_soon.html",
        title=username,
    )


@app.route("/api/upload/v1", methods=["POST"])
def upload_whole_game():
    crucible_game_id = request.form["crucible_game_id"]
    game_start = datetime.datetime.fromisoformat(request.form["date"].rstrip("Z"))
    game = Game.query.filter_by(crucible_game_id=crucible_game_id).first()
    if game is None:
        app.logger.debug(f"Confirmed no existing record for {crucible_game_id}")
    else:
        raise DuplicateGameError(f"Found existing game for {crucible_game_id}")
    game = Game(
        crucible_game_id=request.form['crucible_game_id'],
        date=game_start,
        winner=request.form["winner"],
        winner_deck_id=request.form["winner_deck_id"],
        winner_deck_name=request.form["winner_deck_name"],
        winner_keys=request.form["winner_keys"],
        loser=request.form["loser"],
        loser_deck_id=request.form["loser_deck_id"],
        loser_deck_name=request.form["loser_deck_name"],
        loser_keys=request.form["loser_keys"],
    )
    db.session.add(game)
    db.session.commit()
    log_text = request.form["log"]
    for (seq, log) in enumerate(log_text.split("\n")):
        #log_obj = Log(game=game, message=log, time=datetime.datetime.fromtimestamp(seq), winner_perspective=False)
        log_obj = Log(
            game_id=game.id,
            message=log,
            winner_perspective=False,
            time=game_start + datetime.timedelta(seconds=seq),
        )
        db.session.add(log_obj)
    db.session.commit()
    return make_response(jsonify(success=True), 201)


@app.route("/api/upload_log/v1", methods=["POST"])
def upload_log():
    date = request.form.get("date")
    if date is None:
        game_start = datetime.datetime.now()
    else:
        game_start = datetime.datetime.fromisoformat(date.rstrip("Z"))
    log_text = request.form["log"]
    game = log_to_game(log_text)
    game.date = game_start
    db.session.add(game)
    db.session.commit()
    db.session.refresh(game)
    game.crucible_game_id = f"UNKNOWN-{game.id}"
    db.session.commit()
    for (seq, log) in enumerate(log_text.split("\n")):
        log_obj = Log(
            game_id=game.id,
            message=log,
            winner_perspective=False,
            time=game_start + datetime.timedelta(seconds=seq),
        )
        db.session.add(log_obj)
    db.session.commit()
    return make_response(jsonify(success=True), 201)


if __name__ == "__main__":
    app.run(debug=True)
