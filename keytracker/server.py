#!/usr/bin/env python3
from flask import Flask
import configparser
from keytracker.schema import (
    db,
    Log,
)
from keytracker.utils import (
    config_to_uri,
    render_log,
)
from keytracker.routes import (
    ui,
    api,
)


app = Flask(__name__)
cparser = configparser.ConfigParser()
cparser.read("config.ini")
app.config["SQLALCHEMY_DATABASE_URI"] = config_to_uri(**cparser["db"])
app.config["SECRET_KEY"] = cparser["app"]["secret_key"]
assert app.config["SECRET_KEY"] != "placeholder"
app.app_context().push()
db.app = app
db.init_app(app)
db.create_all()
app.jinja_env.globals.update(render_log=render_log)
app.register_blueprint(ui.blueprint)
app.register_blueprint(api.blueprint)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
