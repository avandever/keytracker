#!/usr/bin/env python3
import click
from flask import current_app
from flask.cli import AppGroup
from keytracker.schema import db, User, League, LeagueSignup
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
        user = User(
            name=name,
            email=email,
            is_test_user=True,
            dok_profile_url="https://decksofkeyforge.com/users/xoque",
            country="US",
            timezone="PST (UTC-8)",
        )
        db.session.add(user)
        db.session.commit()


@test_user.command("signup-all")
@click_log.simple_verbosity_option()
@click.argument("league_id", type=int)
def signup_all(league_id):
    """Sign up all test users for a test league."""
    with current_app.app_context():
        league = League.query.get(league_id)
        if not league:
            raise click.ClickException(f"League {league_id} not found")
        if not league.is_test:
            raise click.ClickException(f"League {league_id} is not a test league")
        test_users = User.query.filter_by(is_test_user=True).order_by(User.id).all()
        if not test_users:
            raise click.ClickException("No test users found")
        existing_user_ids = {
            s.user_id
            for s in LeagueSignup.query.filter_by(league_id=league_id).all()
        }
        next_order = (
            db.session.query(db.func.coalesce(db.func.max(LeagueSignup.signup_order), 0))
            .filter_by(league_id=league_id)
            .scalar()
        ) + 1
        added = 0
        for user in test_users:
            if user.id in existing_user_ids:
                click.echo(f"Skipping {user.name} (already signed up)")
                continue
            signup = LeagueSignup(
                league_id=league_id,
                user_id=user.id,
                signup_order=next_order,
            )
            db.session.add(signup)
            next_order += 1
            added += 1
        db.session.commit()
        click.echo(f"Added {added} test users to league {league.name}")
