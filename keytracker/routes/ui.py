from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)
import patreon
from flask_login import (
    login_required,
    login_user,
    logout_user,
    current_user,
)
from flask import (
    Blueprint,
    flash,
    render_template,
    redirect,
    request,
    send_from_directory,
    send_file,
    url_for,
)
from keytracker.schema import (
    CardInDeck,
    db,
    Deck,
    Game,
    Log,
    Player,
    User,
)
from keytracker.utils import (
    add_player_filters,
    add_game_sort,
    anonymize_game_for_player,
    BadLog,
    basic_stats_to_game,
    DeckNotFoundError,
    get_deck_by_id_with_zeal,
    house_stats_to_csv,
    log_to_game,
    parse_house_stats,
    turn_counts_from_logs,
)
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload
import datetime
import time
import logging
import os


blueprint = Blueprint("ui", __name__, template_folder="templates")
logger = logging.getLogger(__name__)


patreon_client_id = os.getenv("PATREON_CLIENT_ID")
patreon_client_secret = os.getenv("PATREON_CLIENT_SECRET")


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
    deck = get_deck_by_id_with_zeal(deck_id)
    if username is not None:
        games_won = Game.query.filter(
            and_(
                Game.winner_deck_dbid == deck.id,
                Game.winner == username,
            )
        ).count()
        games_lost = Game.query.filter(
            and_(
                Game.loser_deck_dbid == deck.id,
                Game.loser == username,
            )
        ).count()
        deck_games = (
            add_player_filters(Game.query, username, deck_dbid=deck.id)
            .order_by(Game.date.desc())
            .all()
        )
    else:
        games_won = Game.query.filter_by(winner_deck_dbid=deck.id).count()
        games_lost = Game.query.filter_by(loser_deck_dbid=deck.id).count()
        deck_games = (
            add_player_filters(Game.query, deck_dbid=deck.id)
            .order_by(Game.date.desc())
            .all()
        )
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
    if game is None:
        return render_template(
            "game_missing.html",
            crucible_game_id=crucible_game_id,
        )
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


@blueprint.route("/decks", methods=["GET"])
def decks():
    if request.args:
        query = Deck.query
        sas_min = request.args.get("sas_min")
        if sas_min:
            query = query.filter(Deck.sas_rating >= sas_min)
        sas_max = request.args.get("sas_max")
        if sas_max:
            query = query.filter(Deck.sas_rating <= sas_max)
        aerc_min = request.args.get("aerc_min")
        if aerc_min:
            query = query.filter(Deck.aerc_score >= aerc_min)
        aerc_max = request.args.get("aerc_max")
        if aerc_max:
            query = query.filter(Deck.aerc_score <= aerc_max)
        decks = query.all()
    else:
        decks = None
    return render_template(
        "decks.html",
        title=f"Decks Search",
        args=request.args,
        decks=decks,
    )


@blueprint.route("/csv_to_pods", methods=["GET"])
def csv_to_pods():
    """CSV to Pod Stats Page"""
    return render_template(
        "csv_to_pods_landing.html",
        title="Pod Stats From CSV",
    )


@blueprint.route("/csv_to_pods", methods=["POST"])
def csv_to_pods_post():
    max_decks = 1000
    max_to_fetch = 2
    decks_csv = request.files["decks_csv"]
    result_type = request.form["result_type"]
    show_card_images = bool(request.form.get("show_card_images"))
    hide_set = bool(request.form.get("hide_set"))
    house_stats = parse_house_stats(decks_csv, max_decks=max_decks)
    if result_type == "csv":
        output_csv = house_stats_to_csv(house_stats)
        output_filename = decks_csv.filename.replace(".csv", "_pod_stats.csv")
        return send_file(
            output_csv,
            download_name=output_filename,
            as_attachment=True,
        )
        response = make_response(output_csv)
        response.headers["Content-Disposition"] = "attachment; filename=pod_stats.csv"
        return response
    else:
        kf_ids = {pod.link.split("/")[-1] for pod in house_stats}
        decks = Deck.query.options(
            joinedload(Deck.cards_from_assoc).joinedload(CardInDeck.card_in_set)
        ).filter(Deck.kf_id.in_(kf_ids))
        missing_deck_count = len(kf_ids) - decks.count()
        name_to_deck = {deck.name: deck for deck in decks}
        if missing_deck_count > 0:
            missing_kf_ids = kf_ids - {d.kf_id for d in decks}
            if missing_deck_count <= max_to_fetch:
                logger.debug("Missing one or two decks, attempting to fetch.")
                for kf_id in missing_kf_ids:
                    deck = get_deck_by_id_with_zeal(kf_id)
                    name_to_deck[deck.name] = deck
            else:
                logger.debug("Missing too many decks from db, skipping some.")
                flash(
                    f"Warning: {missing_deck_count} unrecognized decks in csv. Skipping them for now, but if you try again later they may be available."
                )
                house_stats = [p for p in house_stats if p.name in name_to_deck.keys()]
        return render_template(
            "csv_to_pods.html",
            house_stats=house_stats,
            max_decks=max_decks,
            name_to_deck=name_to_deck,
            show_card_images=show_card_images,
            hide_set=hide_set,
        )


