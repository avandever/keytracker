#!/usr/bin/env python3
from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
import configparser
from schema import db, Game, HouseTurnCounts, TurnState, Log
from utils import config_to_uri
import datetime

app = Flask(__name__)
cparser = configparser.ConfigParser()
cparser.read("config.ini")
app.config["SQLALCHEMY_DATABASE_URI"] = config_to_uri(**cparser["db"])
db.app = app
db.init_app(app)
db.create_all()


@app.route("/api/upload/v1", methods=["POST"])
def upload_whole_game():
    game = Game(
        crucible_game_id=request.form['crucible_game_id'],
        date=None,
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
        log_obj = Log(game_id=game.id, message=log, winner_perspective=False)
        db.session.add(log_obj)
    db.session.commit()
    return make_response(jsonify(success=True), 201)


if __name__ == "__main__":
    app.run(debug=True)
