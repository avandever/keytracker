from flask import (
    Blueprint,
    flash,
    render_template,
    redirect,
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


@blueprint.route("/deck/<deck_id>", methods=["GET"])
def deck(deck_id):
    deck_games = (
        Game.query
            .filter(
                (Game.winner_deck_id == deck_id) | (Game.loser_deck_id == deck_id)
            ).order_by(Game.date.desc())
            .all()
    )
    if len(deck_games) == 0:
        flash(f"No games found for deck {deck_id}")
        return redirect("/")
    game = deck_games[0]
    deck_name = game.winner_deck_name if game.winner_deck_id == deck_id else game.loser_deck_name
    return render_template(
        "deck.html",
        title=f"{deck_name} Deck Summary",
        games=deck_games,
        deck_name=deck_name,
        deck_id=deck_id,
    )


@blueprint.route("/game/<crucible_game_id>", methods=["GET"])
def game(crucible_game_id):
    game = Game.query.filter_by(crucible_game_id=crucible_game_id).first()
    return render_template(
        "game.html",
        title=f"{game.winner} vs {game.loser}",
        game=game,
    )


@blueprint.route("/user", methods=["GET", "POST"])
@blueprint.route("/user/", methods=["GET", "POST"])
def user_search():
    """User Search Page"""
    if request.method == "POST":
        return redirect(f"/user/{request.form['username']}")
    return render_template(
        "user_search.html",
        title="User Search",
    )


@blueprint.route("/user/<username>", methods=["GET"])
def user(username):
    """User Summary Page"""
    user_games = (
        Game.query
            .filter(
                (Game.winner == username) | (Game.loser == username)
            ).order_by(Game.date.desc())
            .all()
    )
    if len(user_games) == 0:
        flash(f"No games found for user {username}")
        return redirect("/user")
    return render_template(
        "user.html",
        title=f"{username} games",
        username=username,
        games=user_games,
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
