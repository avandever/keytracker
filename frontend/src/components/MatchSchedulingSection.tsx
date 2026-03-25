import { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Chip,
  Alert,
  Divider,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import type { PlayerMatchupInfo } from '../types';
import {
  proposeScheduleTimes,
  clearScheduleProposals,
  confirmScheduleTime,
  clearScheduleConfirmation,
} from '../api/leagues';

interface Props {
  leagueId: number;
  pm: PlayerMatchupInfo;
  myUserId: number;
  /** Called with the updated matchup after a successful API action. */
  onUpdate: (updated: PlayerMatchupInfo) => void;
}

function formatTime(isoUtc: string): string {
  return new Date(isoUtc).toLocaleString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  });
}

export default function MatchSchedulingSection({ leagueId, pm, myUserId, onUpdate }: Props) {
  const [pickerValue, setPickerValue] = useState('');
  const [pendingTimes, setPendingTimes] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState('');

  const opponentId = pm.player1.id === myUserId ? pm.player2.id : pm.player1.id;
  const opponent = pm.player1.id === myUserId ? pm.player2 : pm.player1;

  const confirmedTime = pm.schedule_confirmed_time ?? null;
  const myProposals = (pm.schedule_proposals ?? []).find((p) => p.user_id === myUserId);
  const opponentProposals = (pm.schedule_proposals ?? []).find((p) => p.user_id === opponentId);

  async function doAction(fn: () => Promise<PlayerMatchupInfo>) {
    setBusy(true);
    setLocalError('');
    try {
      const updated = await fn();
      onUpdate(updated);
    } catch (e: any) {
      setLocalError(e.response?.data?.error || e.message);
    } finally {
      setBusy(false);
    }
  }

  function addPending() {
    if (!pickerValue) return;
    const iso = new Date(pickerValue).toISOString();
    if (!pendingTimes.includes(iso)) {
      setPendingTimes((prev) => [...prev, iso]);
    }
    setPickerValue('');
  }

  function removePending(iso: string) {
    setPendingTimes((prev) => prev.filter((t) => t !== iso));
  }

  async function submitProposals() {
    if (!pendingTimes.length) return;
    await doAction(() => proposeScheduleTimes(leagueId, pm.id, pendingTimes));
    setPendingTimes([]);
  }

  // --- Confirmed state ---
  if (confirmedTime) {
    return (
      <Box sx={{ mt: 2 }}>
        <Divider sx={{ mb: 1.5 }} />
        <Typography variant="subtitle2" gutterBottom>
          Scheduled Match Time
        </Typography>
        <Alert
          severity="success"
          action={
            <Button
              size="small"
              color="inherit"
              disabled={busy}
              onClick={() => doAction(() => clearScheduleConfirmation(leagueId, pm.id))}
            >
              Clear
            </Button>
          }
        >
          {formatTime(confirmedTime)}
        </Alert>
        {localError && <Typography color="error" variant="caption">{localError}</Typography>}
      </Box>
    );
  }

  // --- Scheduling UI ---
  return (
    <Box sx={{ mt: 2 }}>
      <Divider sx={{ mb: 1.5 }} />
      <Typography variant="subtitle2" gutterBottom>
        Schedule Match
      </Typography>

      {localError && (
        <Typography color="error" variant="caption" display="block" sx={{ mb: 1 }}>
          {localError}
        </Typography>
      )}

      {/* My proposals */}
      <Typography variant="body2" color="text.secondary" gutterBottom>
        My proposed times:
      </Typography>
      {myProposals?.times.length ? (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
          {myProposals.times.map((t) => (
            <Chip key={t} label={formatTime(t)} size="small" />
          ))}
          <Button
            size="small"
            color="error"
            disabled={busy}
            onClick={() => doAction(() => clearScheduleProposals(leagueId, pm.id))}
          >
            Clear
          </Button>
        </Box>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          (None yet)
        </Typography>
      )}

      {/* Add times */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5, flexWrap: 'wrap' }}>
        <input
          type="datetime-local"
          value={pickerValue}
          onChange={(e) => setPickerValue(e.target.value)}
          style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid #ccc' }}
        />
        <Button size="small" variant="outlined" onClick={addPending} disabled={!pickerValue}>
          Add
        </Button>
      </Box>
      {pendingTimes.length > 0 && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
          {pendingTimes.map((t) => (
            <Chip
              key={t}
              label={formatTime(t)}
              size="small"
              onDelete={() => removePending(t)}
              sx={(theme) => ({ bgcolor: alpha(theme.palette.primary.main, 0.1) })}
            />
          ))}
          <Button
            size="small"
            variant="contained"
            disabled={busy || !pendingTimes.length}
            onClick={submitProposals}
          >
            Submit
          </Button>
        </Box>
      )}

      {/* Opponent proposals */}
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }} gutterBottom>
        {opponent.name}&apos;s proposed times:
      </Typography>
      {opponentProposals?.times.length ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          {opponentProposals.times.map((t) => (
            <Box key={t} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2">{formatTime(t)}</Typography>
              <Button
                size="small"
                variant="outlined"
                color="success"
                disabled={busy}
                onClick={() => doAction(() => confirmScheduleTime(leagueId, pm.id, t))}
              >
                Confirm
              </Button>
            </Box>
          ))}
        </Box>
      ) : (
        <Typography variant="body2" color="text.secondary">
          (None yet)
        </Typography>
      )}
    </Box>
  );
}
