from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    request,
)
from sqlalchemy import or_
from keytracker.schema import (
    db,
    Game,
    Log,
)
from keytracker.utils import (
    basic_stats_to_game,
    DuplicateGameError,
    get_deck_by_id_with_zeal,
    log_to_game,
    get_deck_by_id_with_zeal,
)
import datetime


blueprint = Blueprint("api", __name__, template_folder="templates")


@blueprint.route("/api/upload/v1", methods=["POST"])
def upload_whole_game():
    crucible_game_id = request.form["crucible_game_id"]
    game_start = datetime.datetime.fromisoformat(request.form["date"].rstrip("Z"))
    game = Game.query.filter_by(crucible_game_id=crucible_game_id).first()
    if game is None:
        current_app.logger.debug(f"Confirmed no existing record for {crucible_game_id}")
    else:
        raise DuplicateGameError(f"Found existing game for {crucible_game_id}")
    game = Game(
        crucible_game_id=request.form["crucible_game_id"],
        date=game_start,
        first_player=request.form["first_player"],
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
        log_obj = Log(
            game_id=game.id,
            message=log,
            winner_perspective=False,
            time=game_start + datetime.timedelta(seconds=seq),
        )
        db.session.add(log_obj)
    db.session.commit()
    db.session.refresh(game)
    turn_counts_from_logs(game)
    return make_response(jsonify(success=True), 201)


@blueprint.route("/api/upload_log/v1", methods=["POST"])
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
    db.session.refresh(game)
    turn_counts_from_logs(game)
    return make_response(jsonify(success=True), 201)


@blueprint.route("/api/simple_upload/v1", methods=["POST"])
def simple_upload():
    game = basic_stats_to_game(**request.form)
    existing_game = Game.query.filter_by(crucible_game_id=game.crucible_game_id).first()
    if existing_game is None:
        current_app.logger.debug(
            f"Confirmed no existing record for {game.crucible_game_id}"
        )
    else:
        raise DuplicateGameError(f"Found existing game for {game.crucible_game_id}")
    db.session.add(game)
    db.session.commit()
    return make_response(jsonify(success=True), 201)


@blueprint.route("/api/delete_game/v1/<game_id>", methods=["GET"])
def delete_game(game_id):
    game = Game.query.filter_by(crucible_game_id=game_id).one()
    Log.query.filter_by(game_id=game.id).delete()
    db.session.delete(game)
    db.session.commit()
    return make_response(jsonify(success=True), 201)


@blueprint.route("/api/load_deck_with_dok_data/v1/<deck_id>", methods=["POST"])
def load_deck_with_dok_data(deck_id):
    deck = get_deck_by_id_with_zeal(
        deck_id,
        sas_rating=request.form.get("sas_rating"),
        aerc_score=request.form.get("aerc_score"),
    )
    return make_response(jsonify(success=True, deck_name=deck.name), 201)
