from flask import (
    Blueprint,
    flash,
    render_template,
    redirect,
    request,
    url_for,
)
from keytracker.schema import (
    db,
    Deck,
    Game,
    Log,
    Player,
)
from keytracker.utils import (
    add_player_filters,
    add_game_sort,
    anonymize_game_for_player,
    BadLog,
    basic_stats_to_game,
    DeckNotFoundError,
    get_deck_by_id_with_zeal,
    log_to_game,
    turn_counts_from_logs,
)
import datetime
import time
import logging
from sqlalchemy import and_, or_


blueprint = Blueprint("ui", __name__, template_folder="templates")
logger = logging.getLogger(__name__)


@blueprint.route("/")
def home():
    """Landing page."""
    last_five_games = Game.query.order_by(Game.date.desc()).limit(5).all()
    return render_template(
        "home.html",
        title="Bear Tracks",
        description="KeyForge Game Records and Analysis",
        games=last_five_games,
    )


@blueprint.route("/privacy")
def privacy():
    """Privacy policy."""
    return render_template(
        "privacy.html",
        title="Privacy Policy",
        description="Bear Tracks Privacy Policy",
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
    username = request.args.get("username")
    before = time.time()
    deck = get_deck_by_id_with_zeal(deck_id)
    after = time.time()
    print(f"Took {int(after - before)} s to get deck")
    if username is not None:
        before = time.time()
        games_won = Game.query.filter(
            and_(
                Game.winner_deck_dbid == deck.id,
                Game.winner == username,
            )
        ).count()
        after = time.time()
        print(f"Took {int(after - before)} s to get win count")
        before = time.time()
        games_lost = Game.query.filter_by(
            and_(
                Game.loser_deck_dbid == deck.id,
                Game.loser == username,
            )
        ).count()
        after = time.time()
        print(f"Took {int(after - before)} s to get loss count")
        before = time.time()
        deck_games = (
            add_player_filters(Game.query, username, deck_dbid=deck.id)
            .order_by(Game.date.desc())
            .all()
        )
        after = time.time()
        print(f"Took {int(after - before)} s to get games")
    else:
        before = time.time()
        games_won = Game.query.filter_by(winner_deck_dbid=deck.id).count()
        after = time.time()
        print(f"Took {int(after - before)} s to get win count")
        before = time.time()
        games_lost = Game.query.filter_by(loser_deck_dbid=deck.id).count()
        after = time.time()
        print(f"Took {int(after - before)} s to get loss count")
        before = time.time()
        deck_games = (
            add_player_filters(Game.query, deck_dbid=deck.id)
            .order_by(Game.date.desc())
            .all()
        )
        after = time.time()
        print(f"Took {int(after - before)} s to get games")
    if len(deck_games) == 0:
        flash(f"No games found for deck {deck_id}")
        return redirect(url_for("ui.home"))
    return render_template(
        "deck.html",
        title=f"{deck.name} Deck Summary",
        games=deck_games,
        deck_name=deck.name,
        deck_id=deck.kf_id,
        games_won=games_won,
        games_lost=games_lost,
    )


@blueprint.route("/game/<crucible_game_id>", methods=["GET"])
def game(crucible_game_id):
    game = Game.query.filter_by(crucible_game_id=crucible_game_id).first()
    players = sorted(
        [game.winner, game.loser],
        key=lambda x: x != game.insist_first_player,
    )
    return render_template(
        "game.html",
        title=" vs ".join(players),
        game=game,
    )


@blueprint.route("/games", methods=["GET"])
def games():
    args_list = ["user", "deck", "sas_min", "sas_max", "aerc_min", "aerc_max"]
    if any(
        (
            request.args.get("user1"),
            request.args.get("deck1"),
        )
    ):
        query = Game.query
        query = add_player_filters(
            query, *map(request.args.get, [f"{x}1" for x in args_list])
        )
        query = add_player_filters(
            query, *map(request.args.get, [f"{x}2" for x in args_list])
        )
        query = add_game_sort(
            query, [(request.args.get("sort1"), request.args.get("direction1"))]
        )
        games = query.limit(10).all()
    else:
        games = None
    return render_template(
        "games.html",
        title=f"Games Search",
        args=request.args,
        games=games,
        sort_options={
            "date": "Date",
            "loser_keys": "Keys forged by loser",
            "combined_sas_rating": "Total SAS",
            "winner_sas_rating": "Winner SAS",
            "loser_sas_rating": "Loser SAS",
            "combined_aerc_score": "Total AERC",
            "winner_aerc_score": "Winner AERC",
            "loser_aerc_score": "Loser AERC",
        },
    )


@blueprint.route("/user", methods=["GET", "POST"])
@blueprint.route("/user/", methods=["GET", "POST"])
def user_search():
    """User Search Page"""
    if request.method == "POST":
        return redirect(url_for("ui.user", username=request.form["username"]))
    return render_template(
        "user_search.html",
        title="User Search",
    )


@blueprint.route("/user/<username>", methods=["GET"])
def user(username):
    """User Summary Page"""
    games_won = Game.query.filter(Game.winner == username).count()
    games_lost = Game.query.filter(Game.loser == username).count()
    user_games = (
        Game.query.filter((Game.winner == username) | (Game.loser == username))
        .order_by(Game.date.desc())
        .limit(10000)
        .all()
    )
    if len(user_games) == 0:
        flash(f"No games found for user {username}")
        return redirect(url_for("ui.user_search"))
    return render_template(
        "user.html",
        title=f"{username} games",
        username=username,
        games=user_games,
        games_won=games_won,
        games_lost=games_lost,
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
            db.session.refresh(game)
            turn_counts_from_logs(game)
            winner = Player.query.filter_by(username=game.winner).first()
            loser = Player.query.filter_by(username=game.loser).first()
            if winner.anonymous:
                anonymize_game_for_player(game, winner)
            if loser.anonymous:
                anonymize_game_for_player(game, loser)
            game_reloaded = None
            while game_reloaded is None:
                time.sleep(0.5)
                game_reloaded = Game.query.filter_by(
                    crucible_game_id=game.crucible_game_id,
                ).first()
            return redirect(url_for("ui.game", crucible_game_id=game.crucible_game_id))
    return render_template(
        "upload.html",
        title="Upload a Game!",
    )


@blueprint.route("/upload_simple", methods=("GET", "POST"))
def upload_simple():
    """Manual game upload page with just simple options"""
    if request.method == "POST":
        game = basic_stats_to_game(**request.form)
        existing_game = Game.query.filter_by(
            crucible_game_id=game.crucible_game_id
        ).first()
        if existing_game is None:
            logger.debug(f"Confirmed no existing record for {game.crucible_game_id}")
            db.session.add(game)
            db.session.commit()
            return redirect(url_for("ui.game", crucible_game_id=game.crucible_game_id))
        else:
            flash(f"A game with name '{game.crucible_game_id}' already exists")
    return render_template(
        "upload_simple.html",
        title="Simple Game Upload",
    )
