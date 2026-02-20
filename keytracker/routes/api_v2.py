from flask import (
    Blueprint,
    current_app,
    jsonify,
    request,
)
from flask_login import current_user, login_required
from keytracker.schema import (
    db,
    Deck,
    Game,
    Log,
    Player,
    TcoUsername,
    User,
)
from keytracker.serializers import (
    serialize_deck_detail,
    serialize_deck_summary,
    serialize_game_detail,
    serialize_game_summary,
)
from keytracker.utils import (
    add_player_filters,
    add_game_sort,
    BadLog,
    basic_stats_to_game,
    DeckNotFoundError,
    DuplicateGameError,
    get_deck_by_id_with_zeal,
    house_stats_to_csv,
    log_to_game,
    parse_house_stats,
    turn_counts_from_logs,
    username_to_player,
    anonymize_game_for_player,
)
from sqlalchemy import or_
import datetime
import re
import time


blueprint = Blueprint("api_v2", __name__, url_prefix="/api/v2")

@blueprint.route("/auth/me")
def auth_me():
    if current_user.is_authenticated:
        return jsonify(
            {
                "id": current_user.id,
                "email": current_user.email,
                "name": current_user.name,
                "avatar_url": current_user.avatar_url,
                "is_patron": current_user.is_patron,
                "is_member": current_user.is_member,
                "patreon_tier_title": current_user.patreon_tier_title,
                "patreon_linked": current_user.patreon_id is not None,
                "dok_api_key": current_user.dok_api_key,
                "tco_usernames": [t.username for t in current_user.tco_usernames],
                "is_league_admin": current_user.is_league_admin,
                "dok_profile_url": current_user.dok_profile_url,
                "country": current_user.country,
                "timezone": current_user.timezone,
            }
        )
    return jsonify({"error": "Not authenticated"}), 401


UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@blueprint.route("/auth/settings", methods=["PUT"])
@login_required
def auth_settings():
    data = request.get_json(silent=True) or {}
    if "dok_api_key" in data:
        val = (data["dok_api_key"] or "").strip()
        if val == "":
            current_user.dok_api_key = None
        elif UUID4_RE.match(val):
            current_user.dok_api_key = val
        else:
            return jsonify({"error": "Invalid DoK API key format (expected UUID v4)"}), 400
    if "dok_profile_url" in data:
        val = (data["dok_profile_url"] or "").strip()
        if val == "":
            current_user.dok_profile_url = None
        elif val.startswith("https://decksofkeyforge.com/"):
            current_user.dok_profile_url = val
        else:
            return (
                jsonify(
                    {
                        "error": "DoK profile URL must start with https://decksofkeyforge.com/"
                    }
                ),
                400,
            )
    if "country" in data:
        val = (data["country"] or "").strip()
        current_user.country = val if val else None
    if "timezone" in data:
        val = (data["timezone"] or "").strip()
        current_user.timezone = val if val else None
    if "tco_usernames" in data:
        names = data["tco_usernames"]
        if not isinstance(names, list):
            return jsonify({"error": "tco_usernames must be a list"}), 400
        cleaned = []
        for n in names:
            if not isinstance(n, str):
                return jsonify({"error": "Each TCO username must be a string"}), 400
            n = n.strip()
            if n and len(n) <= 100:
                cleaned.append(n)
        TcoUsername.query.filter_by(user_id=current_user.id).delete()
        for name in cleaned:
            db.session.add(TcoUsername(user_id=current_user.id, username=name))
    db.session.commit()
    return jsonify({
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "avatar_url": current_user.avatar_url,
        "is_patron": current_user.is_patron,
        "is_member": current_user.is_member,
        "patreon_tier_title": current_user.patreon_tier_title,
        "patreon_linked": current_user.patreon_id is not None,
        "dok_api_key": current_user.dok_api_key,
        "tco_usernames": [t.username for t in current_user.tco_usernames],
        "is_league_admin": current_user.is_league_admin,
        "dok_profile_url": current_user.dok_profile_url,
        "country": current_user.country,
        "timezone": current_user.timezone,
    })


SORT_ALLOWLIST = {
    "date",
    "loser_keys",
    "combined_sas_rating",
    "winner_sas_rating",
    "loser_sas_rating",
    "combined_aerc_score",
    "winner_aerc_score",
    "loser_aerc_score",
}


