# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KeyForge Tracker ("Bear Tracks") is a Flask web application for tracking and analyzing KeyForge card game matches. It records games from Crucible game logs, fetches deck data from the Master Vault API, integrates SAS/AERC ratings from Decks of Keyforge, and provides search/statistics features.

## Commands

### Run Development Server
```bash
flask --app keytracker.server run
```

### Run with Gunicorn (production-like)
```bash
gunicorn -w 4 "keytracker.server:app"
```

### Install
```bash
python3 -m venv venv && source venv/bin/activate
pip install . gunicorn
```

### Lint & Format
```bash
bash lint.sh
```
This runs Black on Python files, css-beautify on CSS, and djlint reformat+lint on Jinja2 templates.

### Docker

Build (the `VITE_RECAPTCHA_SITE_KEY` build arg is required for the frontend):
```bash
docker build -t keytracker --build-arg VITE_RECAPTCHA_SITE_KEY=6LfZAXksAAAAAOycX9ZMlksKsKKyyMTAXZnZxJo9 .
```

Run (env vars are stored in `.env`; `--add-host` is required on Linux for `host.docker.internal` to resolve to the host):
```bash
docker stop keytracker && docker rm keytracker
docker run -d --name keytracker \
  --env-file .env \
  --add-host=host.docker.internal:host-gateway \
  -p 3001:3001 -p 3443:3443 \
  keytracker
```

### Alliance Restricted List Population

To add cards to the Alliance Restricted List (run from project root):
```bash
python keytracker/scripts/add_alliance_restricted_card.py --version 2.5 --card-name "Reiteration"
python keytracker/scripts/add_alliance_restricted_card.py --version 2.5 --card-name "Key Abduction" --max-copies 1
```
Reads `DATABASE_URL` from `.env`. Creates the version automatically if it doesn't exist.
See `keytracker/scripts/ALLIANCE_RESTRICTED_LIST.md` for full documentation.

### No test suite exists in this project.

## Architecture

**Entry point**: `keytracker/server.py` — initializes the Flask app, configures SQLAlchemy with MySQL connection pooling, sets up Flask-Login, and registers blueprints and CLI commands.

**Database models**: `keytracker/schema.py` — 25+ SQLAlchemy models. Core entities are `Game`, `Deck`, `Player`, and `Log`. Card data uses `PlatonicCard`/`PlatonicCardInSet`/`CardInDeck` (the old `Card` model is deprecated). `DokDeck` holds SAS/AERC scores from Decks of Keyforge. `log_to_game()` in this file parses Crucible game logs into Game objects using regex matchers.

**Business logic**: `keytracker/utils.py` — Master Vault API client (rate-limited to 1 req/sec), DoK API integration, game creation from logs and manual stats, deck fetching/caching, pod stats calculation, CSV import/export, and MySQL retry decorators.

**Routes**:
- `keytracker/routes/ui.py` — Jinja2 Web UI: game/deck/player browsing, search with filtering, CSV tools, auth pages
- `keytracker/routes/api.py` — REST API v1: game upload (full data or log file), deck enhancement queries
- `keytracker/routes/api_v2.py` — REST API v2 (JSON): read endpoints for games/decks/users, upload endpoints. Powers the MUI frontend.

**Serializers**: `keytracker/serializers.py` — converts SQLAlchemy models to dicts for JSON API responses.

**Rendering**: `keytracker/renderers.py` — formats game log messages into styled HTML with card hover images via regex matching (used by Jinja2 UI).

**Data collection**: `keytracker/scripts/collector.py` — async CLI tool (registered as Flask command) that bulk-fetches deck data from Master Vault API with rate limiting and caching.

**Templates**: `keytracker/templates/` — 20 Jinja2 templates, base layout in `layout.html`.

**Material UI Frontend**: `frontend/` — React + TypeScript + Material UI SPA served at `/mui/`. Uses Vite for builds. API client in `frontend/src/api/`, pages in `frontend/src/pages/`. Dev server proxies `/api` to Flask.

### Frontend Development
```bash
cd frontend && npm install && npm run dev   # Dev server on port 5173
cd frontend && npm run build                # Build to frontend/dist/
```
The Flask app serves the built frontend at `/mui/`. During development, run both the Vite dev server and Flask.

## Configuration

The app reads from `config.ini` (see `config_example.ini`). Key env vars:
- `TRACKER_CONFIG_PATH` — path to config.ini (set to `ENV` to use env vars directly)
- `DATABASE_URL` — direct database URI (when TRACKER_CONFIG_PATH=ENV)
- `SECRET_KEY` — Flask secret key
- `DOK_API_KEY` — Decks of Keyforge API key

## External API Dependencies

- **Master Vault API** — deck data (rate-limited, 1 call/sec in `utils.py`)
- **Decks of Keyforge API** — SAS/AERC scores (requires `DOK_API_KEY`)

## Database

Supports MySQL (production) and SQLite (development) via configurable driver in config.ini. Connection pool: size 20, timeout 5s, READ COMMITTED isolation, pre-ping enabled.

## Frontend/Backend Sync

The TypeScript frontend manually mirrors certain Python enums from `keytracker/schema.py`. When modifying these enums, update both sides:

- `WeekStatus` (`schema.py`) ↔ `WeekStatus` type in `frontend/src/types.ts`
