import { Chip } from '@mui/material';
import type { KeyforgeSetInfo, LeagueWeek } from '../types';
import { formatDeadline, isPast } from '../utils/deadlines';

interface WeekConstraintsProps {
  week: LeagueWeek;
  size?: 'small' | 'medium';
  sets?: KeyforgeSetInfo[];
}

export default function WeekConstraints({ week, size = 'small', sets }: WeekConstraintsProps) {
  const chips: React.ReactNode[] = [];

  if (week.allowed_sets && week.allowed_sets.length > 0) {
    const setMap = new Map((sets || []).map((s) => [s.number, s.shortname]));
    const labels = week.allowed_sets.map((n) => setMap.get(n)).filter((name): name is string => name != null);
    if (labels.length > 0) {
      chips.push(<Chip key="allowed-sets" label={`Sets: ${labels.join(', ')}`} size={size} variant="outlined" color="secondary" />);
    }
  }
  if (week.max_sas) {
    chips.push(<Chip key="max-sas" label={`Max SAS: ${week.max_sas}`} size={size} variant="outlined" />);
  }
  if (week.sas_floor) {
    chips.push(<Chip key="sas-floor" label={`SAS Floor: ${week.sas_floor}`} size={size} variant="outlined" />);
  }
  if (week.combined_max_sas) {
    chips.push(<Chip key="combined-sas" label={`Combined Max SAS: ${week.combined_max_sas}`} size={size} variant="outlined" />);
  }
  if (week.set_diversity) {
    chips.push(<Chip key="set-div" label="Set Diversity" size={size} variant="outlined" color="info" />);
  }
  if (week.house_diversity) {
    chips.push(<Chip key="house-div" label="House Diversity" size={size} variant="outlined" color="info" />);
  }
  if (week.no_keycheat) {
    chips.push(<Chip key="no-keycheat" label="No Keycheat" size={size} variant="outlined" color="error" />);
  }
  if (week.team_max_raw_amber != null) {
    chips.push(<Chip key="team-max-amber" label={`Team Max Aember: ${week.team_max_raw_amber}`} size={size} variant="outlined" />);
  }
  if (week.team_min_raw_amber != null) {
    chips.push(<Chip key="team-min-amber" label={`Team Min Aember: ${week.team_min_raw_amber}`} size={size} variant="outlined" />);
  }
  // Deadlines are advisory, so a passed one is coloured but never blocking.
  if (week.deck_submission_deadline) {
    chips.push(
      <Chip
        key="deck-deadline"
        label={`Decks due: ${formatDeadline(week.deck_submission_deadline)}`}
        size={size}
        variant="outlined"
        color={isPast(week.deck_submission_deadline) ? 'error' : 'warning'}
      />,
    );
  }
  if (week.match_completion_deadline) {
    chips.push(
      <Chip
        key="match-deadline"
        label={`Matches due: ${formatDeadline(week.match_completion_deadline)}`}
        size={size}
        variant="outlined"
        color={isPast(week.match_completion_deadline) ? 'error' : 'warning'}
      />,
    );
  }
  const requiredCount =
    (week.required_card_names?.length ?? 0) + (week.required_card_categories?.length ?? 0);
  if (requiredCount > 0) {
    // Categories describe themselves, so spell them out rather than making a
    // player guess what "3 required" means.
    const parts = [
      ...(week.required_card_names ?? []),
      ...(week.required_card_categories ?? []).map(
        (c) =>
          c.label ||
          [c.rarities, c.traits, c.card_types, c.card_titles]
            .filter((v): v is string[] => !!v && v.length > 0)
            .map((v) => v.slice(0, 3).join('/') + (v.length > 3 ? '…' : ''))
            .join(' ') ||
          'any card',
      ),
    ];
    chips.push(
      <Chip
        key="required-cards"
        label={`Required: ${parts.join(' / ')}`}
        size={size}
        variant="outlined"
        color="info"
        // A chip keeps its label on one line, and this one can list fifteen
        // cards, so it runs off the edge of the card it sits on. Let it grow
        // downwards instead of sideways.
        sx={{
          height: 'auto',
          maxWidth: '100%',
          '& .MuiChip-label': {
            display: 'block',
            whiteSpace: 'normal',
            overflowWrap: 'anywhere',
            py: 0.5,
          },
        }}
      />,
    );
  }
  if (week.format_type === 'sas_ladder' && week.sas_ladder_maxes && week.sas_ladder_maxes.length > 0) {
    const numRungs = week.sas_ladder_maxes.length + 1;
    chips.push(<Chip key="sas-ladder" label={`SAS Ladder: ${numRungs} rungs`} size={size} variant="outlined" color="secondary" />);
    if (week.sas_ladder_feature_rung != null && week.feature_match_applies) {
      chips.push(<Chip key="feature-rung" label={`Feature: Rung ${week.sas_ladder_feature_rung}`} size={size} variant="outlined" />);
    }
  }

  if (chips.length === 0) return null;

  return <>{chips}</>;
}

export function CombinedSas({ selections }: { selections: { deck?: { sas_rating?: number | null } | null }[] }) {
  const ratings = selections
    .map((s) => s.deck?.sas_rating)
    .filter((r): r is number => r != null);
  if (ratings.length < 2) return null;
  const total = ratings.reduce((a, b) => a + b, 0);
  return <Chip label={`Combined SAS: ${total}`} size="small" variant="outlined" />;
}
