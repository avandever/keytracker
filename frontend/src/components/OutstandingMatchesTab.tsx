import { Box, Card, CardContent, Chip, Typography } from '@mui/material';
import CaptainMatchControls from './CaptainMatchControls';
import type { LeagueDetail, LeagueWeek, PlayerMatchupInfo } from '../types';

interface Props {
  leagueId: number;
  league: LeagueDetail;
  myTeamId: number;
  onChanged: () => void;
  setError: (msg: string) => void;
  setSuccess: (msg: string) => void;
}

interface Outstanding {
  week: LeagueWeek;
  pm: PlayerMatchupInfo;
  /** Player on the captain's own team, shown first. */
  mine: { id: number; name: string };
  theirs: { id: number; name: string };
  myWins: number;
  theirWins: number;
  decided: boolean;
}

/**
 * Every match on this team that still needs something done to it, across all
 * weeks, so a captain chasing results does not have to open each week tab in
 * turn and work out which ones are missing.
 */
export default function OutstandingMatchesTab({
  leagueId,
  league,
  myTeamId,
  onChanged,
  setError,
  setSuccess,
}: Props) {
  const myMemberIds = new Set(
    (league.teams.find((t) => t.id === myTeamId)?.members ?? []).map((m) => m.user.id),
  );

  const outstanding: Outstanding[] = [];
  for (const week of league.weeks || []) {
    // Nothing to report before pairings are out.
    if (week.status !== 'published' && week.status !== 'completed') continue;
    const winsNeeded = Math.ceil(week.best_of_n / 2);
    for (const wm of week.matchups) {
      if (wm.team1.id !== myTeamId && wm.team2.id !== myTeamId) continue;
      for (const pm of wm.player_matchups) {
        if (pm.is_double_loss) continue;
        const p1Wins = pm.games.filter((g) => g.winner_id === pm.player1.id).length;
        const p2Wins = pm.games.filter((g) => g.winner_id === pm.player2.id).length;
        const decided = p1Wins >= winsNeeded || p2Wins >= winsNeeded;
        if (decided && pm.result_confirmed) continue; // fully done
        const p1IsMine = myMemberIds.has(pm.player1.id);
        outstanding.push({
          week,
          pm,
          mine: p1IsMine ? pm.player1 : pm.player2,
          theirs: p1IsMine ? pm.player2 : pm.player1,
          myWins: p1IsMine ? p1Wins : p2Wins,
          theirWins: p1IsMine ? p2Wins : p1Wins,
          decided,
        });
      }
    }
  }

  if (outstanding.length === 0) {
    return (
      <Typography color="text.secondary">
        Nothing outstanding — every match with pairings out is reported and verified.
      </Typography>
    );
  }

  // Group by week so the list reads in the order a captain thinks about it.
  const byWeek = new Map<number, Outstanding[]>();
  for (const o of outstanding) {
    const list = byWeek.get(o.week.id) ?? [];
    list.push(o);
    byWeek.set(o.week.id, list);
  }

  return (
    <>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {outstanding.length} match{outstanding.length !== 1 ? 'es' : ''} still need
        {outstanding.length !== 1 ? '' : 's'} a result or a verification.
      </Typography>
      {[...byWeek.entries()].map(([weekId, items]) => {
        const week = items[0].week;
        return (
          <Card key={weekId} sx={{ mb: 2 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                {week.name || `Week ${week.week_number}`}
              </Typography>
              {items.map((o) => {
                const unverified = o.decided && !o.pm.result_confirmed;
                return (
                  <Box key={o.pm.id} sx={{ mb: 2, pb: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 1 }}>
                      <Typography variant="body2">
                        {o.mine.name} {o.myWins} - {o.theirWins} {o.theirs.name}
                      </Typography>
                      {!unverified && <Chip label="Needs result" size="small" color="default" />}
                    </Box>

                    <CaptainMatchControls
                      leagueId={leagueId}
                      week={o.week}
                      pm={o.pm}
                      mine={o.mine}
                      theirs={o.theirs}
                      decided={o.decided}
                      onChanged={onChanged}
                      setError={setError}
                      setSuccess={setSuccess}
                    />
                  </Box>
                );
              })}
            </CardContent>
          </Card>
        );
      })}
      <Typography variant="caption" color="text.secondary">
        Formats that need a deck chosen per game (Triad, Moirai and similar) must be
        reported from the week tab, which knows which decks are legal.
      </Typography>
    </>
  );
}
