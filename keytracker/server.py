#!/usr/bin/env python3
from flask import current_app, Flask, jsonify
from keytracker.schema import (
    db,
    Log,
)
from keytracker import utils
from keytracker import schema
from keytracker.renderers import (
    render_card_images,
    render_dropdown,
    render_input_number,
    render_log,
    render_game_listing,
)
from keytracker.routes import (
    ui,
    api,
)
from keytracker.scripts.collector import collector
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
app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000  # 16 MB
app.app_context().push()
db.app = app
db.init_app(app)
db.create_all()
app.jinja_env.globals.update(
    render_card_images=render_card_images,
    render_dropdown=render_dropdown,
    render_game_listing=render_game_listing,
    render_input_number=render_input_number,
    render_log=render_log,
)
app.register_blueprint(ui.blueprint)
app.register_blueprint(api.blueprint)

app.cli.add_command(collector)


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
        "CardType": schema.CardType,
        "Deck": schema.Deck,
        "DokDeck": schema.DokDeck,
        "EnhancedCard": schema.EnhancedCard,
        "Enhancements": schema.Enhancements,
        "Expansion": schema.Expansion,
        "Game": schema.Game,
        "House": schema.House,
        "HouseTurnCounts": schema.HouseTurnCounts,
        "logging": logging,
        "Log": schema.Log,
        "PlatonicCard": schema.PlatonicCard,
        "PlatonicCardInSet": schema.PlatonicCardInSet,
        "Player": schema.Player,
        "PodStats": schema.PodStats,
        "Rarity": schema.Rarity,
        "time": time,
        "Trait": schema.Trait,
        "TurnState": schema.TurnState,
    }


if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
