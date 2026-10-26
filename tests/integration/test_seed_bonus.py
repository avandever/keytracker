"""Seeds carry points into the playoffs, and scoring stays editable after the draw."""
import json
import os
import sys

os.environ["TRACKER_CONFIG_PATH"] = "ENV"
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.pop("ENABLE_COLLECTOR", None)

from keytracker.server import app
from keytracker.schema import (
    KeyforgeSet, League, LeagueAdmin, LeagueStatus, Team, TeamMember, User, db,
)

FAIL = []
DM = 928


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + str(detail)) if detail else ''}")
    if not ok:
        FAIL.append(label)


def body(r):
    try:
        return json.loads(r.data)
    except Exception:
        return {"raw": r.data[:200].decode("utf-8", "replace")}


with app.app_context():
    db.drop_all()
    db.create_all()
    db.session.add(KeyforgeSet(number=DM, name="Draconian Measures",
                               shortname="DM", dokname="DM"))
    admin = User(email="admin@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="Seeds", team_size=1, num_teams=4,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))
    teams, players = [], {}
    for i, label in enumerate("ABCD"):
        team = Team(league_id=league.id, name=f"Team {label}", order_number=i + 1)
        db.session.add(team)
        db.session.flush()
        u = User(email=f"{label}@e.com", name=f"Player {label}")
        db.session.add(u)
        db.session.flush()
        db.session.add(TeamMember(team_id=team.id, user_id=u.id, is_captain=True))
        teams.append(team.id)
        players[team.id] = u.id
    db.session.commit()
    league_id, admin_id = league.id, admin.id

c = app.test_client()
base = f"/api/v2/leagues/{league_id}/playoffs"
with c.session_transaction() as s:
    s["_user_id"] = str(admin_id)
    s["_fresh"] = True


def standings():
    return body(c.get(f"{base}/standings"))


r = c.put(f"{base}/config", json={
    "teams_advancing": 4, "points_per_round": [1, 2],
    "seed_bonus_points": [3, 2, 1],
})
check("the bonus saves", r.status_code == 200, str(body(r))[:80])
check("and comes back on the config",
      body(r).get("seed_bonus_points") == [3, 2, 1],
      body(r).get("seed_bonus_points"))

r = c.put(f"{base}/brackets", json={"brackets": [
    {"name": "One", "format_type": "archon_standard", "allowed_sets": [DM]},
]})
bracket_id = body(r)["brackets"][0]["id"]
# Seeded in order: Team A first, Team D last.
c.put(f"{base}/qualifiers", json={"team_ids": teams})

got = {row["team_name"]: row for row in standings()["standings"]}
check("first seed carries 3", got["Team A"]["points"] == 3, got["Team A"]["points"])
check("second carries 2", got["Team B"]["points"] == 2, got["Team B"]["points"])
check("third carries 1", got["Team C"]["points"] == 1, got["Team C"]["points"])
check("and fourth carries nothing, being past the list",
      got["Team D"]["points"] == 0, got["Team D"]["points"])
check("the floor includes it", got["Team A"]["min_points"] == 3,
      got["Team A"]["min_points"])
check("and so does the ceiling",
      got["Team A"]["max_points"] == 3 + 1 + 2, got["Team A"]["max_points"])

# --- and it still adds up once the brackets are out ----------------------
c.post(f"{base}/publish", json={"published": True})
for t in teams:
    with c.session_transaction() as s:
        s["_user_id"] = str(players[t])
    c.put(f"{base}/assignments", json={"team_id": t, "assignments": [
        {"bracket_id": bracket_id, "user_id": players[t]},
    ]})
with c.session_transaction() as s:
    s["_user_id"] = str(admin_id)
c.post(f"{base}/assignments/publish", json={"published": True})
c.post(f"{base}/draw", json={"seed": 4})

# --- scoring may still be corrected; the bracket shape may not -----------
r = c.put(f"{base}/config", json={"seed_bonus_points": [5, 3, 1]})
check("the bonus can be corrected after the draw", r.status_code == 200,
      str(body(r))[:90])
got = {row["team_name"]: row for row in standings()["standings"]}
check("and the standings follow it", got["Team A"]["points"] == 5,
      got["Team A"]["points"])

r = c.put(f"{base}/config", json={"teams_advancing": 2})
check("but the shape of the draw cannot be changed",
      r.status_code == 400 and "teams_advancing" in str(body(r).get("error", "")),
      body(r).get("error"))

r = c.put(f"{base}/config", json={"seed_bonus_points": []})
check("clearing it is allowed", r.status_code == 200, str(body(r))[:70])
got = {row["team_name"]: row for row in standings()["standings"]}
check("and then nobody carries anything",
      all(row["points"] == 0 for row in got.values()),
      {k: v["points"] for k, v in got.items()})

r = c.put(f"{base}/config", json={"seed_bonus_points": [3, -1]})
check("a negative bonus is refused", r.status_code == 400,
      body(r).get("error"))

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
