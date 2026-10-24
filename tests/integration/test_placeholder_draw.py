"""Drawing with the teams alone, and binding players as captains finish."""
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


TEAMS = 4
SIZE = 2

with app.app_context():
    db.drop_all()
    db.create_all()
    admin = User(email="admin@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="Placeholders", team_size=SIZE, num_teams=TEAMS,
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


def tree():
    return {b["id"]: b for b in body(c.get(f"{base}/brackets/tree"))["brackets"]}


def put_assignments(team_id, pairs):
    return c.put(f"{base}/assignments", json={
        "team_id": team_id,
        "assignments": [{"bracket_id": bid, "user_id": uid} for bid, uid in pairs],
    })


# --- the draw happens with nobody assigned ---------------------------------
r = c.post(f"{base}/draw", json={"seed": 3})
out = body(r)
check("the brackets draw with nobody assigned", r.status_code == 200, str(out)[:100])
check("and make two rounds for four teams", out.get("rounds") == 2, out.get("rounds"))

t = tree()
check("every bracket hides its pairings",
      all(b["pairings_hidden"] for b in t.values()),
      {k: v["pairings_hidden"] for k, v in t.items()})
sides = [m["team1_id"] for m in t[b1]["matches"]] + [m["team2_id"] for m in t[b1]["matches"]]
check("so no team shows in any slot", all(s is None for s in sides), sides)

# --- captains can still assign after the draw ------------------------------
act_as(players[teams[0]][0])
r = put_assignments(teams[0], [(b1, players[teams[0]][0])])
check("a captain can assign after the draw", r.status_code == 200, body(r).get("error"))

# Every team fills bracket one, leaving bracket two empty.
for team_id in teams[1:]:
    act_as(players[team_id][0])
    r = put_assignments(team_id, [(b1, players[team_id][0])])
    check(f"team {team_id} fills bracket one", r.status_code == 200, body(r).get("error"))

act_as(admin_id)
t = tree()
check("a filled bracket shows its pairings", t[b1]["pairings_hidden"] is False)
sides = [m["team1_id"] for m in t[b1]["matches"] if m["round_number"] == 1]
check("with teams in the first-round slots", all(s is not None for s in sides), sides)
check("the unfilled bracket still hides its own", t[b2]["pairings_hidden"] is True)

# --- publishing still needs the whole house -------------------------------
r = c.post(f"{base}/assignments/publish", json={"published": True})
check("publishing waits for every bracket", r.status_code == 400, str(body(r))[:80])
check("and counts the four that are missing", body(r).get("missing_count") == 4,
      body(r).get("missing_count"))

# --- a round opens with no matches while that is outstanding ---------------
r = c.post(f"{base}/rounds/1/start", json={"bracket_id": b1})
out = body(r)
check("one bracket's round opens on its own", out.get("weeks_created") == 1,
      out.get("weeks_created"))
check("without matchups", out.get("matches_created") == 0, out.get("matches_created"))

# --- fill the rest, publish, and bind bracket one --------------------------
for team_id in teams:
    act_as(players[team_id][0])
    r = put_assignments(team_id, [(b1, players[team_id][0]), (b2, players[team_id][1])])
    check(f"team {team_id} fills both", r.status_code == 200, body(r).get("error"))

act_as(admin_id)
r = c.post(f"{base}/assignments/publish", json={"published": True})
check("publishing now works", r.status_code == 200, str(body(r))[:80])
r = c.post(f"{base}/rounds/1/start", json={"bracket_id": b1})
check("bracket one's matchups are made", body(r).get("matches_created") == 2,
      body(r).get("matches_created"))

t = tree()
check("bracket one is now locked", t[b1]["assignments_locked"] is True)
check("bracket two is not", t[b2]["assignments_locked"] is False)

# --- the lock is per bracket ----------------------------------------------
act_as(players[teams[0]][0])
r = put_assignments(teams[0], [(b1, players[teams[0]][1]), (b2, players[teams[0]][0])])
check("changing a started bracket is refused", r.status_code == 400, body(r).get("error"))

# Bracket two alone still moves, and bracket one is left as it was.
r = put_assignments(teams[0], [(b1, players[teams[0]][0]), (b2, players[teams[0]][1])])
check("sending the started one back unchanged is fine", r.status_code == 200,
      body(r).get("error"))
# Published by now, so the reply carries every team: look at ours.
mine = {b["id"]: [a for a in b["assignments"] if a["team_id"] == teams[0]]
        for b in body(r)["brackets"]}
check("bracket one keeps its player",
      [a["user_id"] for a in mine[b1]] == [players[teams[0]][0]],
      [a["user_id"] for a in mine[b1]])

# A player fixed in a started bracket cannot be moved into another.
r = put_assignments(teams[0], [(b2, players[teams[0]][0])])
check("and its player cannot be put in another bracket",
      r.status_code == 400, body(r).get("error"))

# Omitting the started bracket does not wipe it.
r = put_assignments(teams[0], [(b2, players[teams[0]][1])])
check("omitting the started bracket leaves it alone", r.status_code == 200,
      body(r).get("error"))
mine = {b["id"]: [a for a in b["assignments"] if a["team_id"] == teams[0]]
        for b in body(r)["brackets"]}
check("it still has its player",
      [a["user_id"] for a in mine[b1]] == [players[teams[0]][0]],
      [a["user_id"] for a in mine[b1]])

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
