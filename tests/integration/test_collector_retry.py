"""What the MV retry loop does when Master Vault serves something else."""
import json
import os
import sys
import tempfile

os.environ["TRACKER_CONFIG_PATH"] = "ENV"
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.pop("ENABLE_COLLECTOR", None)

import requests

from keytracker.server import app
from keytracker import utils
from keytracker.schema import db

FAIL = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + str(detail)) if detail else ''}")
    if not ok:
        FAIL.append(label)


HTML = "<html><head><title>503 Service Unavailable</title></head></html>"


class NotJson:
    """What MV actually served: an HTML error page, with a 200 on it."""

    status_code = 200
    text = HTML

    def json(self):
        raise requests.exceptions.JSONDecodeError("Expecting value", HTML, 0)


class Throttled:
    status_code = 200
    text = '{"code": 429}'

    def json(self):
        return {"code": 429, "message": "slow", "detail": " down"}


class Fine:
    status_code = 200
    text = "{}"

    def json(self):
        return {"data": [], "_linked": {"cards": []}}


class Upstream:
    """Hands out canned responses in order, counting the calls."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        i = min(self.calls - 1, len(self.responses) - 1)
        return self.responses[i]


real_sleep = utils.time.sleep
utils.time.sleep = lambda *a, **k: None

with app.app_context():
    db.drop_all()
    db.create_all()
    dest = tempfile.mkdtemp()

    # --- it absorbs the bad body instead of crashing in the clause ---------
    upstream = Upstream(NotJson())
    utils.mv_api.callMVSync = upstream
    try:
        utils.dump_page_json_to_file(page=1, reverse=False, dest=dest, tries=3)
        raised = None
    except Exception as exc:
        raised = exc
    check("it raises the decode error, not a NameError",
          isinstance(raised, json.decoder.JSONDecodeError), repr(raised))
    check("and not a NameError in particular", not isinstance(raised, NameError))
    check("having fetched again on each try rather than re-reading one body",
          upstream.calls == 3, upstream.calls)

    # --- a blip recovers ---------------------------------------------------
    upstream = Upstream(NotJson(), Fine())
    utils.mv_api.callMVSync = upstream
    try:
        utils.dump_page_json_to_file(page=2, reverse=False, dest=dest, tries=3)
        err = None
    except Exception as exc:
        err = exc
    check("a single bad response is ridden out", err is None, repr(err))
    check("on the second fetch", upstream.calls == 2, upstream.calls)
    written = os.path.join(dest, "2.json")
    check("and the page is written", os.path.exists(written))
    if os.path.exists(written):
        check("with the good payload in it",
              json.load(open(written)) == {"data": [], "_linked": {"cards": []}})

    # --- the throttling path re-fetches too --------------------------------
    upstream = Upstream(Throttled())
    utils.mv_api.callMVSync = upstream
    try:
        utils.dump_page_json_to_file(page=3, reverse=False, dest=dest, tries=4)
        raised = None
    except Exception as exc:
        raised = exc
    check("a 429 ends as RequestThrottled",
          isinstance(raised, utils.RequestThrottled), repr(raised))
    check("after asking again each time", upstream.calls == 4, upstream.calls)

    # --- the collector's own ingest takes the same path --------------------
    upstream = Upstream(NotJson(), Fine())
    utils.mv_api.callMVSync = upstream
    try:
        new_decks = utils.get_decks_from_page_v2(
            page=1,
            reverse=False,
            add_decks_cache={"seen_deck_ids": set()},
            tries=3,
        )
        err = None
    except Exception as exc:
        new_decks, err = None, exc
    check("the deck ingest rides out the same blip", err is None, repr(err))
    check("and reports the empty page", new_decks == 0, new_decks)

utils.time.sleep = real_sleep
print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
