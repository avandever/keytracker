import logging
import queue
import threading
import time

from flask import Flask, current_app

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
    from keytracker.utils import (
        calculate_pod_stats,
        refresh_deck_from_mv,
        update_sas_scores,
    )

    log = current_app.logger
    deck = Deck.query.get(deck_id)
    if not deck:
        return

    t0 = time.monotonic()

    if len(deck.cards_from_assoc) < 36:
        try:
            t_mv = time.monotonic()
            refresh_deck_from_mv(deck)
            db.session.flush()
            log.info(
                "Deck %s (%s): MV refresh %.1fs",
                deck_id, deck.kf_id, time.monotonic() - t_mv,
            )
        except Exception:
            log.exception("MV refresh failed for deck %s (%s)", deck_id, deck.kf_id)

    if len(deck.pod_stats) == 0 and len(deck.cards_from_assoc) >= 36:
        try:
            t_pod = time.monotonic()
            calculate_pod_stats(deck)
            db.session.commit()
            log.info(
                "Deck %s: pod stats %.1fs",
                deck_id, time.monotonic() - t_pod,
            )
        except Exception:
            log.exception("Pod stats failed for deck %s", deck_id)

    if not deck.dok or deck.dok.last_refresh is None:
        try:
            t_sas = time.monotonic()
            update_sas_scores(deck, dok_api_key=user_dok_api_key)
            db.session.commit()
            log.info(
                "Deck %s: SAS update %.1fs",
                deck_id, time.monotonic() - t_sas,
            )
        except Exception:
            log.exception("SAS update failed for deck %s", deck_id)

    log.info(
        "Deck %s refresh total: %.1fs", deck_id, time.monotonic() - t0,
    )


def start_worker():
    t = threading.Thread(target=_worker, daemon=True, name="deck-refresh-worker")
    t.start()
