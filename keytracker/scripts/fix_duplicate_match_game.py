"""
Fix duplicate MatchGame records for the Ewok_jr vs Shadowmeld feature match.

Bug: both players independently reported game 1 as Ewok_jr winning 3-2.
  - game 1 (id=81): reported by Shadowmeld, Ewok_jr won 3-2  ← keep
  - game 2 (id=82): reported by Ewok_jr, Ewok_jr won 3-2  ← delete (duplicate)

After fix, Shadowmeld can report his actual game 2 and game 3 wins.

Run with:
  python keytracker/scripts/fix_duplicate_match_game.py [--dry-run]
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_dotenv('.env')
os.environ.setdefault('TRACKER_CONFIG_PATH', 'ENV')

from keytracker.server import app
from keytracker.schema import db, PlayerMatchup, MatchGame, User

DRY_RUN = '--dry-run' in sys.argv

MATCHUP_ID = 43   # Ewok_jr (p1=48) vs Shadowmeld (p2=37)
DUPLICATE_GAME_ID = 82  # game#=2, same result as game#=1


def main():
    with app.app_context():
        pm = db.session.get(PlayerMatchup, MATCHUP_ID)
        if not pm:
            print(f"ERROR: PlayerMatchup {MATCHUP_ID} not found.")
            return

        games = sorted(pm.games, key=lambda g: (g.game_number, g.id))
        print(f"PlayerMatchup id={pm.id}  (p1={pm.player1_id}, p2={pm.player2_id})")
        print("\nCurrent games:")
        for g in games:
            p1 = db.session.get(User, pm.player1_id)
            p2 = db.session.get(User, pm.player2_id)
            winner = p1 if g.winner_id == pm.player1_id else p2
            rb = db.session.get(User, g.reported_by_id)
            print(f"  id={g.id} game#={g.game_number} winner={winner.name} ({g.player1_keys}-{g.player2_keys}) reported_by={rb.name if rb else g.reported_by_id}")

        dup = db.session.get(MatchGame, DUPLICATE_GAME_ID)
        if not dup:
            print(f"\nGame id={DUPLICATE_GAME_ID} not found — already deleted?")
            return
        if dup.player_matchup_id != MATCHUP_ID:
            print(f"\nERROR: Game {DUPLICATE_GAME_ID} belongs to matchup {dup.player_matchup_id}, not {MATCHUP_ID}.")
            return

        print(f"\nPlan: DELETE MatchGame id={DUPLICATE_GAME_ID} (game#={dup.game_number}, duplicate of game#=1)")

        if DRY_RUN:
            print("\nDRY RUN — no changes made. Remove --dry-run to apply.")
            return

        confirm = input("\nApply? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("Aborted.")
            return

        db.session.delete(dup)
        db.session.commit()
        print("Done.")

        print("\nUpdated games:")
        db.session.refresh(pm)
        for g in sorted(pm.games, key=lambda g: g.game_number):
            p1 = db.session.get(User, pm.player1_id)
            p2 = db.session.get(User, pm.player2_id)
            winner = p1 if g.winner_id == pm.player1_id else p2
            print(f"  id={g.id} game#={g.game_number} winner={winner.name} ({g.player1_keys}-{g.player2_keys})")


if __name__ == '__main__':
    main()
