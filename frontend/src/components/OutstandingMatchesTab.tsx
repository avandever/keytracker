import { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
  alpha,
} from '@mui/material';
import { reportGame, confirmMatchResult } from '../api/leagues';
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
  const [winnerById, setWinnerById] = useState<Record<number, number | ''>>({});
  const [winnerKeysById, setWinnerKeysById] = useState<Record<number, string>>({});
  const [loserKeysById, setLoserKeysById] = useState<Record<number, string>>({});
  const [busyId, setBusyId] = useState<number | null>(null);

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

  const handleVerify = async (pmId: number) => {
    setBusyId(pmId);
    setError('');
    try {
      await confirmMatchResult(leagueId, pmId);
      setSuccess('Result verified.');
      onChanged();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setBusyId(null);
    }
  };

  const handleReport = async (o: Outstanding) => {
    const winnerId = winnerById[o.pm.id];
    if (!winnerId) return;
    setBusyId(o.pm.id);
    setError('');
    try {
      const winnerKeys = parseInt(winnerKeysById[o.pm.id] ?? '3', 10) || 0;
      const loserKeys = parseInt(loserKeysById[o.pm.id] ?? '0', 10) || 0;
      await reportGame(leagueId, o.pm.id, {
        game_number: o.pm.games.length + 1,
        winner_id: winnerId,
        player1_keys: winnerId === o.pm.player1.id ? winnerKeys : loserKeys,
        player2_keys: winnerId === o.pm.player2.id ? winnerKeys : loserKeys,
      });
      setSuccess('Game reported.');
      setWinnerById((prev) => ({ ...prev, [o.pm.id]: '' }));
      onChanged();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setBusyId(null);
    }
  };

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
                const busy = busyId === o.pm.id;
                const unverified = o.decided && !o.pm.result_confirmed;
                return (
                  <Box key={o.pm.id} sx={{ mb: 2, pb: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 1 }}>
                      <Typography variant="body2">
                        {o.mine.name} {o.myWins} - {o.theirWins} {o.theirs.name}
                      </Typography>
                      {unverified ? (
                        <Chip
                          label="Unverified"
                          size="small"
                          sx={(theme) => ({
                            bgcolor: alpha(theme.palette.warning.main, 0.15),
                            color: theme.palette.warning.dark,
                          })}
                        />
                      ) : (
                        <Chip label="Needs result" size="small" color="default" />
                      )}
                      {unverified && (
                        <Button
                          size="small"
                          variant="outlined"
                          color="success"
                          disabled={busy}
                          onClick={() => handleVerify(o.pm.id)}
                        >
                          Verify
                        </Button>
                      )}
                    </Box>

                    {!o.decided && (
                      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                        <FormControl size="small" sx={{ minWidth: 160 }}>
                          <InputLabel>{`Game ${o.pm.games.length + 1} winner`}</InputLabel>
                          <Select
                            label={`Game ${o.pm.games.length + 1} winner`}
                            value={winnerById[o.pm.id] ?? ''}
                            onChange={(e) =>
                              setWinnerById((prev) => ({ ...prev, [o.pm.id]: e.target.value as number }))
                            }
                          >
                            <MenuItem value={o.mine.id}>{o.mine.name}</MenuItem>
                            <MenuItem value={o.theirs.id}>{o.theirs.name}</MenuItem>
                          </Select>
                        </FormControl>
                        <TextField
                          size="small"
                          label="Winner keys"
                          type="number"
                          sx={{ width: 110 }}
                          value={winnerKeysById[o.pm.id] ?? '3'}
                          onChange={(e) =>
                            setWinnerKeysById((prev) => ({ ...prev, [o.pm.id]: e.target.value }))
                          }
                        />
                        <TextField
                          size="small"
                          label="Loser keys"
                          type="number"
                          sx={{ width: 110 }}
                          value={loserKeysById[o.pm.id] ?? '0'}
                          onChange={(e) =>
                            setLoserKeysById((prev) => ({ ...prev, [o.pm.id]: e.target.value }))
                          }
                        />
                        <Button
                          size="small"
                          variant="contained"
                          disabled={busy || !winnerById[o.pm.id]}
                          onClick={() => handleReport(o)}
                        >
                          Report
                        </Button>
                      </Box>
                    )}
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
