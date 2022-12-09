from flask import (
    Blueprint,
    flash,
    render_template,
    request,
)
from keytracker.schema import (
    db,
    Game,
    Log,
)
from keytracker.utils import (
    BadLog,
    DeckNotFoundError,
    log_to_game,
)
import datetime


blueprint = Blueprint("ui", __name__, template_folder="templates")


@blueprint.route("/")
def home():
    """Landing page."""
    last_five_games = Game.query.order_by(Game.date.desc()).limit(5).all()
    return render_template(
        "home.html",
        title="Bear Tracks",
        games=last_five_games,
    )


@blueprint.route("/fame")
def hall_of_fame():
    """Hall of fame"""
    return render_template(
        "coming_soon.html",
        title="Hall of Fame",
        description="",
    )


@blueprint.route("/leaderboard")
def leaderboard():
    """Leaderboard"""
    return render_template(
        "coming_soon.html",
        title="Leaderboard",
        description="",
    )


@blueprint.route("/game/<crucible_game_id>", methods=["GET"])
def game(crucible_game_id):
    game = Game.query.filter_by(crucible_game_id=crucible_game_id).first()
    return render_template(
        "game.html",
        title=f"{game.winner} vs {game.loser}",
        game=game,
    )


@blueprint.route("/user/<username>", methods=["GET"])
def user(username):
    """User Summary Page"""
    return render_template(
        "coming_soon.html",
        title=username,
    )


@blueprint.route("/upload", methods=("GET", "POST"))
def upload():
    """Manual game upload page"""
    if request.method == "POST":
        game_start = datetime.datetime.now()
        log_text = request.form["log"]
        try:
            game = log_to_game(log_text)
        except (BadLog, DeckNotFoundError) as exc:
            flash(str(exc))
        else:
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
            return render_template(
                "upload.html",
                title="Upload a Game!",
                success=f"{game.winner} vs. {game.loser}",
            )
    return render_template(
        "upload.html",
        title="Upload a Game!",
    )
