import logging
import queue
import threading

from flask import Flask

logger = logging.getLogger(__name__)
_queue: queue.Queue = queue.Queue()


def enqueue(
    app: Flask,
    game_id: int,
    winner_deck_id: str | None,
    loser_deck_id: str | None,
):
    _queue.put((app, game_id, winner_deck_id, loser_deck_id))


def _worker():
    while True:
        app, game_id, winner_deck_id, loser_deck_id = _queue.get()
        try:
            with app.app_context():
                _enrich(game_id, winner_deck_id, loser_deck_id)
        except Exception:
            logger.exception("Deck enrichment failed for game %s", game_id)
        finally:
            _queue.task_done()


def _enrich(game_id, winner_deck_id, loser_deck_id):
    from keytracker.schema import db, Game
    from keytracker.utils import get_deck_by_id_with_zeal

    game = Game.query.get(game_id)
    if not game:
        return
    for deck_id, side in [(winner_deck_id, "winner"), (loser_deck_id, "loser")]:
        if not deck_id:
            continue
        try:
            deck = get_deck_by_id_with_zeal(deck_id)
            if side == "winner":
                game.winner_deck = deck
                game.winner_deck_id = deck.kf_id
                game.winner_deck_name = deck.name
                game.winner_deck_dbid = deck.id
            else:
                game.loser_deck = deck
                game.loser_deck_id = deck.kf_id
                game.loser_deck_name = deck.name
                game.loser_deck_dbid = deck.id
        except Exception:
            logger.exception(
                "Could not enrich %s deck %s for game %s", side, deck_id, game_id
            )
    db.session.commit()


def start_worker():
    t = threading.Thread(target=_worker, daemon=True, name="deck-enrichment-worker")
    t.start()
