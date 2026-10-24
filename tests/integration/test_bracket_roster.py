"""A bracket week names the one player from the viewer's own team."""
import json
import os
import sys

os.environ["TRACKER_CONFIG_PATH"] = "ENV"
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.pop("ENABLE_COLLECTOR", None)

from keytracker.server import app
from keytracker.schema import (
    League, LeagueAdmin, LeagueStatus, Team, TeamMember, User, db,
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


TEAMS, SIZE = 4, 2

with app.app_context():
    db.drop_all()
    db.create_all()
    admin = User(email="admin@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="Roster", team_size=SIZE, num_teams=TEAMS,
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
        s["_user_id"] = str(user_id)
        s["_fresh"] = True


act_as(admin_id)
c.put(f"{base}/config", json={"teams_advancing": TEAMS, "points_per_round": [1, 2]})
r = c.put(f"{base}/brackets", json={"brackets": [
    {"name": "One", "format_type": "archon_standard"},
    {"name": "Two", "format_type": "triad"},
]})
b1, b2 = [b["id"] for b in body(r)["brackets"]]
c.put(f"{base}/qualifiers", json={"team_ids": teams})
c.post(f"{base}/publish", json={"published": True})

# Everyone fills bracket one; nobody fills bracket two.
for team_id in teams:
    act_as(players[team_id][0])
    c.put(f"{base}/assignments", json={"team_id": team_id, "assignments": [
        {"bracket_id": b1, "user_id": players[team_id][0]},
    ]})

act_as(admin_id)
c.post(f"{base}/draw", json={"seed": 5})
r = c.post(f"{base}/rounds/1/start", json={})
check("both bracket weeks open", body(r).get("weeks_created") == 2,
      body(r).get("weeks_created"))


def weeks_for(user_id):
    act_as(user_id)
    data = body(c.get(f"/api/v2/leagues/{league_id}"))
    return {w["playoff_bracket_id"]: w for w in data.get("playoff_weeks", [])}


# --- each team is told its own player, and only its own -------------------
for team_id in teams:
    for who, label in ((players[team_id][0], "captain"), (players[team_id][1], "teammate")):
        got = weeks_for(who)
        check(f"team {team_id}'s {label} sees their own player in bracket one",
              got[b1]["playoff_team_user_id"] == players[team_id][0],
              got[b1]["playoff_team_user_id"])
        check(f"and nobody in the bracket team {team_id} has not filled",
              got[b2]["playoff_team_user_id"] is None,
              got[b2]["playoff_team_user_id"])

# The value must be this team's, never a rival's.
mine = weeks_for(players[teams[0]][0])
others = {players[t][0] for t in teams[1:]}
check("a rival's player never appears in my week",
      mine[b1]["playoff_team_user_id"] not in others,
      mine[b1]["playoff_team_user_id"])

# --- an ordinary week is unaffected ---------------------------------------
act_as(players[teams[0]][0])
data = body(c.get(f"/api/v2/leagues/{league_id}"))
check("ordinary weeks are not given one", all(
    w.get("playoff_team_user_id") is None for w in data.get("weeks", [])
))

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
