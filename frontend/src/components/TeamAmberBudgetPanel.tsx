import { Box, Chip, LinearProgress, Typography } from '@mui/material';
import type { TeamAmberBudget } from '../types';

/**
 * Shows a team's raw aember spend against the week's cap.
 *
 * The cap is enforced only when a deck is submitted, so without this the first
 * sign of trouble is a rejected submission. Showing the running total lets a
 * team plan who spends what before anyone is blocked.
 */
export default function TeamAmberBudgetPanel({ budget }: { budget: TeamAmberBudget }) {
  const { claimed, remaining, max_raw_amber, min_raw_amber, unknown_decks, members } = budget;
  const over = max_raw_amber != null && claimed > max_raw_amber;
  const pct = max_raw_amber ? Math.min(100, (claimed / max_raw_amber) * 100) : 0;
  // The floor only matters once the team has finished picking, so it is shown
  // as a target rather than an error.
  const belowMin = min_raw_amber != null && claimed < min_raw_amber;

  return (
    <Box sx={{ mb: 2, p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 1 }}>
        <Typography variant="subtitle2">Team Raw Aember</Typography>
        <Typography variant="body2" color="text.secondary">
          {claimed} claimed
          {max_raw_amber != null && ` of ${max_raw_amber}`}
          {remaining != null && ` — ${remaining} left`}
        </Typography>
        {over && <Chip label="Over cap" size="small" color="error" />}
        {belowMin && (
          <Chip label={`Needs ${min_raw_amber - claimed} more`} size="small" color="warning" variant="outlined" />
        )}
      </Box>

      {max_raw_amber != null && (
        <LinearProgress
          variant="determinate"
          value={pct}
          color={over ? 'error' : 'primary'}
          sx={{ mb: 1, height: 6, borderRadius: 3 }}
        />
      )}

      {unknown_decks > 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
          {unknown_decks} selected deck{unknown_decks !== 1 ? 's have' : ' has'} no DoK data yet and
          {unknown_decks !== 1 ? ' are' : ' is'} not counted — the real total may be higher.
        </Typography>
      )}

      {members.map((m) => (
        <Box key={m.user_id} sx={{ display: 'flex', gap: 1, alignItems: 'baseline', flexWrap: 'wrap' }}>
          <Typography variant="body2" sx={{ minWidth: 140 }}>
            {m.name ?? `User ${m.user_id}`}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {m.decks.length === 0
              ? 'no deck submitted'
              : m.decks
                  .map((d) => `${d.deck_name ?? 'Unknown'} (${d.raw_amber ?? '?'})`)
                  .join(', ')}
          </Typography>
          {m.decks.length > 0 && (
            <Typography variant="body2" sx={{ ml: 'auto', fontWeight: 500 }}>
              {m.subtotal}
            </Typography>
          )}
        </Box>
      ))}
    </Box>
  );
}
