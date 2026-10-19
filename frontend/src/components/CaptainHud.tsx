import { Alert, Box, Chip, Paper, Typography, alpha } from '@mui/material';
import type { LeagueWeek, TeamDetail } from '../types';
import { ALLIANCE_FORMATS, deckSlotsForFormat } from '../utils/deckSlots';
import { formatDeadline, isPast } from '../utils/deadlines';

type Members = TeamDetail['members'];

interface Props {
  /**
   * The weeks this summary covers.
   *
   * One for an ordinary week. A playoff round passes every bracket in it: the
   * deadlines belong to the round, and a captain chasing eleven brackets wants
   * one list of what is outstanding, not the same card eleven times.
   */
  weeks: LeagueWeek[];
  myTeam: TeamDetail;
  /**
   * Who from the team plays a given week. Defaults to the whole roster, which
   * is every week except a playoff bracket, where one player plays.
   */
  membersFor?: (week: LeagueWeek) => Members;
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

/** What to call a week when several are listed together. */
const weekLabel = (week: LeagueWeek) =>
  week.playoff_bracket_name || week.name || `Week ${week.week_number}`;

/**
 * What a captain has to chase, in one place.
 *
 * All of it is already on the page somewhere -- spread across eleven player
 * rows, the matchup list and the Outstanding tab. A captain checking whether
 * their team is ready should not have to assemble it themselves.
 */
export default function CaptainHud({ weeks, myTeam, membersFor }: Props) {
  const memberIds = new Set(myTeam.members.map((m) => m.user.id));
  const many = weeks.length > 1;
  const playing = (week: LeagueWeek): Members => membersFor?.(week) ?? myTeam.members;

  // An alliance is one deck built from three pods and files no deck
  // selection, so counting those alone read a finished alliance as nothing.
  const selectionsFor = (week: LeagueWeek, userId: number) => {
    if (ALLIANCE_FORMATS.includes(week.format_type)) {
      const pods = (week.alliance_selections || []).filter(
        (s) => s.user_id === userId && s.slot_type === 'pod',
      ).length;
      return pods >= 3 ? deckSlotsForFormat(week.format_type) : 0;
    }
    return (week.deck_selections || []).filter((ds) => ds.user_id === userId).length;
  };

  // Counted per slot, not per player: in a two-deck format someone who has
  // entered one of their two is half done, not nothing.
  let decksExpected = 0;
  let decksIn = 0;
  const missingDecks: { week: LeagueWeek; name: string }[] = [];
  for (const week of weeks) {
    const slots = deckSlotsForFormat(week.format_type);
    for (const m of playing(week)) {
      const entered = selectionsFor(week, m.user.id);
      decksExpected += slots;
      decksIn += Math.min(entered, slots);
      if (entered < slots) missingDecks.push({ week, name: m.user.name });
    }
  }

  type Pm = LeagueWeek['matchups'][number]['player_matchups'][number];
  const verified: Pm[] = [];
  const unverified: { week: LeagueWeek; pm: Pm }[] = [];
  const inProgress: { week: LeagueWeek; pm: Pm }[] = [];
  const notPlayed: { week: LeagueWeek; pm: Pm }[] = [];
  const notStarted: Pm[] = [];
  let total = 0;

  for (const week of weeks) {
    const winsNeeded = Math.ceil(week.best_of_n / 2);
    const mine = (week.matchups || []).filter(
      (wm) => wm.team1.id === myTeam.id || wm.team2.id === myTeam.id,
    );
    for (const pm of mine.flatMap((wm) => wm.player_matchups)) {
      total += 1;
      if (pm.is_double_loss) {
        verified.push(pm);
        continue;
      }
      const p1 = pm.games.filter((g) => g.winner_id === pm.player1.id).length;
      const p2 = pm.games.filter((g) => g.winner_id === pm.player2.id).length;
      const decided = p1 >= winsNeeded || p2 >= winsNeeded;
      if (decided && pm.result_confirmed) verified.push(pm);
      else if (decided) unverified.push({ week, pm });
      else if (pm.games.length > 0) inProgress.push({ week, pm });
      else notPlayed.push({ week, pm });
      if (
        !decided &&
        NEEDS_START.has(week.format_type) &&
        !(pm.player1_started && pm.player2_started)
      ) {
        notStarted.push(pm);
      }
    }
  }

  const ourName = (pm: Pm) =>
    memberIds.has(pm.player1.id) ? pm.player1.name : pm.player2.name;
  const theirName = (pm: Pm) =>
    memberIds.has(pm.player1.id) ? pm.player2.name : pm.player1.name;
  // A bracket name earns its place only when several are listed at once.
  const versus = ({ week, pm }: { week: LeagueWeek; pm: Pm }) =>
    `${many ? `${weekLabel(week)}: ` : ''}${ourName(pm)} v ${theirName(pm)}`;

  const subs = weeks.flatMap((week) =>
    (week.substitutions || [])
      .filter((s) => s.team_id === myTeam.id)
      .map((s) => ({ week, sub: s })),
  );

  // The deadlines belong to the round, so every week in one carries the same
  // pair; the first to name either settles it.
  const deckDeadline = weeks.find((w) => w.deck_submission_deadline)?.deck_submission_deadline;
  const matchDeadline = weeks.find((w) => w.match_completion_deadline)?.match_completion_deadline;

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
        {total > 0 && (
          <>
            <Chip size="small" label={`Verified ${verified.length}`} color={verified.length === total ? 'success' : 'default'} />
            {unverified.length > 0 && <Chip size="small" color="warning" label={`Unverified ${unverified.length}`} />}
            {inProgress.length > 0 && <Chip size="small" label={`In progress ${inProgress.length}`} />}
            {notPlayed.length > 0 && <Chip size="small" label={`Not played ${notPlayed.length}`} />}
          </>
        )}
        {subs.length > 0 && <Chip size="small" color="info" label={`Subs ${subs.length}`} />}
      </Box>

      {missingDecks.length > 0 && (
        <Typography variant="body2" color="text.secondary">
          <strong>No deck yet:</strong>{' '}
          {missingDecks
            .map((m) => (many ? `${weekLabel(m.week)}: ${m.name}` : m.name))
            .join(', ')}
        </Typography>
      )}

      {unverified.length > 0 && (
        <Typography variant="body2" color="text.secondary">
          <strong>Waiting on your verification:</strong>{' '}
          {unverified.map(versus).join(', ')}
        </Typography>
      )}

      {notPlayed.length > 0 && (
        <Typography variant="body2" color="text.secondary">
          <strong>No result yet:</strong> {notPlayed.map(versus).join(', ')}
        </Typography>
      )}

      {notStarted.length > 0 && (
        <Typography variant="body2" color="text.secondary">
          <strong>Not started on the site:</strong> {notStarted.length} of {total}
          {' '}— these cannot be reported until both players start, or someone records the
          match as already played.
        </Typography>
      )}

      {subs.length > 0 && (
        <Typography variant="body2" color="text.secondary">
          <strong>Covering:</strong>{' '}
          {subs
            .map(({ week, sub }) =>
              `${many ? `${weekLabel(week)}: ` : ''}${sub.in_user.name} for ${sub.out_user.name}`,
            )
            .join(', ')}
        </Typography>
      )}

      {nothingToDo && total > 0 && (
        <Alert severity="success" sx={{ mt: 1, py: 0 }}>
          Nothing outstanding for this {many ? 'round' : 'week'}.
        </Alert>
      )}
    </Paper>
  );
}
