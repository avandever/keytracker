"""Keep pytest out of this directory.

These are not pytest tests. Each file is a standalone script that builds a
league from nothing in a scratch MySQL database and drives the real API
through a Flask test client, so the module body runs on import and expects
DATABASE_URL to be pointed somewhere disposable. Collected by pytest they
would execute at collection time against whatever database happened to be
configured, which is the one thing they must never do.

Run them with ./run.sh instead; see README.md.
"""

collect_ignore_glob = ["*.py"]
