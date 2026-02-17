#!/usr/bin/env python3
import click
from flask import current_app
from flask.cli import AppGroup
from keytracker.schema import db, User
import click_log

test_user = AppGroup('test-user')
click_log.basic_config()


class EmailExists(Exception):
    pass

@test_user.command("create")
@click_log.simple_verbosity_option()
@click.argument("name", type=str)
@click.argument("email", type=str)
def create(name, email):
    with current_app.app_context():
        existing = User.query.filter_by(email=email).first()
        if existing:
            raise EmailExists(f"User with email {email} already exists")
        user = User(name=name, email=email, is_test_user=True)
        db.session.add(user)
        db.session.commit()
