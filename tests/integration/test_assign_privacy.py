"""Who can see which player a team put in a bracket, and when."""
import json
import os
import sys

os.environ["TRACKER_CONFIG_PATH"] = "ENV"
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.pop("ENABLE_COLLECTOR", None)

from keytracker.server import app
from keytracker.schema import (
    League, LeagueAdmin, LeagueStatus, PlayoffConfig, Team, TeamMember, User, db,
)

FAIL = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + str(detail)) if detail else ''}")
    if not ok:
        FAIL.append(label)


def body(r):
    try:
        return json.loads(r.data)
    except Exception:
        return {"raw": r.data[:300].decode("utf-8", "replace")}


TEAMS = 4
SIZE = 2

with app.app_context():
    db.drop_all()
    db.create_all()
    admin = User(email="admin@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="Privacy", team_size=SIZE, num_teams=TEAMS,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))
    teams, players = [], {}
    for t in range(TEAMS):
        team = Team(league_id=league.id, name=f"T{t+1}", order_number=t + 1)
        db.session.add(team)
        db.session.flush()
        roster = []
        for p in range(SIZE):
            u = User(email=f"t{t}p{p}@e.com", name=f"T{t+1}P{p+1}")
            db.session.add(u)
            db.session.flush()
            # The first on each team captains it.
            db.session.add(TeamMember(team_id=team.id, user_id=u.id, is_captain=(p == 0)))
            roster.append(u.id)
        teams.append(team.id)
        players[team.id] = roster
    db.session.commit()
    league_id, admin_id = league.id, admin.id

c = app.test_client()
base = f"/api/v2/leagues/{league_id}/playoffs"


def act_as(user_id):
    with c.session_transaction() as s:
        if user_id is None:
            s.clear()
        else:
            s["_user_id"] = str(user_id)
            s["_fresh"] = True


act_as(admin_id)
c.put(f"{base}/config", json={"teams_advancing": TEAMS, "points_per_round": [1, 2]})
r = c.put(f"{base}/brackets", json={"brackets": [
    {"name": "One", "format_type": "archon_standard"},
    {"name": "Two", "format_type": "triad"},
]})
bracket_ids = [b["id"] for b in body(r)["brackets"]]
check("two brackets defined", len(bracket_ids) == 2, body(r).get("error"))
c.put(f"{base}/qualifiers", json={"team_ids": teams})
r = c.post(f"{base}/publish", json={"published": True})
check("setup published", r.status_code == 200, body(r))


def assign(team_id, captain_id):
    return c.put(f"{base}/assignments", json={
        "team_id": team_id,
        "assignments": [
            {"bracket_id": bracket_ids[i], "user_id": players[team_id][i]}
            for i in range(SIZE)
        ],
    })


# --- team 1 assigns; nobody else should learn anything ----------------------
act_as(players[teams[0]][0])
r = assign(teams[0], players[teams[0]][0])
check("a captain can assign", r.status_code == 200, body(r).get("error"))
own = [b for b in body(r)["brackets"]]
check("the save returns the team's own picks",
      all(len(b["assignments"]) == 1 for b in own),
      [len(b["assignments"]) for b in own])


def seen_by(user_id):
    act_as(user_id)
    data = body(c.get(base))
    return data, sum(len(b["assignments"]) for b in data["brackets"])


mine, count = seen_by(players[teams[0]][0])
check("team 1 sees its own two", count == 2, count)
check("and is told they are not revealed",
      all(b["assignments_revealed"] is False for b in mine["brackets"]))

_, count = seen_by(players[teams[0]][1])
check("a non-captain on team 1 sees them too", count == 2, count)

_, count = seen_by(players[teams[1]][0])
check("the rival captain sees nothing", count == 0, count)

_, count = seen_by(admin_id)
check("the admin sees nothing either", count == 0, count)

_, count = seen_by(None)
check("a signed-out visitor sees nothing", count == 0, count)

# The raw payload must not carry a name anywhere a rival could dig it out.
act_as(players[teams[1]][0])
raw = c.get(base).data.decode("utf-8")
leaked = [p for p in ("T1P1", "T1P2") if p in raw]
check("no team 1 player name anywhere in the rival's payload", not leaked, leaked)

# --- progress is visible without the names ---------------------------------
data, _ = seen_by(admin_id)
progress = {row["team_name"]: (row["assigned"], row["total"])
            for row in data["assignment_progress"]}
check("progress counts team 1 as done", progress.get("T1") == (2, 2), progress.get("T1"))
check("and the rest as untouched",
      all(progress[f"T{i+1}"] == (0, 2) for i in range(1, TEAMS)), progress)

# --- publishing is refused while anything is missing -----------------------
act_as(admin_id)
r = c.post(f"{base}/assignments/publish", json={"published": True})
check("publishing is refused while brackets are unfilled", r.status_code == 400,
      str(body(r))[:90])
check("and it says how many are missing", body(r).get("missing_count") == 6,
      body(r).get("missing_count"))

act_as(players[teams[1]][0])
r = c.post(f"{base}/assignments/publish", json={"published": True})
check("a captain cannot publish", r.status_code == 403, body(r))

# --- everyone assigns, then it publishes -----------------------------------
for team_id in teams[1:]:
    act_as(players[team_id][0])
    r = assign(team_id, players[team_id][0])
    check(f"team {team_id} assigns", r.status_code == 200, body(r).get("error"))

act_as(admin_id)
r = c.post(f"{base}/assignments/publish", json={"published": True})
check("publishing now works", r.status_code == 200, body(r))
check("the config carries the timestamp",
      bool(body(r).get("assignments_published_at")), body(r).get("assignments_published_at"))

_, count = seen_by(players[teams[1]][0])
check("the rival captain now sees all eight", count == TEAMS * SIZE, count)
data, _ = seen_by(None)
check("and so does a signed-out visitor",
      sum(len(b["assignments"]) for b in data["brackets"]) == TEAMS * SIZE)
check("revealed is now true", all(b["assignments_revealed"] for b in data["brackets"]))

# --- and it can be taken back ----------------------------------------------
act_as(admin_id)
r = c.post(f"{base}/assignments/publish", json={"published": False})
check("the reveal can be retracted", r.status_code == 200, body(r))
# Team 2 has assigned by now, so being blind again means seeing its own two
# and nothing of anyone else's.
_, count = seen_by(players[teams[1]][0])
check("the rival captain is back to only its own", count == SIZE, count)
act_as(players[teams[1]][0])
raw = c.get(base).data.decode("utf-8")
leaked = [p for p in ("T1P1", "T1P2", "T3P1", "T4P1") if p in raw]
check("and no other team's player is named again", not leaked, leaked)

# --- a round opened before the reveal must not leak through its matchups ----
act_as(admin_id)
r = c.post(f"{base}/draw", json={"seed": 7})
check("the brackets draw", r.status_code == 200, str(body(r))[:90])
r = c.post(f"{base}/rounds/1/start", json={})
out = body(r)
check("the round opens", r.status_code == 200, str(out)[:90])
check("its weeks are made", out.get("weeks_created") == 2, out.get("weeks_created"))
check("but no matchups, since the assignments are private",
      out.get("matches_created") == 0, out.get("matches_created"))
check("and it says how many it held back",
      out.get("matches_deferred") == 4, out.get("matches_deferred"))

r = c.post(f"{base}/assignments/publish", json={"published": True})
check("publishing after the draw works", r.status_code == 200, str(body(r))[:90])
r = c.post(f"{base}/rounds/1/start", json={})
out = body(r)
check("opening the round again fills the matchups in",
      out.get("matches_created") == 4, out.get("matches_created"))
check("and makes no second set of weeks", out.get("weeks_created") == 0,
      out.get("weeks_created"))

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
