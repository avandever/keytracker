import { Chip } from '@mui/material';
import type { KeyforgeSetInfo, LeagueWeek } from '../types';

interface WeekConstraintsProps {
  week: LeagueWeek;
  size?: 'small' | 'medium';
  sets?: KeyforgeSetInfo[];
}

export default function WeekConstraints({ week, size = 'small', sets }: WeekConstraintsProps) {
  const chips: React.ReactNode[] = [];

  if (week.allowed_sets && week.allowed_sets.length > 0) {
    const setMap = new Map((sets || []).map((s) => [s.number, s.shortname]));
    const labels = week.allowed_sets.map((n) => setMap.get(n) ?? String(n));
    chips.push(<Chip key="allowed-sets" label={`Sets: ${labels.join(', ')}`} size={size} variant="outlined" color="secondary" />);
  }
  if (week.max_sas) {
    chips.push(<Chip key="max-sas" label={`Max SAS: ${week.max_sas}`} size={size} variant="outlined" />);
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
