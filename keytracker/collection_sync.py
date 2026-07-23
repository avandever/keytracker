import logging
import queue
import threading
import datetime
import time

from flask import Flask

logger = logging.getLogger(__name__)
_queue: queue.Queue = queue.Queue()


def enqueue(app: Flask, user_id: int, job_id: int):
    _queue.put((app, user_id, job_id))


def _worker():
    while True:
        app, user_id, job_id = _queue.get()
        try:
            with app.app_context():
                _run_sync(user_id, job_id)
        except Exception:
            logger.exception(
                "Collection sync failed for user %s job %s", user_id, job_id
            )
        finally:
            _queue.task_done()


def _run_sync(user_id: int, job_id: int):
    from flask import current_app
    from keytracker.schema import db, CollectionSyncJob, User
    from keytracker.utils import sync_collection_from_dok
    import keytracker.deck_refresh as deck_refresh

    job = CollectionSyncJob.query.get(job_id)
    if not job:
        return
    job.status = "running"
    job.started_at = datetime.datetime.utcnow()
    db.session.commit()

    try:
        user = User.query.get(user_id)
        t0 = time.monotonic()
        result = sync_collection_from_dok(user)
        elapsed = time.monotonic() - t0
        timing = result.get("timing", {})
        logger.info(
            "Collection sync completed for user %s in %.1fs: "
            "%d standard decks, %d alliance decks, %d need refresh. "
            "Timing breakdown — DoK API: %.1fs, DB/processing: %.1fs, "
            "standard pages: %d (DoK: %.1fs, DB: %.1fs), "
            "alliance (DoK: %.1fs, DB: %.1fs)",
            user_id,
            elapsed,
            result["standard_decks"],
            result["alliance_decks"],
            len(result.get("refresh_deck_ids", [])),
            timing.get("dok_api_total", 0),
            timing.get("db_total", 0),
            timing.get("standard_pages", 0),
            timing.get("standard_dok", 0),
            timing.get("standard_db", 0),
            timing.get("alliance_dok", 0),
            timing.get("alliance_db", 0),
        )
        job.status = "done"
        job.standard_decks = result["standard_decks"]
        job.alliance_decks = result["alliance_decks"]
        app = current_app._get_current_object()
        for deck_id in result.get("refresh_deck_ids", []):
            deck_refresh.enqueue(app, deck_id, user.dok_api_key)
        logger.info(
            "Enqueued %d decks for refresh (user %s)",
            len(result.get("refresh_deck_ids", [])),
            user_id,
        )
    except Exception as e:
        logger.exception("Collection sync error for user %s", user_id)
        job.status = "failed"
        job.error = str(e)
    finally:
        job.completed_at = datetime.datetime.utcnow()
        db.session.commit()


def start_worker():
    t = threading.Thread(target=_worker, daemon=True, name="collection-sync-worker")
    t.start()