@blueprint.route("/games/mine")
@login_required
def games_mine():
    usernames = [t.username for t in current_user.tco_usernames]
    if not usernames:
        return jsonify({
            "error": "No TCO usernames configured",
            "tco_usernames": [],
            "games_won": 0,
            "games_lost": 0,
            "games": [],
        })
    games_won = Game.query.filter(Game.winner.in_(usernames)).count()
    games_lost = Game.query.filter(Game.loser.in_(usernames)).count()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    offset = (page - 1) * per_page
    user_games = (
        Game.query.filter(
            or_(Game.winner.in_(usernames), Game.loser.in_(usernames))
        )
        .order_by(Game.date.desc())
        .limit(per_page)
        .offset(offset)
        .all()
    )
    return jsonify({
        "tco_usernames": usernames,
        "games_won": games_won,
        "games_lost": games_lost,
        "games": [serialize_game_summary(g) for g in user_games],
    })


@blueprint.route("/games/recent")
def games_recent():
    limit = request.args.get("limit", 5, type=int)
    limit = min(limit, 50)
    games = Game.query.order_by(Game.date.desc()).limit(limit).all()
    return jsonify([serialize_game_summary(g) for g in games])


@blueprint.route("/games/search")
def games_search():
    args_list = ["user", "deck", "sas_min", "sas_max", "aerc_min", "aerc_max"]
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    query = Game.query

    if any(request.args.get(f"{x}1") for x in args_list):
        query = add_player_filters(
            query, *[request.args.get(f"{x}1") for x in args_list]
        )
        query = add_player_filters(
            query, *[request.args.get(f"{x}2") for x in args_list]
        )

        sort_col = request.args.get("sort1", "date")
        direction = request.args.get("direction1", "desc")
        if sort_col in SORT_ALLOWLIST and direction in ("asc", "desc"):
            query = add_game_sort(query, [(sort_col, direction)])
        else:
            query = query.order_by(Game.date.desc())
    else:
        query = query.order_by(Game.date.desc())

    offset = (page - 1) * per_page
    games = query.limit(per_page).offset(offset).all()
    return jsonify([serialize_game_summary(g) for g in games])


@blueprint.route("/games/<crucible_game_id>")
def game_detail(crucible_game_id):
    game = Game.query.filter_by(crucible_game_id=crucible_game_id).first()
    if game is None:
        return jsonify({"error": "Game not found"}), 404
    return jsonify(serialize_game_detail(game))


@blueprint.route("/decks/search")
def decks_search():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    query = Deck.query
    sas_min = request.args.get("sas_min", type=int)
    if sas_min is not None:
        query = query.filter(Deck.sas_rating >= sas_min)
    sas_max = request.args.get("sas_max", type=int)
    if sas_max is not None:
        query = query.filter(Deck.sas_rating <= sas_max)
    aerc_min = request.args.get("aerc_min", type=int)
    if aerc_min is not None:
        query = query.filter(Deck.aerc_score >= aerc_min)
    aerc_max = request.args.get("aerc_max", type=int)
    if aerc_max is not None:
        query = query.filter(Deck.aerc_score <= aerc_max)

    offset = (page - 1) * per_page
    decks = query.limit(per_page).offset(offset).all()
    return jsonify([serialize_deck_summary(d) for d in decks])


