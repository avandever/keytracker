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
```bash
docker build -t keytracker .
docker run -p 3001:3001 keytracker
```

### No test suite exists in this project.

## Architecture

**Entry point**: `keytracker/server.py` — initializes the Flask app, configures SQLAlchemy with MySQL connection pooling, sets up Flask-Login, and registers blueprints and CLI commands.

**Database models**: `keytracker/schema.py` — 25+ SQLAlchemy models. Core entities are `Game`, `Deck`, `Player`, and `Log`. Card data uses `PlatonicCard`/`PlatonicCardInSet`/`CardInDeck` (the old `Card` model is deprecated). `DokDeck` holds SAS/AERC scores from Decks of Keyforge. `log_to_game()` in this file parses Crucible game logs into Game objects using regex matchers.

**Business logic**: `keytracker/utils.py` — Master Vault API client (rate-limited to 1 req/sec), DoK API integration, game creation from logs and manual stats, deck fetching/caching, pod stats calculation, CSV import/export, and MySQL retry decorators.

**Routes**:
- `keytracker/routes/ui.py` — Web UI: game/deck/player browsing, search with filtering, CSV tools, auth pages
- `keytracker/routes/api.py` — REST API: game upload (full data or log file), deck enhancement queries, search endpoint

**Rendering**: `keytracker/renderers.py` — formats game log messages into styled HTML with card hover images via regex matching.

**Data collection**: `keytracker/scripts/collector.py` — async CLI tool (registered as Flask command) that bulk-fetches deck data from Master Vault API with rate limiting and caching.

**Templates**: `keytracker/templates/` — 20 Jinja2 templates, base layout in `layout.html`.

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
