import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import {
  reportGame,
  confirmMatchResult,
  markMatchAlreadyPlayed,
  submitTertiatePurgeRetroactive,
} from '../api/leagues';
import type { LeagueWeek, PlayerMatchupInfo } from '../types';

/**
 * Formats with a step before the first game, which both players have to start
 * for. Mirrors NEEDS_START in the reporting endpoint.
 */
const NEEDS_START = new Set([
  'triad',
  'triad_short',
  'tertiate',
  'adaptive',
  'adaptive_short',
  'oubliette',
  'nordic_hexad',
  'exchange',
  'moirai',
]);

/**
 * Formats where reporting a game also names the deck each player used, which
 * the endpoint requires and these controls do not collect. Mirrors the
 * per-format checks in the reporting endpoint.
 */
const NEEDS_DECK_PER_GAME = new Set(['triad', 'exchange', 'nordic_hexad', 'moirai']);

interface Props {
  leagueId: number;
  week: LeagueWeek;
  pm: PlayerMatchupInfo;
  /** The player on the captain's own team. */
  mine: { id: number; name: string };
  theirs: { id: number; name: string };
  /** Whether the match has already been won. */
  decided: boolean;
  onChanged: () => void;
  setError: (message: string) => void;
  setSuccess: (message: string) => void;
}

/**
 * Everything a captain can do to one of their team's matches: verify a result,
 * record a match played away from the site, fill in Tertiate purges after the
 * fact, and report a game on a player's behalf.
 *
 * The same controls belong wherever a captain is looking at the match -- the
 * outstanding list, or the week itself -- so they live here rather than being
 * written twice and drifting apart.
 */