@blueprint.route("/decks/<deck_id>")
def deck_detail(deck_id):
    deck = Deck.query.filter_by(kf_id=deck_id).first()
    if deck is None:
        return jsonify({"error": "Deck not found"}), 404
    data = serialize_deck_detail(deck)
    username = request.args.get("username")
    if username is not None:
        games_won = Game.query.filter(
            Game.winner_deck_dbid == deck.id,
            Game.winner == username,
        ).count()
        games_lost = Game.query.filter(
            Game.loser_deck_dbid == deck.id,
            Game.loser == username,
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
    data["games_won"] = games_won
    data["games_lost"] = games_lost
    data["games"] = [serialize_game_summary(g) for g in deck_games]
    return jsonify(data)


@blueprint.route("/users/<username>")
def user_detail(username):
    games_won = Game.query.filter(Game.winner == username).count()
    games_lost = Game.query.filter(Game.loser == username).count()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    offset = (page - 1) * per_page
    user_games = (
        Game.query.filter((Game.winner == username) | (Game.loser == username))
        .order_by(Game.date.desc())
        .limit(per_page)
        .offset(offset)
        .all()
    )
    if games_won + games_lost == 0:
        return jsonify({"error": "User not found"}), 404
    return jsonify(
        {
            "username": username,
            "games_won": games_won,
            "games_lost": games_lost,
            "games": [serialize_game_summary(g) for g in user_games],
        }
    )


@blueprint.route("/upload/log", methods=["POST"])
@login_required
def upload_log():
    data = request.get_json(silent=True) or {}
    log_text = data.get("log", "")
    date_str = data.get("date")
    if not log_text:
        return jsonify({"error": "Missing 'log' field"}), 400
    if date_str:
        game_start = datetime.datetime.fromisoformat(date_str.rstrip("Z"))
    else:
        game_start = datetime.datetime.now()
    try:
        game = log_to_game(log_text)
    except (BadLog, DeckNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400
    game.date = game_start
    db.session.add(game)
    db.session.commit()
    db.session.refresh(game)
    game.crucible_game_id = f"UNKNOWN-{game.id}"
    db.session.commit()
    for seq, line in enumerate(log_text.split("\n")):
        log_obj = Log(
            game_id=game.id,
            message=line,
            winner_perspective=False,
            time=game_start + datetime.timedelta(seconds=seq),
        )
        db.session.add(log_obj)
    db.session.commit()
    db.session.refresh(game)
    turn_counts_from_logs(game)
    winner = Player.query.filter_by(username=game.winner).first()
    loser = Player.query.filter_by(username=game.loser).first()
    if winner and winner.anonymous:
        anonymize_game_for_player(game, winner)
    if loser and loser.anonymous:
        anonymize_game_for_player(game, loser)
    return jsonify({"success": True, "crucible_game_id": game.crucible_game_id}), 201


@blueprint.route("/upload/simple", methods=["POST"])
@login_required
def upload_simple():
    data = request.get_json(silent=True) or {}
    try:
        game = basic_stats_to_game(**data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    existing = Game.query.filter_by(crucible_game_id=game.crucible_game_id).first()
    if existing is not None:
        return jsonify({"error": f"Game '{game.crucible_game_id}' already exists"}), 409
    db.session.add(game)
    db.session.commit()
    return jsonify({"success": True, "crucible_game_id": game.crucible_game_id}), 201


@blueprint.route("/csv/pods", methods=["POST"])
@login_required
def csv_pods():
    if "decks_csv" not in request.files:
        return jsonify({"error": "Missing 'decks_csv' file"}), 400
    decks_csv = request.files["decks_csv"]
    max_decks = request.form.get("max_decks", 1000, type=int)
    result_type = request.form.get("result_type", "json")
    house_stats = parse_house_stats(decks_csv, max_decks=max_decks)
    if result_type == "csv":
        from flask import send_file

        output_csv = house_stats_to_csv(house_stats)
        output_filename = decks_csv.filename.replace(".csv", "_pod_stats.csv")
        return send_file(
            output_csv,
            download_name=output_filename,
            as_attachment=True,
        )
    pods = [
        {
            "name": pod.name,
            "sas": pod.sas,
            "expansion": pod.expansion,
            "house": pod.house,
            "cards": pod.cards,
            "link": pod.link,
            "on_market": pod.on_market,
            "price": pod.price,
        }
        for pod in house_stats
    ]
    return jsonify(pods)


# --- Admin ---

ADMIN_EMAIL = "andrew.vandever@gmail.com"


@blueprint.route("/admin/users", methods=["GET"])
@login_required
def admin_list_users():
    if current_user.email != ADMIN_EMAIL:
        return jsonify({"error": "Admin access required"}), 403
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)
    q = User.query.order_by(User.id)
    total = q.count()
    users = q.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify(
        {
            "users": [
                {
                    "id": u.id,
                    "name": u.name,
                    "email": u.email,
                    "is_member": u.is_member,
                    "free_membership": u.free_membership,
                    "is_patron": u.is_patron,
                    "is_test_user": u.is_test_user,
                    "is_league_admin": u.is_league_admin,
                }
                for u in users
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    )


@blueprint.route("/admin/users/<int:user_id>", methods=["DELETE"])
@login_required
def admin_delete_user(user_id):
    if current_user.email != ADMIN_EMAIL:
        return jsonify({"error": "Admin access required"}), 403
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user.email == ADMIN_EMAIL:
        return jsonify({"error": "Cannot delete admin user"}), 400
    db.session.delete(user)
    db.session.commit()
    return jsonify({"success": True}), 200


@blueprint.route("/admin/users/<int:user_id>/free-membership", methods=["POST"])
@login_required
def admin_toggle_free_membership(user_id):
    if current_user.email != ADMIN_EMAIL:
        return jsonify({"error": "Admin access required"}), 403
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    user.free_membership = not user.free_membership
    db.session.commit()
    return jsonify({"success": True, "free_membership": user.free_membership}), 200
