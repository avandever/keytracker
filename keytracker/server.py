#!/usr/bin/env python3
from flask import Flask, jsonify
from keytracker.schema import (
    db,
    Log,
)
from keytracker.utils import (
    load_config,
)
from keytracker.renderers import (
    render_dropdown,
    render_input_number,
    render_log,
    render_game_listing,
)
from keytracker.routes import (
    ui,
    api,
)
from sqlalchemy.exc import (
    OperationalError,
    PendingRollbackError,
)
import os


app = Flask(__name__)
app.config.update(load_config())
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_size": 10,
    "pool_recycle": int(os.getenv("SQLALCHEMY_POOL_RECYCLE", 300)),
    "pool_pre_ping": True,
}
app.app_context().push()
db.app = app
db.init_app(app)
db.create_all()
app.jinja_env.globals.update(
    render_dropdown=render_dropdown,
    render_game_listing=render_game_listing,
    render_input_number=render_input_number,
    render_log=render_log,
)
app.register_blueprint(ui.blueprint)
app.register_blueprint(api.blueprint)


@app.errorhandler(OperationalError)
    db.session.rollback()
    return jsonify({"status_code": 500, "status": "Internal Server Error"})


@app.errorhandler(PendingRollbackError)
def handle_pending_rollback(error):
    db.session.rollback()
    return jsonify({"status_code": 500, "status": "Internal Server Error"})


if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
