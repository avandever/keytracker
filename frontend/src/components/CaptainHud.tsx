import { Alert, Box, Chip, Paper, Typography, alpha } from '@mui/material';
import type { LeagueWeek, TeamDetail } from '../types';
import { deckSlotsForFormat } from '../utils/deckSlots';
import { formatDeadline, isPast } from '../utils/deadlines';

interface Props {
  week: LeagueWeek;
  myTeam: TeamDetail;
}

/** Formats where both players press Start before anything else can happen. */
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
 * What a captain has to chase this week, in one place.
 *
 * All of it is already on the page somewhere -- spread across eleven player
 * rows, the matchup list and the Outstanding tab. A captain checking whether
 * their team is ready should not have to assemble it themselves.
 */
export default function CaptainHud({ week, myTeam }: Props) {
  const memberIds = new Set(myTeam.members.map((m) => m.user.id));
  const slots = deckSlotsForFormat(week.format_type);

  const selectionsFor = (userId: number) =>
    (week.deck_selections || []).filter((ds) => ds.user_id === userId).length;
  const missingDecks = myTeam.members.filter((m) => selectionsFor(m.user.id) < slots);
  // Counted per slot, not per player: in a two-deck format someone who has
  // entered one of their two is half done, not nothing.
  const decksExpected = myTeam.members.length * slots;
  const decksIn = myTeam.members.reduce(
    (total, m) => total + Math.min(selectionsFor(m.user.id), slots),
    0,
  );

  const winsNeeded = Math.ceil(week.best_of_n / 2);
  const mine = (week.matchups || []).filter(
    (wm) => wm.team1.id === myTeam.id || wm.team2.id === myTeam.id,
  );
  const pms = mine.flatMap((wm) => wm.player_matchups);

  const verified: typeof pms = [];
  const unverified: typeof pms = [];
  const inProgress: typeof pms = [];
  const notPlayed: typeof pms = [];
  const notStarted: typeof pms = [];
  for (const pm of pms) {
    if (pm.is_double_loss) {
      verified.push(pm);
      continue;
    }
    const p1 = pm.games.filter((g) => g.winner_id === pm.player1.id).length;
    const p2 = pm.games.filter((g) => g.winner_id === pm.player2.id).length;
    const decided = p1 >= winsNeeded || p2 >= winsNeeded;
    if (decided && pm.result_confirmed) verified.push(pm);
    else if (decided) unverified.push(pm);
    else if (pm.games.length > 0) inProgress.push(pm);
    else notPlayed.push(pm);
    if (
      !decided &&
      NEEDS_START.has(week.format_type) &&
      !(pm.player1_started && pm.player2_started)
    ) {
      notStarted.push(pm);
    }
  }

  const ourName = (pm: (typeof pms)[number]) =>
    memberIds.has(pm.player1.id) ? pm.player1.name : pm.player2.name;
  const theirName = (pm: (typeof pms)[number]) =>
    memberIds.has(pm.player1.id) ? pm.player2.name : pm.player1.name;

  const subs = (week.substitutions || []).filter((s) => s.team_id === myTeam.id);
  const deckDeadline = week.deck_submission_deadline;
  const matchDeadline = week.match_completion_deadline;

  const nothingToDo =
    missingDecks.length === 0 && unverified.length === 0 && notPlayed.length === 0 &&
    inProgress.length === 0;

  return (
    <Paper
      variant="outlined"
      sx={(theme) => ({
        mb: 2,
        p: 1.5,
        bgcolor: alpha(theme.palette.primary.main, 0.04),
      })}
    >
      <Typography variant="subtitle2" gutterBottom>
        Captain&apos;s summary
      </Typography>

      {(deckDeadline || matchDeadline) && (
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
          {deckDeadline && (
            <Chip
              size="small"
              color={isPast(deckDeadline) ? 'error' : 'default'}
              variant={isPast(deckDeadline) ? 'filled' : 'outlined'}
              label={`Decks due ${formatDeadline(deckDeadline)}`}
            />
          )}
          {matchDeadline && (
            <Chip
              size="small"
              color={isPast(matchDeadline) ? 'error' : 'default'}
              variant={isPast(matchDeadline) ? 'filled' : 'outlined'}
              label={`Matches due ${formatDeadline(matchDeadline)}`}
            />
          )}
        </Box>
      )}

      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: missingDecks.length || notPlayed.length || unverified.length ? 1 : 0 }}>
        <Chip
          size="small"
          label={`Decks ${decksIn}/${decksExpected}`}
          color={missingDecks.length ? 'warning' : 'success'}
        />
        {pms.length > 0 && (
          <>
            <Chip size="small" label={`Verified ${verified.length}`} color={verified.length === pms.length ? 'success' : 'default'} />
            {unverified.length > 0 && <Chip size="small" color="warning" label={`Unverified ${unverified.length}`} />}
            {inProgress.length > 0 && <Chip size="small" label={`In progress ${inProgress.length}`} />}
            {notPlayed.length > 0 && <Chip size="small" label={`Not played ${notPlayed.length}`} />}
          </>
        )}
        {subs.length > 0 && <Chip size="small" color="info" label={`Subs ${subs.length}`} />}
      </Box>

      {missingDecks.length > 0 && (
        <Typography variant="body2" color="text.secondary">
          <strong>No deck yet:</strong> {missingDecks.map((m) => m.user.name).join(', ')}
        </Typography>
      )}

      {unverified.length > 0 && (
        <Typography variant="body2" color="text.secondary">
          <strong>Waiting on your verification:</strong>{' '}
          {unverified.map((pm) => `${ourName(pm)} v ${theirName(pm)}`).join(', ')}
        </Typography>
      )}

      {notPlayed.length > 0 && (
        <Typography variant="body2" color="text.secondary">
          <strong>No result yet:</strong>{' '}
          {notPlayed.map((pm) => `${ourName(pm)} v ${theirName(pm)}`).join(', ')}
        </Typography>
      )}

      {notStarted.length > 0 && (
        <Typography variant="body2" color="text.secondary">
          <strong>Not started on the site:</strong> {notStarted.length} of {pms.length}
          {' '}— these cannot be reported until both players start, or someone records the
          match as already played.
        </Typography>
      )}

      {subs.length > 0 && (
        <Typography variant="body2" color="text.secondary">
          <strong>Covering:</strong>{' '}
          {subs.map((s) => `${s.in_user.name} for ${s.out_user.name}`).join(', ')}
        </Typography>
      )}

      {nothingToDo && pms.length > 0 && (
        <Alert severity="success" sx={{ mt: 1, py: 0 }}>
          Nothing outstanding for this week.
        </Alert>
      )}
    </Paper>
  );
}
