import logging
import queue
import threading
import datetime

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
            logger.exception("Collection sync failed for user %s job %s", user_id, job_id)
        finally:
            _queue.task_done()


def _run_sync(user_id: int, job_id: int):
    from keytracker.schema import db, CollectionSyncJob, User
    from keytracker.utils import sync_collection_from_dok

    job = CollectionSyncJob.query.get(job_id)
    if not job:
        return
    job.status = "running"
    job.started_at = datetime.datetime.utcnow()
    db.session.commit()

    try:
        user = User.query.get(user_id)
        result = sync_collection_from_dok(user)
        job.status = "done"
        job.standard_decks = result["standard_decks"]
        job.alliance_decks = result["alliance_decks"]
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
