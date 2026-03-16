"""
Minimal Flask test app — registers only the blueprints under test and uses an
in-memory SQLite DB so tests run without a real database connection.
"""

import pytest
from flask import Flask

from keytracker.schema import db
from keytracker.routes.mv_proxy import mv_proxy_bp


@pytest.fixture(scope="session")
def app():
    test_app = Flask(__name__)
    test_app.config["TESTING"] = True
    test_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    test_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    test_app.config["SECRET_KEY"] = "test-secret-key"

    db.init_app(test_app)
    test_app.register_blueprint(mv_proxy_bp, url_prefix="/api/master-vault")

    return test_app


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()
