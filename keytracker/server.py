#!/usr/bin/env python3
from flask import current_app, Flask, jsonify, redirect, request
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix
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
    leagues,
)
from keytracker.routes.standalone import standalone_bp

from keytracker.scripts.collector import collector
from keytracker.scripts.sealed import sealed
from keytracker.scripts.test_user import test_user
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
# Trust one proxy hop (Caddy → Gunicorn) so url_for generates correct
# scheme/host and request.remote_addr reflects the real client IP.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
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
db.app = app
db.init_app(app)

from flask_mail import Mail  # noqa: E402

mail = Mail(app)

login_manager = LoginManager()
login_manager.session_protection = "basic"
login_manager.init_app(app)

from keytracker.schema import User


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except (OperationalError, PendingRollbackError):
        db.session.rollback()
        return User.query.get(int(user_id))


auth.init_oauth(app)

# Add google_id and avatar_url columns if they don't exist (migration)
with app.app_context():
    db.create_all()
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
                if "is_league_admin" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN is_league_admin BOOLEAN NOT NULL DEFAULT FALSE"
                        )
                    )
                if "is_test_user" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN is_test_user BOOLEAN NOT NULL DEFAULT FALSE"
                        )
                    )
                if "password_hash" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN password_hash VARCHAR(256)"
                        )
                    )
                if "email_verified" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE"
                        )
                    )
                if "email_verification_token" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN email_verification_token VARCHAR(100) UNIQUE"
                        )
                    )
                if "verification_token_expires_at" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN verification_token_expires_at DATETIME"
                        )
                    )
                if "password_reset_token" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN password_reset_token VARCHAR(100) UNIQUE"
                        )
                    )
                if "password_reset_token_expires_at" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_user ADD COLUMN password_reset_token_expires_at DATETIME"
                        )
                    )
        if inspector.has_table("tracker_league"):
            columns = {c["name"] for c in inspector.get_columns("tracker_league")}
            with db.engine.begin() as conn:
                if "is_test" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE tracker_league ADD COLUMN is_test BOOLEAN NOT NULL DEFAULT FALSE"
                        )
                    )
    except Exception:
        pass


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith("/api/"):
        return jsonify({"error": "Authentication required"}), 401
    from flask import send_from_directory

    return send_from_directory(FRONTEND_DIST, "index.html")


@app.after_request
def prevent_caching_for_user_responses(response):
    """Prevent CDN/proxy caching of any user-specific response.

    Without this, CDNs can cache authenticated API responses or auth
    redirects (which carry Set-Cookie headers) and serve them to other
    users — leaking session cookies across clients.

    Covers:
    - /api/* — authenticated API endpoints
    - /auth/* — OAuth callbacks that set session cookies
    - Any response that sets a cookie — belt-and-suspenders
    """
    if (
        request.path.startswith("/api/")
        or request.path.startswith("/auth/")
        or "Set-Cookie" in response.headers
    ):
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Vary"] = "Cookie"
    return response


app.register_blueprint(auth.blueprint)
app.register_blueprint(api.blueprint)
app.register_blueprint(api_v2.blueprint)
app.register_blueprint(leagues.blueprint)
app.register_blueprint(standalone_bp)

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


app.cli.add_command(collector)
app.cli.add_command(sealed)
app.cli.add_command(test_user)


def _ensure_nobody_user():
    """Create the nobody@example.com guest user if it doesn't exist."""
    from keytracker.schema import User

    try:
        if not User.query.filter_by(email="nobody@example.com").first():
            guest = User(email="nobody@example.com", name="Guest Player")
            db.session.add(guest)
            db.session.commit()
    except Exception:
        db.session.rollback()


with app.app_context():
    _ensure_nobody_user()


@app.cli.command("cleanup-standalone-matches")
def cleanup_standalone_matches():
    """Delete unfinished standalone matches older than 24 hours."""
    import datetime as dt
    from keytracker.schema import StandaloneMatch, StandaloneMatchStatus

    cutoff = dt.datetime.utcnow() - dt.timedelta(hours=24)
    deleted = StandaloneMatch.query.filter(
        StandaloneMatch.status != StandaloneMatchStatus.COMPLETED,
        StandaloneMatch.created_at < cutoff,
    ).delete(synchronize_session=False)
    db.session.commit()
    print(f"Deleted {deleted} stale standalone matches.")


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


if os.getenv("ENABLE_CARD_REFRESHER", "").lower() in ("1", "true", "yes"):
    import threading

    card_refresher_thread = threading.Thread(
        target=utils.run_background_card_refresher,
        args=(app,),
        daemon=True,
    )
    card_refresher_thread.start()
    logging.getLogger("card_refresher").info(
        "Background card refresher thread launched"
    )


if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
