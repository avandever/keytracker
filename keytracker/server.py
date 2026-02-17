#!/usr/bin/env python3
from flask import current_app, Flask, jsonify, redirect, request
from flask_login import LoginManager
from keytracker.schema import (
    db,
    Log,
)
from keytracker import utils
from keytracker import schema
from keytracker.routes import (
    api,
    api_v2,
    auth,
)
# from keytracker.scripts.collector import collector
from keytracker.scripts.sealed import sealed
import sqlalchemy
from sqlalchemy.exc import (
    OperationalError,
    PendingRollbackError,
)
import os
import logging
import time


app = Flask(__name__)
app.config.update(utils.load_config())
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "isolation_level": "READ COMMITTED",
    "pool_size": 20,
    "pool_recycle": int(os.getenv("SQLALCHEMY_POOL_RECYCLE", 10)),
    "pool_pre_ping": True,
    "pool_timeout": 5,
    "pool_reset_on_return": "commit",
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1000 * 1000  # 16 MB
app.app_context().push()
db.app = app
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

from keytracker.schema import User


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


auth.init_oauth(app)

db.create_all()

# Add google_id and avatar_url columns if they don't exist (migration)
with app.app_context():
    try:
        from sqlalchemy import inspect as sa_inspect, text

        inspector = sa_inspect(db.engine)
        if inspector.has_table("tracker_user"):
            columns = {c["name"] for c in inspector.get_columns("tracker_user")}
            with db.engine.begin() as conn:
                if "google_id" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN google_id VARCHAR(200) UNIQUE"
                        )
                    )
                if "avatar_url" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN avatar_url VARCHAR(500)"
                        )
                    )
                if "patreon_id" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN patreon_id VARCHAR(200) UNIQUE"
                        )
                    )
                if "patreon_access_token" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN patreon_access_token VARCHAR(500)"
                        )
                    )
                if "patreon_refresh_token" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN patreon_refresh_token VARCHAR(500)"
                        )
                    )
                if "is_patron" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN is_patron BOOLEAN NOT NULL DEFAULT FALSE"
                        )
                    )
                if "patreon_tier_title" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN patreon_tier_title VARCHAR(200)"
                        )
                    )
                if "patreon_pledge_cents" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN patreon_pledge_cents INTEGER"
                        )
                    )
                if "patreon_linked_at" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN patreon_linked_at DATETIME"
                        )
                    )
                if "free_membership" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN free_membership BOOLEAN NOT NULL DEFAULT FALSE"
                        )
                    )
                if "dok_api_key" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN dok_api_key VARCHAR(36)"
                        )
                    )
    except Exception:
        pass


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith("/api/"):
        return jsonify({"error": "Authentication required"}), 401
    return redirect("/auth/google/login?next=" + request.path)


app.register_blueprint(auth.blueprint)
app.register_blueprint(api.blueprint)
app.register_blueprint(api_v2.blueprint)

# Serve React frontend at /
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


@app.route("/mui/")
@app.route("/mui/<path:path>")
def serve_react_legacy(path=""):
    return redirect("/" + path, code=301)


@app.route("/")
@app.route("/<path:path>")
def serve_react(path=""):
    from flask import send_from_directory

    full_path = os.path.join(FRONTEND_DIST, path)
    if path and os.path.isfile(full_path):
        return send_from_directory(FRONTEND_DIST, path)
    return send_from_directory(FRONTEND_DIST, "index.html")

# app.cli.add_command(collector)
app.cli.add_command(sealed)


@app.errorhandler(OperationalError)
def handle_mysql_disconnect(error):
    db.session.rollback()
    return jsonify({"status_code": 500, "status": "Internal Server Error"})


@app.errorhandler(PendingRollbackError)
def handle_pending_rollback(error):
    db.session.rollback()
    return jsonify({"status_code": 500, "status": "Internal Server Error"})


@app.shell_context_processor
def shell_context():
    return {
        "or_": sqlalchemy.or_,
        "and_": sqlalchemy.and_,
        "not_": sqlalchemy.not_,
        "func": sqlalchemy.func,
        "current_app": current_app,
        "db": schema.db,
        "utils": utils,
        "Card": schema.Card,
        "CardInDeck": schema.CardInDeck,
        "Deck": schema.Deck,
        "DokDeck": schema.DokDeck,
        "EnhancedCard": schema.EnhancedCard,
        "Enhancements": schema.Enhancements,
        "Game": schema.Game,
        "HouseTurnCounts": schema.HouseTurnCounts,
        "logging": logging,
        "Log": schema.Log,
        "PlatonicCard": schema.PlatonicCard,
        "PlatonicCardInSet": schema.PlatonicCardInSet,
        "Player": schema.Player,
        "PodStats": schema.PodStats,
        "time": time,
        "Trait": schema.Trait,
        "TurnState": schema.TurnState,
    }


if os.getenv("ENABLE_COLLECTOR", "").lower() in ("1", "true", "yes"):
    import threading

    collector_thread = threading.Thread(
        target=utils.run_background_collector,
        args=(app,),
        daemon=True,
    )
    collector_thread.start()
    logging.getLogger("collector").info("Background collector thread launched")


if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
