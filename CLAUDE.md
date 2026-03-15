# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KeyForge Tracker ("Bear Tracks") is a Flask web application for tracking and analyzing KeyForge card game matches. It records games from Crucible game logs, fetches deck data from the Master Vault API, integrates SAS/AERC ratings from Decks of Keyforge, and provides league management, team play, and game analytics.

## Related Projects

- `~/tracker-proxy` — Caddy reverse proxy (deployed to DigitalOcean App Platform, see its CLAUDE.md)
- `~/keytracker-extension` — Chrome MV3 extension that captures games from thecrucible.online and submits them here

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

Build (the `VITE_RECAPTCHA_SITE_KEY` build arg is required — frontend will not build without it):
```bash
docker build -t keytracker --build-arg VITE_RECAPTCHA_SITE_KEY=6LfZAXksAAAAAOycX9ZMlksKsKKyyMTAXZnZxJo9 .
```

Run (env vars are stored in `.env`; `--add-host` is required on Linux for `host.docker.internal` to resolve to the host):
```bash
docker stop keytracker && docker rm keytracker
docker run -d --name keytracker \
  --restart always \
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

### Entry Point: `keytracker/server.py`
Initializes Flask app, configures SQLAlchemy (MySQL connection pooling: size 20, timeout 5s, READ COMMITTED isolation, pre-ping), sets up Flask-Login, and registers blueprints:
- `auth_bp` — OAuth and email auth
- `api_bp` (v1) — legacy game upload
- `api_v2_bp` — JSON API powering the React frontend
- `leagues_bp` — league/team/draft management
- `standalone_bp` — one-off 1v1 matches

Also starts background threads (if enabled via env vars) and creates the guest user `nobody@example.com` for standalone matches.

### Database Models: `keytracker/schema.py`
25+ SQLAlchemy models. Key ones:
- **Core**: `Game`, `Deck`, `Player`, `Log`, `DokDeck` (SAS/AERC scores)
- **Cards**: `PlatonicCard`/`PlatonicCardInSet`/`CardInDeck` (the old `Card` model is deprecated)
- **Leagues**: `League`, `LeagueSignup`, `Team`, `TeamMember`, `LeagueAdmin`, `LeagueWeek`, `LeagueAdminLog`
- **Matchups**: `PlayerMatchup`, `PlayerDeckSelection`, `AlliancePodSelection`
- **Sealed**: `SealedPoolDeck`, `AllianceDeck`
- **Standalone**: `StandaloneMatch`
- **Collection**: `UserDeckCollection`, `UserAllianceCollection`
- **Extended game data**: `ExtendedGameData` (turn_snapshots, key_events JSON cols)
- **SAS Ladder**: `SasLadderAssignment`

Key enums (in `schema.py`):
- `LeagueStatus`: setup → drafting → active → playoffs → completed
- `WeekStatus`: setup → curation → thief → deck_selection → team_paired → pairing → published → completed
- `WeekFormat`: archon, triad, sealed, alliance, team_archon, team_triad, team_sealed, team_sealed_alliance, sas_ladder
- `SignupStatus`: signed_up, drafted, waitlisted

`log_to_game()` in this file parses Crucible game logs into Game objects using regex matchers.

### Business Logic: `keytracker/utils.py`
Master Vault API client (rate-limited to 1 req/sec), DoK API integration, game creation from logs and manual stats, deck fetching/caching, pod stats calculation, CSV import/export, and MySQL retry decorators.

### Routes

| File | Blueprint prefix | Purpose |
|------|-----------------|---------|
| `routes/auth.py` | `/auth` | OAuth (Google/Patreon/Discord), email auth, session |
| `routes/api.py` | `/api` | v1: game upload, deck export |
| `routes/api_v2.py` | `/api/v2` | v2 JSON API powering React frontend |
| `routes/leagues.py` | `/api/v2/leagues` | Full league CRUD, teams, draft, weeks, pairings, sealed pools |
| `routes/standalone.py` | `/api/v2/standalone` | One-off 1v1 matches |
| `routes/ui.py` | `/` | Legacy Jinja2 web UI (do not add new features here) |

Key `api_v2.py` endpoints:
- `GET /api/v2/auth/me`, `PUT /api/v2/auth/settings`
- `GET /api/v2/games/mine`, `/games/recent`, `/games/search/<id>`
- `POST /api/v2/upload/log`, `/upload/simple`, `/upload/extended`
- `GET /api/v2/decks/search`, `/decks/<id>`
- `GET /api/v2/users/<username>`
- `POST /api/v2/collection/sync`, `GET /api/v2/collection/sync/status`, `GET /api/v2/collection`
- `GET /api/v2/timing-leaderboard`

`leagues.py` is ~4000 lines — main league file with all team, draft, week, pairing, and pool logic.

### Serializers: `keytracker/serializers.py`
Converts SQLAlchemy models to dicts for JSON API responses. Key functions: `serialize_league_detail`, `serialize_team_detail` (accepts `hide_members` param — used during drafting to hide rosters from non-admins/non-captains), `serialize_league_week`, `serialize_matchup`.

### Rendering: `keytracker/renderers.py`
Formats game log messages into styled HTML with card hover images via regex matching (Jinja2 UI only).

### Background Workers (in `keytracker/server.py`)
Started on launch if enabled:
- Deck enrichment: Fetches SAS/AERC from DoK for un-enhanced decks. Enabled with `ENABLE_COLLECTOR=1`.
- Collection sync: Async DoK collection sync via job queue (pending/running/completed/failed). Always runs.
- Card refresher: Periodic deck listing refresh from Master Vault. Enabled with `ENABLE_CARD_REFRESHER=1`.

### React Frontend: `frontend/`
React + TypeScript + Material UI SPA. Built with Vite to `frontend/dist/`, served by Flask at `/`.

**Pages** (`frontend/src/pages/`):
- League: `LeagueListPage`, `CreateLeaguePage`, `LeagueDetailPage`, `LeagueAdminPage`, `MyLeagueInfoPage`, `MyTeamPage`, `DraftBoardPage`
- Games: `GamesSearchPage`, `GameDetailPage`, `StandaloneMatchesPage`, `StandaloneMatchPage`, `UploadLogPage`
- Decks: `DecksSearchPage`, `DeckDetailPage`
- Users: `UserProfilePage`, `AccountPage`, `MyGamesPage`, `MyCollectionPage`
- Admin: `UserAdminPage`, `TimingLeaderboardPage`

**API client** (`frontend/src/api/`): `leagues.ts`, `games.ts`, `decks.ts`, `users.ts`, `collection.ts`, `auth.ts`, `admin.ts`, `standalone.ts`

**Frontend dev**:
```bash
cd frontend && npm install && npm run dev   # Dev server on port 5173 (proxies /api to Flask)
cd frontend && npm run build                # Build to frontend/dist/
```

## Configuration

### Environment Variables (when `TRACKER_CONFIG_PATH=ENV`)
- `DATABASE_URL` — full database URI
- `SECRET_KEY` — Flask secret key
- `DOK_API_KEY` — Decks of Keyforge API key
- `ENABLE_COLLECTOR=1` — start deck enrichment background thread
- `ENABLE_CARD_REFRESHER=1` — start card refresher background thread
- `HTTP_PORT`, `HTTPS_PORT`, `SSL_CERTFILE`, `SSL_KEYFILE` — for `start.sh`

### config.ini Sections (alternative to env vars)
`[db]`, `[app]`, `[google]`, `[patreon]`, `[discord]`, `[email]`, `[recaptcha]`
See `config_example.ini` for structure.

## External API Dependencies

- **Master Vault API** — deck data (rate-limited, 1 call/sec in `utils.py`)
- **Decks of Keyforge API** — SAS/AERC scores (requires `DOK_API_KEY`)

## Database

Supports MySQL (production) and SQLite (development) via configurable driver in config.ini. Connection pool: size 20, timeout 5s, READ COMMITTED isolation, pre-ping enabled. Multiple MySQL retry decorators in `utils.py` and `server.py` handle transient connection errors.

## Frontend/Backend Sync

The TypeScript frontend manually mirrors certain Python enums from `keytracker/schema.py`. When modifying these enums, update both sides:

- `WeekStatus` (`schema.py`) ↔ `WeekStatus` type in `frontend/src/types.ts`

## Important Gotchas

- **Docker `--restart always`**: Always include this flag in `docker run`.
- **`VITE_RECAPTCHA_SITE_KEY` is a required build arg** — frontend build fails without it.
- **`hide_team_members` in serializers**: During `drafting` status, `serialize_team_detail` is called with `hide_members=True` for non-admin/non-captain viewers. Don't bypass this when adding new team-related serialization.
- **Co-captains**: Teams can have multiple captains (`is_captain=True` on multiple `TeamMember` rows). The `assign_captain` endpoint no longer clears existing captains. Use `DELETE .../captain/<user_id>` to remove captaincy.
- **Guest user**: `nobody@example.com` is created at startup by `_ensure_nobody_user()` in `server.py`. Used as opponent placeholder in standalone matches.
- **UI is legacy Jinja2**: All new pages/features use the React/MUI frontend. Do not add to `keytracker/templates/` or `routes/ui.py`.
- **League admin log**: All admin actions on leagues are logged to `LeagueAdminLog` (visible in Admin Log tab of LeagueAdminPage). Use `_log_admin_action()` helper in `leagues.py` when adding admin endpoints.
- **Tab indices in LeagueDetailPage**: Computed as named variables (e.g., `teamsIdx`, `signupsIdx`), not magic numbers. They are conditional based on `showTeamLists` and `showSignups` — recalculate all when adding new tabs.