export default function CaptainMatchControls({
  leagueId,
  week,
  pm,
  mine,
  theirs,
  decided,
  onChanged,
  setError,
  setSuccess,
}: Props) {
  const [winner, setWinner] = useState<number | ''>('');
  const [winnerKeys, setWinnerKeys] = useState('3');
  const [loserKeys, setLoserKeys] = useState('0');
  const [busy, setBusy] = useState(false);
  const [alreadyPlayedOpen, setAlreadyPlayedOpen] = useState(false);
  const [purgeMine, setPurgeMine] = useState('');
  const [purgeTheirs, setPurgeTheirs] = useState('');
  const [forgetting, setForgetting] = useState(false);

  const unverified = decided && !pm.result_confirmed && !pm.is_double_loss;
  // A match played off-site never got its Start presses, and without them the
  // report is refused.
  const needsStart =
    NEEDS_START.has(week.format_type) && !(pm.player1_started && pm.player2_started);
  const nextGame = pm.games.length + 1;
  const purgesThisGame = (pm.tertiate_purge_choices || []).filter(
    (p) => p.game_number === nextGame,
  );
  const needsPurges =
    week.format_type === 'tertiate' && !needsStart && purgesThisGame.length < 2;

  const slotOne = (userId: number) =>
    (week.deck_selections || []).find(
      (ds) => ds.user_id === userId && ds.slot_number === 1,
    );
  // Each player purges from the OTHER player's deck.
  const housesTheyCanTake = slotOne(theirs.id)?.deck?.houses || [];
  const housesTakenFromMine = slotOne(mine.id)?.deck?.houses || [];
  const canNameHouses = housesTheyCanTake.length > 0 && housesTakenFromMine.length > 0;

  const run = async (what: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setError('');
    try {
      await what();
      setSuccess(done);
      onChanged();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleVerify = () => run(() => confirmMatchResult(leagueId, pm.id), 'Result verified.');

  const handleAlreadyPlayed = () =>
    run(async () => {
      await markMatchAlreadyPlayed(leagueId, pm.id);
      setAlreadyPlayedOpen(false);
    }, 'Recorded as already played — you can enter the result now.');

  const handleRetroPurge = (notRecorded: boolean) =>
    run(async () => {
      const mineIsP1 = pm.player1.id === mine.id;
      const body = notRecorded
        ? { not_recorded: true }
        : {
            player1_house: mineIsP1 ? purgeMine : purgeTheirs,
            player2_house: mineIsP1 ? purgeTheirs : purgeMine,
          };
      await submitTertiatePurgeRetroactive(leagueId, pm.id, body);
      setForgetting(false);
    }, notRecorded ? 'Purges recorded as not remembered.' : 'Purges recorded.');

  const handleReport = () => {
    if (!winner) return;
    const wk = parseInt(winnerKeys, 10) || 0;
    const lk = parseInt(loserKeys, 10) || 0;
    return run(async () => {
      await reportGame(leagueId, pm.id, {
        game_number: nextGame,
        winner_id: winner,
        player1_keys: winner === pm.player1.id ? wk : lk,
        player2_keys: winner === pm.player2.id ? wk : lk,
      });
      setWinner('');
    }, 'Game reported.');
  };

  return (
    <>
      {unverified && (
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 1 }}>
          <Chip label="Needs verifying" size="small" variant="outlined" color="warning" />
          <Button size="small" variant="outlined" color="success" disabled={busy} onClick={handleVerify}>
            Verify
          </Button>
        </Box>
      )}

      {!decided && needsStart && (
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Typography variant="body2" color="text.secondary">
            Not started on the site, so the result cannot be entered yet.
          </Typography>
          <Button size="small" variant="outlined" disabled={busy} onClick={() => setAlreadyPlayedOpen(true)}>
            We already played
          </Button>
        </Box>
      )}

      {!decided && needsPurges && (
        <Box sx={{ mt: 1, p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom>
            House purges &mdash; Game {nextGame}
          </Typography>
          {canNameHouses ? (
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
              <FormControl size="small" sx={{ minWidth: 190 }}>
                <InputLabel>{`${mine.name} purged`}</InputLabel>
                <Select
                  label={`${mine.name} purged`}
                  value={purgeMine}
                  onChange={(e) => setPurgeMine(e.target.value as string)}
                >
                  {housesTheyCanTake.map((h) => (
                    <MenuItem key={h} value={h}>{h}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 190 }}>
                <InputLabel>{`${theirs.name} purged`}</InputLabel>
                <Select
                  label={`${theirs.name} purged`}
                  value={purgeTheirs}
                  onChange={(e) => setPurgeTheirs(e.target.value as string)}
                >
                  {housesTakenFromMine.map((h) => (
                    <MenuItem key={h} value={h}>{h}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Button
                size="small"
                variant="contained"
                disabled={busy || !purgeMine || !purgeTheirs}
                onClick={() => handleRetroPurge(false)}
              >
                Save purges
              </Button>
            </Box>
          ) : (
            <Typography variant="body2" color="text.secondary">
              One of the decks is not visible to you, so the houses cannot be picked here.
              The players can enter them from the week tab, or you can record them as not
              remembered.
            </Typography>
          )}
          {forgetting ? (
            <Box sx={{ mt: 1 }}>
              <Typography variant="body2">
                This records Game {nextGame} as <strong>not remembered</strong> for both
                players, rather than guessing at the houses.
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
                <Button size="small" onClick={() => setForgetting(false)} disabled={busy}>
                  Back
                </Button>
                <Button
                  size="small"
                  variant="contained"
                  color="warning"
                  disabled={busy}
                  onClick={() => handleRetroPurge(true)}
                >
                  Confirm: not remembered
                </Button>
              </Box>
            </Box>
          ) : (
            <Button size="small" color="warning" sx={{ mt: 1 }} onClick={() => setForgetting(true)}>
              We do not remember the purges
            </Button>
          )}
        </Box>
      )}

      {!decided && !needsStart && !needsPurges && NEEDS_DECK_PER_GAME.has(week.format_type) && (
        <Typography variant="body2" color="text.secondary">
          {week.format_type === 'triad' ? 'Triad' : 'This format'} records which deck each
          player used, so the game has to be reported from the player&apos;s own match page.
        </Typography>
      )}

      {!decided && !needsStart && !needsPurges && !NEEDS_DECK_PER_GAME.has(week.format_type) && (
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>{`Game ${nextGame} winner`}</InputLabel>
            <Select
              label={`Game ${nextGame} winner`}
              value={winner}
              onChange={(e) => setWinner(e.target.value as number)}
            >
              <MenuItem value={mine.id}>{mine.name}</MenuItem>
              <MenuItem value={theirs.id}>{theirs.name}</MenuItem>
            </Select>
          </FormControl>
          <TextField
            size="small"
            label="Winner keys"
            type="number"
            sx={{ width: 110 }}
            value={winnerKeys}
            onChange={(e) => setWinnerKeys(e.target.value)}
          />
          <TextField
            size="small"
            label="Loser keys"
            type="number"
            sx={{ width: 110 }}
            value={loserKeys}
            onChange={(e) => setLoserKeys(e.target.value)}
          />
          <Button size="small" variant="contained" disabled={busy || !winner} onClick={handleReport}>
            Report
          </Button>
        </Box>
      )}

      <Dialog
        open={alreadyPlayedOpen}
        onClose={() => setAlreadyPlayedOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Record this match as already played?</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            Only do this if the match really was played.
          </Alert>
          <Typography variant="body2">
            {`${mine.name} vs ${theirs.name} will be started for both players, so the result can be entered. This skips the deck reveal and any pre-game choices the format normally runs through on the site.`}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            It is recorded in the league admin log, with your name against it.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAlreadyPlayedOpen(false)}>Cancel</Button>
          <Button variant="contained" disabled={busy} onClick={handleAlreadyPlayed}>
            Continue
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
