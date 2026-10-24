"""A captain can ask My Info for the bracket their teammate is stuck in."""
import json
import os
import sys
import uuid

os.environ["TRACKER_CONFIG_PATH"] = "ENV"
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.pop("ENABLE_COLLECTOR", None)

from keytracker.server import app
from keytracker.schema import (
    KeyforgeSet, League, LeagueAdmin, LeagueStatus, Team, TeamMember, User, db,
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
        return {"raw": r.data[:200].decode("utf-8", "replace")}


DM = 928

with app.app_context():
    db.drop_all()
    db.create_all()
    db.session.add(KeyforgeSet(number=DM, name="Draconian Measures",
                               shortname="DM", dokname="DM"))
    admin = User(email="admin@e.com", name="Admin")
    db.session.add(admin)
    db.session.flush()
    league = League(name="Reach", team_size=2, num_teams=2,
                    status=LeagueStatus.ACTIVE.value, created_by_id=admin.id)
    db.session.add(league)
    db.session.flush()
    db.session.add(LeagueAdmin(league_id=league.id, user_id=admin.id))
    users, teams = {}, []
    for i, (label, names) in enumerate(
        (("A", ("Cap", "Stuck")), ("B", ("OtherCap", "Rival")))
    ):
        team = Team(league_id=league.id, name=f"Team {label}", order_number=i + 1)
        db.session.add(team)
        db.session.flush()
        teams.append(team.id)
        for j, name in enumerate(names):
            u = User(email=f"{name}@e.com", name=name)
            db.session.add(u)
            db.session.flush()
            db.session.add(
                TeamMember(team_id=team.id, user_id=u.id, is_captain=(j == 0))
            )
            users[name] = u.id
    db.session.commit()
    league_id, admin_id = league.id, admin.id

c = app.test_client()
base = f"/api/v2/leagues/{league_id}/playoffs"


def act_as(uid):
    with c.session_transaction() as s:
        s["_user_id"] = str(uid)
        s["_fresh"] = True


# Two brackets: the captain plays one, the stuck player the other.
act_as(admin_id)
c.put(f"{base}/config", json={"teams_advancing": 2, "points_per_round": [1]})
r = c.put(f"{base}/brackets", json={"brackets": [
    {"name": "Captains", "format_type": "archon_standard", "allowed_sets": [DM]},
    {"name": "Theirs", "format_type": "triad", "allowed_sets": [DM]},
]})
b_cap, b_other = [b["id"] for b in body(r)["brackets"]]
c.put(f"{base}/qualifiers", json={"team_ids": teams})
c.post(f"{base}/publish", json={"published": True})
for team_id, cap, player in ((teams[0], "Cap", "Stuck"),
                             (teams[1], "OtherCap", "Rival")):
    act_as(users[cap])
    c.put(f"{base}/assignments", json={"team_id": team_id, "assignments": [
        {"bracket_id": b_cap, "user_id": users[cap]},
        {"bracket_id": b_other, "user_id": users[player]},
    ]})
act_as(admin_id)
c.post(f"{base}/assignments/publish", json={"published": True})
c.post(f"{base}/draw", json={"seed": 1})
c.post(f"{base}/rounds/1/start", json={})


def brackets_for(uid, act_for=None):
    act_as(uid)
    url = f"/api/v2/leagues/{league_id}/my-info"
    if act_for:
        url += f"?act_for={act_for}"
    d = body(c.get(url))
    return (
        sorted(w["playoff_bracket_name"] for w in (d.get("playoff_weeks") or [])),
        d.get("acting_for_user_id"),
    )


names, acting = brackets_for(users["Cap"])
check("the captain's own My Info holds only their own bracket",
      names == ["Captains"], names)
check("and says it is acting for nobody", acting is None, acting)

names, acting = brackets_for(users["Cap"], users["Stuck"])
check("asking for their teammate adds that bracket",
      names == ["Captains", "Theirs"], names)
check("and says whose it is", acting == users["Stuck"], acting)

names, acting = brackets_for(users["Cap"], users["Rival"])
check("asking for the other team's player is refused",
      names == ["Captains"] and acting is None, (names, acting))

names, acting = brackets_for(users["Stuck"], users["Cap"])
check("a player who is not captain cannot ask for anyone",
      names == ["Theirs"] and acting is None, (names, acting))

names, acting = brackets_for(users["OtherCap"], users["Stuck"])
check("the opposing captain cannot ask for our player",
      acting is None, (names, acting))

print()
print("FAILED: " + str(FAIL) if FAIL else "all checks passed")
sys.exit(1 if FAIL else 0)
