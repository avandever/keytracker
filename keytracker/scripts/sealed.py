#!/usr/bin/env python3
import click
import csv
from flask import current_app
from flask.cli import AppGroup
from keytracker.schema import (
    db,
    Deck,
    EXPANSION_VALUES,
)
import keytracker.schema
import click_log
from sqlalchemy.sql.expression import func


sealed = AppGroup("sealed")
click_log.basic_config()


@sealed.command("gen-csv")
@click_log.simple_verbosity_option()
@click.argument("num_decks", type=int)
@click.argument("out_file", type=click.File("w"))
@click.option(
    "sets",
    "--set",
    default=[],
    multiple=True,
    type=click.Choice([exp.shortname for exp in EXPANSION_VALUES]),
)
def gen_csv(num_decks, out_file, sets):
    with current_app.app_context():
        query = Deck.query
        if sets:
            query = query.filter(
                Deck.expansion.in_(
                    [exp.number for exp in EXPANSION_VALUES if exp.shortname in sets]
                )
            )
        query = query.order_by(func.rand()).limit(num_decks)
        print(query)
        results = query.with_entities(Deck.kf_id).all()
        writer = csv.writer(out_file)
        dok_links = [f"https://decksofkeyforge.com/decks/{d.kf_id}" for d in results]
        for res in results:
            writer.writerows([[link] for link in dok_links])


if __name__ == "__main__":
    sealed()
