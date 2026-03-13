import logging
import queue
import threading

from flask import Flask

logger = logging.getLogger(__name__)
_queue: queue.Queue = queue.Queue()


def enqueue(app: Flask, deck_id: int, user_dok_api_key: str | None = None):
    _queue.put((app, deck_id, user_dok_api_key))


def _worker():
    while True:
        app, deck_id, user_dok_api_key = _queue.get()
        try:
            with app.app_context():
                _refresh(deck_id, user_dok_api_key)
        except Exception:
            logger.exception("Deck refresh failed for deck %s", deck_id)
        finally:
            _queue.task_done()


def _refresh(deck_id: int, user_dok_api_key: str | None):
    from keytracker.schema import db, Deck
    from keytracker.utils import calculate_pod_stats, refresh_deck_from_mv, update_sas_scores

    deck = Deck.query.get(deck_id)
    if not deck:
        return

    if len(deck.cards_from_assoc) < 36:
        try:
            refresh_deck_from_mv(deck)
            db.session.flush()
        except Exception:
            logger.exception("MV refresh failed for deck %s (%s)", deck_id, deck.kf_id)

    if len(deck.pod_stats) == 0 and len(deck.cards_from_assoc) >= 36:
        try:
            calculate_pod_stats(deck)
        except Exception:
            logger.exception("Pod stats failed for deck %s", deck_id)

    if not deck.dok or deck.dok.last_refresh is None:
        try:
            update_sas_scores(deck, dok_api_key=user_dok_api_key)
        except Exception:
            logger.exception("SAS update failed for deck %s", deck_id)

    db.session.commit()


def start_worker():
    t = threading.Thread(target=_worker, daemon=True, name="deck-refresh-worker")
    t.start()
