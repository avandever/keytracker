import { useEffect, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Container,
  Divider,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  OutlinedInput,
  Paper,
  Select,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import { Link as RouterLink } from 'react-router-dom';
import { podSearch } from '../api/decks';
import { getSets } from '../api/leagues';
import type {
  KeyforgeSetInfo,
  PodSearchCardFilter,
  PodSearchResponse,
} from '../types';

const HOUSES = [
  'Brobnar',
  'Dis',
  'Ekwidon',
  'Geistoid',
  'Logos',
  'Mars',
  'Sanctum',
  'Saurian',
  'Shadows',
  'Star Alliance',
  'Unfathomable',
  'Untamed',
];

const PIP_TYPES = [
  { key: 'amber', label: 'Æmber' },
  { key: 'capture', label: 'Capture' },
  { key: 'draw', label: 'Draw' },
  { key: 'damage', label: 'Damage' },
  { key: 'discard', label: 'Discard' },
  { key: 'power', label: 'Power' },
];

const POD_RANGES = [
  { key: 'sas_rating', label: 'Pod SAS' },
  { key: 'aerc_score', label: 'Pod AERC' },
  { key: 'num_enhancements', label: 'Enhancements' },
  { key: 'creatures', label: 'Creatures' },
  { key: 'raw_amber', label: 'Raw Æmber' },
  { key: 'total_amber', label: 'Total Æmber' },
];

// Deck SAS/AERC come off the Deck row; the lettered values come from DoK.
const DECK_RANGES = [
  { key: 'sas_rating', label: 'Deck SAS' },
  { key: 'aerc_score', label: 'Deck AERC' },
  { key: 'expected_amber', label: 'E — Expected Æmber' },
  { key: 'amber_control', label: 'A — Æmber Control' },
  { key: 'artifact_control', label: 'R — Artifact Control' },
  { key: 'creature_control', label: 'C — Creature Control' },
  { key: 'efficiency', label: 'F — Efficiency' },
  { key: 'disruption', label: 'D — Disruption' },
  { key: 'creature_protection', label: 'P — Creature Protection' },
  { key: 'effective_power', label: 'Effective Power' },
];

const SORTS = [
  { key: 'pod_sas', label: 'Pod SAS' },
  { key: 'pod_aerc', label: 'Pod AERC' },
  { key: 'pod_enhancements', label: 'Pod enhancements' },
  { key: 'pod_creatures', label: 'Pod creatures' },
  { key: 'pod_total_amber', label: 'Pod total æmber' },
  { key: 'deck_sas', label: 'Deck SAS' },
  { key: 'deck_aerc', label: 'Deck AERC' },
  { key: 'deck_expected_amber', label: 'Deck E' },
  { key: 'deck_amber_control', label: 'Deck A' },
  { key: 'deck_creature_control', label: 'Deck C' },
  { key: 'deck_efficiency', label: 'Deck F' },
  { key: 'deck_name', label: 'Deck name' },
];

interface PipRow {
  pip: string;
  min: string;
  max: string;
}

interface CardRow {
  id: number;
  cardName: string;
  minCount: string;
  pips: PipRow[];
  isEnhanced: string;
  isMaverick: string;
  isAnomaly: string;
}

let nextRowId = 1;

function emptyCardRow(): CardRow {
  return {
    id: nextRowId++,
    cardName: '',
    minCount: '1',
    pips: [{ pip: 'damage', min: '', max: '' }],
    isEnhanced: '',
    isMaverick: '',
    isAnomaly: '',
  };
}

function numberOrUndefined(value: string): number | undefined {
  if (value.trim() === '') return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function triStateToBool(value: string): boolean | undefined {
  if (value === 'yes') return true;
  if (value === 'no') return false;
  return undefined;
}

/** Collect <field>_min / <field>_max pairs, dropping blanks. */
function rangePayload(values: Record<string, string>, keys: string[]) {
  const out: Record<string, number> = {};
  keys.forEach((key) => {
    const min = numberOrUndefined(values[`${key}_min`] ?? '');
    if (min !== undefined) out[`${key}_min`] = min;
    const max = numberOrUndefined(values[`${key}_max`] ?? '');
    if (max !== undefined) out[`${key}_max`] = max;
  });
  return out;
}

function fmt(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined) return '-';
  return Number.isInteger(value) ? String(value) : value.toFixed(digits);
}

export default function PodSearchPage() {
  const [scope, setScope] = useState<'collection' | 'all'>('collection');
  const [cardRows, setCardRows] = useState<CardRow[]>([emptyCardRow()]);
  const [podValues, setPodValues] = useState<Record<string, string>>({});
  const [deckValues, setDeckValues] = useState<Record<string, string>>({});
  const [houses, setHouses] = useState<string[]>([]);
  const [expansions, setExpansions] = useState<number[]>([]);
  const [deckName, setDeckName] = useState('');
  const [sort, setSort] = useState('pod_sas');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [perPage, setPerPage] = useState(25);
  const [includeTotal, setIncludeTotal] = useState(false);
  const [sets, setSets] = useState<KeyforgeSetInfo[]>([]);

  const [result, setResult] = useState<PodSearchResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getSets().then(setSets).catch(() => {});
  }, []);

  const updateCardRow = (id: number, patch: Partial<CardRow>) => {
    setCardRows((rows) => rows.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  };

  const updatePip = (rowId: number, index: number, patch: Partial<PipRow>) => {
    setCardRows((rows) =>
      rows.map((r) =>
        r.id === rowId
          ? { ...r, pips: r.pips.map((p, i) => (i === index ? { ...p, ...patch } : p)) }
          : r
      )
    );
  };

  const buildCardFilters = (): PodSearchCardFilter[] => {
    const filters: PodSearchCardFilter[] = [];
    cardRows.forEach((row) => {
      const filter: PodSearchCardFilter = {};
      let meaningful = false;

      if (row.cardName.trim()) {
        filter.card_name = row.cardName.trim();
        meaningful = true;
      }
      row.pips.forEach((pip) => {
        const min = numberOrUndefined(pip.min);
        if (min !== undefined) {
          filter[`enhanced_${pip.pip}_min`] = min;
          meaningful = true;
        }
        const max = numberOrUndefined(pip.max);
        if (max !== undefined) {
          filter[`enhanced_${pip.pip}_max`] = max;
          meaningful = true;
        }
      });
      ([
        ['is_enhanced', row.isEnhanced],
        ['is_maverick', row.isMaverick],
        ['is_anomaly', row.isAnomaly],
      ] as const).forEach(([key, raw]) => {
        const value = triStateToBool(raw);
        if (value !== undefined) {
          filter[key] = value;
          meaningful = true;
        }
      });

      if (!meaningful) return;
      const minCount = numberOrUndefined(row.minCount);
      if (minCount !== undefined && minCount > 1) filter.min_count = minCount;
      filters.push(filter);
    });
    return filters;
  };

  const runSearch = (targetPage: number) => {
    setLoading(true);
    setError('');

    const podFilters: Record<string, unknown> = {
      ...rangePayload(podValues, POD_RANGES.map((r) => r.key)),
    };
    if (houses.length) podFilters.houses = houses;
    if (expansions.length) podFilters.expansions = expansions;

    const deckFilters: Record<string, unknown> = {
      ...rangePayload(deckValues, DECK_RANGES.map((r) => r.key)),
    };
    if (deckName.trim()) deckFilters.name = deckName.trim();

    podSearch({
      scope,
      card_filters: buildCardFilters(),
      pod_filters: podFilters,
      deck_filters: deckFilters,
      sort,
      sort_dir: sortDir,
      page: targetPage,
      per_page: perPage,
      include_total: includeTotal,
    })
      .then((data) => {
        setResult(data);
        setPage(targetPage);
      })
      .catch((e) => {
        setError(e.response?.data?.error || e.message);
        setResult(null);
      })
      .finally(() => setLoading(false));
  };

  const rangeFields = (
    config: { key: string; label: string }[],
    values: Record<string, string>,
    setValues: (updater: (prev: Record<string, string>) => Record<string, string>) => void
  ) => (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
      {config.map(({ key, label }) => (
        <Box key={key} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Typography variant="body2" sx={{ minWidth: 150 }}>{label}</Typography>
          <TextField
            label="min"
            size="small"
            type="number"
            sx={{ width: 90 }}
            value={values[`${key}_min`] ?? ''}
            onChange={(e) =>
              setValues((prev) => ({ ...prev, [`${key}_min`]: e.target.value }))
            }
          />
          <TextField
            label="max"
            size="small"
            type="number"
            sx={{ width: 90 }}
            value={values[`${key}_max`] ?? ''}
            onChange={(e) =>
              setValues((prev) => ({ ...prev, [`${key}_max`]: e.target.value }))
            }
          />
        </Box>
      ))}
    </Box>
  );

  return (
    <Container maxWidth="xl" sx={{ mt: 3, mb: 6 }}>
      <Typography variant="h5" gutterBottom>Advanced Pod Search</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Find pods by the cards inside them — for example, a pod holding a Keyfrog
        with two damage pips, in a deck with E over 25. Card criteria match within
        a single pod.
      </Typography>

      <ToggleButtonGroup
        exclusive
        size="small"
        value={scope}
        onChange={(_, value) => value && setScope(value)}
        sx={{ mb: 2 }}
      >
        <ToggleButton value="collection">My Collection</ToggleButton>
        <ToggleButton value="all">All Decks</ToggleButton>
      </ToggleButtonGroup>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle1" sx={{ mb: 1 }}>Card criteria</Typography>
        {cardRows.map((row, rowIndex) => (
          <Box key={row.id}>
            {rowIndex > 0 && <Divider sx={{ my: 2 }}>and</Divider>}
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
              <TextField
                label="Card name"
                size="small"
                sx={{ width: 240 }}
                value={row.cardName}
                onChange={(e) => updateCardRow(row.id, { cardName: e.target.value })}
              />
              <Tooltip title="How many copies must match, within one pod">
                <TextField
                  label="Copies"
                  size="small"
                  type="number"
                  sx={{ width: 90 }}
                  value={row.minCount}
                  onChange={(e) => updateCardRow(row.id, { minCount: e.target.value })}
                />
              </Tooltip>
              {([
                ['Enhanced', 'isEnhanced'],
                ['Maverick', 'isMaverick'],
                ['Anomaly', 'isAnomaly'],
              ] as const).map(([label, field]) => (
                <FormControl key={field} size="small" sx={{ width: 130 }}>
                  <InputLabel>{label}</InputLabel>
                  <Select
                    label={label}
                    value={row[field]}
                    onChange={(e) => updateCardRow(row.id, { [field]: e.target.value })}
                  >
                    <MenuItem value=""><em>Any</em></MenuItem>
                    <MenuItem value="yes">Yes</MenuItem>
                    <MenuItem value="no">No</MenuItem>
                  </Select>
                </FormControl>
              ))}
              {cardRows.length > 1 && (
                <IconButton
                  size="small"
                  onClick={() =>
                    setCardRows((rows) => rows.filter((r) => r.id !== row.id))
                  }
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              )}
            </Box>

            <Box sx={{ mt: 1, ml: 1 }}>
              {row.pips.map((pip, pipIndex) => (
                <Box
                  key={pipIndex}
                  sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}
                >
                  <Typography variant="body2" sx={{ width: 40 }}>pips</Typography>
                  <FormControl size="small" sx={{ width: 140 }}>
                    <InputLabel>Type</InputLabel>
                    <Select
                      label="Type"
                      value={pip.pip}
                      onChange={(e) =>
                        updatePip(row.id, pipIndex, { pip: e.target.value })
                      }
                    >
                      {PIP_TYPES.map((p) => (
                        <MenuItem key={p.key} value={p.key}>{p.label}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <TextField
                    label="min"
                    size="small"
                    type="number"
                    sx={{ width: 90 }}
                    value={pip.min}
                    onChange={(e) => updatePip(row.id, pipIndex, { min: e.target.value })}
                  />
                  <TextField
                    label="max"
                    size="small"
                    type="number"
                    sx={{ width: 90 }}
                    value={pip.max}
                    onChange={(e) => updatePip(row.id, pipIndex, { max: e.target.value })}
                  />
                  {row.pips.length > 1 && (
                    <IconButton
                      size="small"
                      onClick={() =>
                        updateCardRow(row.id, {
                          pips: row.pips.filter((_, i) => i !== pipIndex),
                        })
                      }
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  )}
                </Box>
              ))}
              <Button
                size="small"
                startIcon={<AddIcon />}
                onClick={() =>
                  updateCardRow(row.id, {
                    pips: [...row.pips, { pip: 'amber', min: '', max: '' }],
                  })
                }
              >
                Add pip constraint
              </Button>
            </Box>
          </Box>
        ))}
        <Button
          size="small"
          startIcon={<AddIcon />}
          sx={{ mt: 1 }}
          onClick={() => setCardRows((rows) => [...rows, emptyCardRow()])}
        >
          Add card criterion
        </Button>
      </Paper>

      <Accordion variant="outlined" disableGutters>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="subtitle1">Pod filters</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
            <FormControl size="small" sx={{ minWidth: 220 }}>
              <InputLabel>Houses</InputLabel>
              <Select
                multiple
                value={houses}
                onChange={(e) => setHouses(e.target.value as string[])}
                input={<OutlinedInput label="Houses" />}
                renderValue={(selected) => (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {(selected as string[]).map((h) => (
                      <Chip key={h} label={h} size="small" />
                    ))}
                  </Box>
                )}
              >
                {HOUSES.map((house) => (
                  <MenuItem key={house} value={house}>{house}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 220 }}>
              <InputLabel>Sets</InputLabel>
              <Select
                multiple
                value={expansions}
                onChange={(e) => setExpansions(e.target.value as number[])}
                input={<OutlinedInput label="Sets" />}
                renderValue={(selected) => (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {(selected as number[]).map((num) => (
                      <Chip
                        key={num}
                        size="small"
                        label={sets.find((s) => s.number === num)?.shortname ?? num}
                      />
                    ))}
                  </Box>
                )}
              >
                {sets.map((set) => (
                  <MenuItem key={set.number} value={set.number}>{set.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
          {rangeFields(POD_RANGES, podValues, setPodValues)}
        </AccordionDetails>
      </Accordion>

      <Accordion variant="outlined" disableGutters sx={{ mb: 2 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="subtitle1">Deck filters (SAS / AERC)</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <TextField
            label="Deck name contains"
            size="small"
            sx={{ width: 280, mb: 2 }}
            value={deckName}
            onChange={(e) => setDeckName(e.target.value)}
          />
          {rangeFields(DECK_RANGES, deckValues, setDeckValues)}
          <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
            AERC letters are deck-wide: pod-level scores are only stored as pod
            SAS and pod AERC.
          </Typography>
        </AccordionDetails>
      </Accordion>

      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 2 }}>
        <FormControl size="small" sx={{ width: 200 }}>
          <InputLabel>Sort by</InputLabel>
          <Select label="Sort by" value={sort} onChange={(e) => setSort(e.target.value)}>
            {SORTS.map((s) => (
              <MenuItem key={s.key} value={s.key}>{s.label}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ width: 130 }}>
          <InputLabel>Order</InputLabel>
          <Select
            label="Order"
            value={sortDir}
            onChange={(e) => setSortDir(e.target.value as 'asc' | 'desc')}
          >
            <MenuItem value="desc">High → low</MenuItem>
            <MenuItem value="asc">Low → high</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ width: 110 }}>
          <InputLabel>Per page</InputLabel>
          <Select
            label="Per page"
            value={perPage}
            onChange={(e) => setPerPage(Number(e.target.value))}
          >
            {[10, 25, 50, 100].map((n) => (
              <MenuItem key={n} value={n}>{n}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <Tooltip title="Counting every match roughly doubles the query time">
          <FormControlLabel
            control={
              <Checkbox
                size="small"
                checked={includeTotal}
                onChange={(e) => setIncludeTotal(e.target.checked)}
              />
            }
            label="Exact total"
          />
        </Tooltip>
        <Button variant="contained" disabled={loading} onClick={() => runSearch(1)}>
          Search
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {loading && <CircularProgress />}

      {result && !loading && (
        <>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
            <Typography variant="subtitle2">
              {result.total !== null
                ? `${result.total} matching pods`
                : `Page ${result.page}${result.has_more ? '' : ' (last)'}`}
            </Typography>
            <Box sx={{ flexGrow: 1 }} />
            <Button
              size="small"
              disabled={page <= 1}
              onClick={() => runSearch(page - 1)}
            >
              Previous
            </Button>
            <Button
              size="small"
              disabled={!result.has_more}
              onClick={() => runSearch(page + 1)}
            >
              Next
            </Button>
          </Box>

          {result.pods.length === 0 ? (
            <Alert severity="info">No pods matched.</Alert>
          ) : (
            <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Deck</TableCell>
                    <TableCell>House</TableCell>
                    <TableCell>Set</TableCell>
                    <TableCell align="right">Pod SAS</TableCell>
                    <TableCell align="right">Pod AERC</TableCell>
                    <TableCell align="right">Enh.</TableCell>
                    <TableCell align="right">Creatures</TableCell>
                    <TableCell align="right">Deck SAS</TableCell>
                    <TableCell align="right">E</TableCell>
                    <TableCell align="right">A</TableCell>
                    <TableCell align="right">C</TableCell>
                    <TableCell>Links</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {result.pods.map((pod) => (
                    <TableRow key={`${pod.deck_kf_id}-${pod.house}`}>
                      <TableCell>
                        <Typography
                          component={RouterLink}
                          to={`/deck/${pod.deck_kf_id}`}
                          variant="body2"
                          sx={{ color: 'primary.main', textDecoration: 'none' }}
                        >
                          {pod.deck_name}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={pod.house} size="small" />
                      </TableCell>
                      <TableCell>{pod.expansion_name}</TableCell>
                      <TableCell align="right">{fmt(pod.sas_rating)}</TableCell>
                      <TableCell align="right">{fmt(pod.aerc_score)}</TableCell>
                      <TableCell align="right">{fmt(pod.num_enhancements)}</TableCell>
                      <TableCell align="right">{fmt(pod.creatures)}</TableCell>
                      <TableCell align="right">{fmt(pod.deck_sas)}</TableCell>
                      <TableCell align="right">{fmt(pod.dok?.expected_amber)}</TableCell>
                      <TableCell align="right">{fmt(pod.dok?.amber_control)}</TableCell>
                      <TableCell align="right">{fmt(pod.dok?.creature_control)}</TableCell>
                      <TableCell>
                        <Typography
                          component="a"
                          href={pod.deck_mv_url}
                          target="_blank"
                          rel="noopener"
                          variant="body2"
                          sx={{ mr: 1 }}
                        >
                          MV
                        </Typography>
                        <Typography
                          component="a"
                          href={pod.deck_dok_url}
                          target="_blank"
                          rel="noopener"
                          variant="body2"
                        >
                          DoK
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </>
      )}
    </Container>
  );
}