@blueprint.route("/user", methods=["GET"])
def user_search():
    """User Search Page"""
    return render_template(
        "user_search.html",
        title="User Search",
    )


@blueprint.route("/user", methods=["POST"])
def user_search_post():
    """User Search Page"""
    return redirect(url_for("ui.user", username=request.form["username"]))


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


@blueprint.route("/upload", methods=["GET"])
def upload():
    return render_template(
        "upload.html",
        title="Upload a Game!",
    )


@blueprint.route("/upload", methods=["POST"])
def upload_post():
    """Manual game upload page"""
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
        for seq, log in enumerate(log_text.split("\n")):
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
        time.sleep(20)
        return redirect(url_for("ui.game", crucible_game_id=game.crucible_game_id))
    return render_template(
        "upload.html",
        title="Upload a Game!",
    )


@blueprint.route("/upload_simple", methods=["GET"])
def upload_simple():
    """Manual game upload page with just simple options"""
    return render_template(
        "upload_simple.html",
        title="Simple Game Upload",
    )


@blueprint.route("/upload_simple", methods=["POST"])
def upload_simple_post():
    """Manual game upload page with just simple options"""
    game = basic_stats_to_game(**request.form)
    existing_game = Game.query.filter_by(crucible_game_id=game.crucible_game_id).first()
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


@blueprint.route("/login")
def login():
    return render_template("login.html")


@blueprint.route("/login", methods=["POST"])
def login_post():
    # login code here
    email = request.form.get("email")
    password = request.form.get("password")
    remember = bool(request.form.get("remember"))

    user = User.query.filter_by(email=email).first()

    if user and check_password_hash(user.password, password):
        login_user(user, remember=remember)
        return redirect(url_for("ui.profile"))
    else:
        flash("Please check your login details and try again.")
        return redirect(url_for("ui.login"))


@blueprint.route("/signup")
def signup():
    return render_template("signup.html")


@blueprint.route("/signup", methods=["POST"])
def signup_post():
    # Add user
    email = request.form.get("email")
    name = request.form.get("name")
    password = request.form.get("password")
    user = User.query.filter_by(email=email).first()
    if user:
        flash("Email address already exists")
        return redirect(url_for("ui.signup"))
    new_user = User(
        email=email,
        name=name,
        password=generate_password_hash(password),
    )
    db.session.add(new_user)
    db.session.commit()
    return redirect(url_for("ui.login"))


@blueprint.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Successfully logged out.")
    return redirect(url_for("ui.home"))


@blueprint.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=current_user)


@blueprint.route("/oauth/redirect")
def oauth_redirect():
    oauth_client = patreon.OAuth(patreon_client_id, patreon_client_secret)
    tokens = oauth_client.get_tokens(
        request.args.get("code"),
        "https://tracker.ancientbearrepublic.com/oauth/redirect",
    )
    print(f"tokens: {tokens}")
    access_token = tokens["access_token"]
    api_client = patreon.API(access_token)
    user_response = api_client.get_identity()
    user = user_response.data()
    memberships = user.relationship("memberships")
    membership = memberships[0] if memberships and len(memberships) > 0 else None
    print(memberships)
    return str(memberships)


@blueprint.route("/patreon")
def patreon():
    return render_template("patreon.html")


@blueprint.route("/robots.txt")
def static_from_root():
    return send_from_directory("static", request.path[1:])
