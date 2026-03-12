#!/usr/bin/env python3
import click
from flask import current_app
from keytracker.schema import db, Player
from keytracker.utils import anonymize_all_games_for_player, CantAnonymize


@click.command("anonymize-player")
@click.argument("username")
def anonymize_player(username):
    """Anonymize all games for a Crucible username and add it to the exclusion list.

    Sets Player.anonymous=True (blocks future uploads from using this name) and
    replaces the username with 'anonymous' in all existing game records, logs,
    and house-turn counts.

    Example:
        flask anonymize-player SomePlayer
    """
    with current_app.app_context():
        player = Player.query.filter_by(username=username).first()
        if player is None:
            raise click.ClickException(f"No Player record found for username '{username}'.")

        if player.username == "anonymous":
            raise click.ClickException("Cannot anonymize the 'anonymous' placeholder player.")

        if player.anonymous:
            click.echo(
                f"'{username}' is already marked anonymous. "
                "Running anonymization pass anyway in case any games were missed."
            )
        else:
            player.anonymous = True
            db.session.commit()
            click.echo(f"Marked '{username}' as anonymous (future uploads will be redirected).")

        try:
            anonymize_all_games_for_player(player)
            click.echo(f"Done. All games for '{username}' have been anonymized.")
        except CantAnonymize as e:
            raise click.ClickException(str(e))
