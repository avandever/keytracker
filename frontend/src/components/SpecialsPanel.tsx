import { Box, Chip, Paper, Tooltip, Typography, alpha } from '@mui/material';
import type { RequiredCardUsage } from '../types';

/**
 * The week's required cards as a shared pool.
 *
 * Each named card, and each category, can be used by one player on the team,
 * so every deck submitted takes something off the table. Working that out
 * meant opening each teammate's deck in turn and ticking cards off by hand.
 */
export default function SpecialsPanel({ usage }: { usage: RequiredCardUsage }) {
  const items = usage.items || [];
  if (items.length === 0) return null;
  const taken = items.filter((i) => i.claimed_by);
  const available = items.filter((i) => !i.claimed_by);

  return (
    <Paper
      variant="outlined"
      sx={(theme) => ({ mb: 2, p: 1.5, bgcolor: alpha(theme.palette.info.main, 0.04) })}
    >
      <Typography variant="subtitle2" gutterBottom>
        Required cards: {available.length} of {items.length} still available
      </Typography>

      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: taken.length ? 1 : 0 }}>
        {available.map((item) => (
          <Chip
            key={item.key}
            size="small"
            color="success"
            variant="outlined"
            label={item.label}
          />
        ))}
        {available.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            Every required card is spoken for.
          </Typography>
        )}
      </Box>

      {taken.length > 0 && (
        <>
          <Typography variant="caption" color="text.secondary">
            Already claimed:
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
            {taken.map((item) => (
              <Tooltip
                key={item.key}
                title={`${item.claimed_by!.name}${item.deck_name ? ` — ${item.deck_name}` : ''}`}
              >
                <Chip
                  size="small"
                  variant="filled"
                  label={`${item.label} · ${item.claimed_by!.name}`}
                  sx={{ opacity: 0.75 }}
                />
              </Tooltip>
            ))}
          </Box>
        </>
      )}
    </Paper>
  );
}
