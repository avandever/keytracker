from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    request,
)
from keytracker.schema import (
    db,
    Game,
    Log,
)
from keytracker.utils import (
    DuplicateGameError,
    log_to_game,
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
    return make_response(jsonify(success=True), 201)
