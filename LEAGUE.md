# League Feature Architecture

## Overview
Team-based league competitions with admin-managed setup, snake draft for player selection, and per-league pages.

## Database Models (keytracker/schema.py)

- **League**: Core league entity with name, description, fee_amount, team_size, num_teams, status (setup/drafting/active/completed)
- **LeagueAdmin**: Join table for per-league admin access (league_id, user_id)
- **Team**: Belongs to league, has name and order_number (used for draft ordering)
- **TeamMember**: User on a team, with is_captain and has_paid flags
- **LeagueSignup**: User signup for a league, with signup_order and status (signed_up/drafted/waitlisted)
- **DraftPick**: Records each draft pick (round_number, pick_number, team_id, picked_user_id)
- **User.is_league_admin**: Boolean flag granting permission to create new leagues

## Enums
- **LeagueStatus**: setup → drafting → active → completed
- **SignupStatus**: signed_up → drafted/waitlisted (set when draft starts)

## API Endpoints (keytracker/routes/leagues.py)

Blueprint: `/api/v2/leagues`

### League CRUD
- `GET /` — list all leagues
- `POST /` — create league (requires is_league_admin)
- `GET /<id>` — league detail with current-user context flags
- `PUT /<id>` — update settings (admin, setup only)

### Signups
- `POST /<id>/signup` — sign up (setup only)
- `DELETE /<id>/signup` — withdraw (setup only)

### Teams
- `GET /<id>/teams` — list teams
- `POST /<id>/teams` — create team (admin)
- `PUT /<id>/teams/<tid>` — update team name (admin or captain)
- `DELETE /<id>/teams/<tid>` — delete team (admin, setup only)

### Captain & Fees
- `POST /<id>/teams/<tid>/captain` — assign captain from signup list (admin)
- `POST /<id>/teams/<tid>/fees/<uid>` — toggle fee paid (admin or captain)

### Admins
- `POST /<id>/admins` — add league admin
- `DELETE /<id>/admins/<uid>` — remove league admin

### Draft
- `POST /<id>/draft/start` — transition setup → drafting
- `GET /<id>/draft` — get draft state (captains + admins only)
- `POST /<id>/draft/pick` — make a pick (current captain or admin)

## Draft Mechanics

- **Snake draft**: Round 1 goes team 1→N by order_number, Round 2 goes N→1, alternating
- **State is computed**: `compute_draft_state()` recalculates from DraftPick records each time
- **Captains fill 1 spot**: Each team drafts `team_size - 1` additional players
- **Auto-transition**: When all picks made, league status → active
- **Waitlisting**: When draft starts, signups beyond available spots get waitlisted

## Frontend Pages

- `/leagues` — LeagueListPage: list all leagues, create button for admins
- `/leagues/new` — CreateLeaguePage: league creation form
- `/league/:id` — LeagueDetailPage: teams, signups, action buttons
- `/league/:id/admin` — LeagueAdminPage: settings, team management, captain assignment, start draft
- `/league/:id/draft` — DraftBoardPage: 5-second polling, pick grid, available players
- `/league/:id/my-info` — MyLeagueInfoPage: team info, fee status
- `/league/:id/my-team` — MyTeamPage: captain-only team management

## Test Users & Impersonation

### Test Users
- `is_test_user` boolean on User model
- Created via CLI: `flask create-test-users` (creates TestUser1–TestUser20, idempotent)
- No password/Google auth — only usable via impersonation

### Test Leagues
- `is_test` boolean on League model, set at creation time
- Shown as "Test" chip in league list and detail pages

### Per-Tab Impersonation
Allows an admin to act as different test users in different browser tabs:

1. **Frontend**: `TestUserContext` stores `testUserId` in React state (per component tree = per tab)
2. **API interceptor**: Axios request interceptor attaches `X-Test-User-Id` header when set
3. **Backend**: `get_effective_user()` in `keytracker/routes/leagues.py` validates:
   - Real `current_user` is a league admin (`is_league_admin`)
   - Target user is a test user (`is_test_user == True`)
   - Returns the test User object instead of `current_user`
4. All league endpoints use `get_effective_user()` for user identity
5. Non-league endpoints (auth/me, etc.) are unaffected
6. `TestUserPicker` component (floating bottom-right panel) visible only to league admins

### API Endpoint
- `GET /api/v2/leagues/test-users` — returns list of test users (league admins only)

## Key Design Decisions

1. `is_league_admin` on User controls who can create leagues; `LeagueAdmin` table controls per-league admin access
2. Captains must sign up first, then admins assign them to teams
3. Draft board visibility: captains and league admins only during drafting
4. Draft uses 5-second polling (no websockets)
5. League creator is automatically added as a league admin
