import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  Tab,
  Tabs,
  TextField,
  Typography,
  alpha,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useLeagueNumericId } from '../contexts/LeagueContext';
import {
  getCardCategoryOptions,
  getLeague,
  getRestrictedListVersions,
  getSets,
  searchCards,
} from '../api/leagues';
import {
  drawPlayoffs,
  getPlayoffSetup,
  getPlayoffStandings,
  getPlayoffTree,
  publishPlayoffs,
  setPlayoffBrackets,
  setPlayoffQualifiers,
  startPlayoffRound,
  updatePlayoffConfig,
} from '../api/playoffs';
import type { PlayoffSetup, PlayoffStandings, PlayoffTree } from '../api/playoffs';
import type {
  CardCategoryPreset,
  KeyforgeSetInfo,
  LeagueDetail,
  RequiredCardCategory,
} from '../types';
import { localInputToIso } from '../utils/deadlines';
import { WEEK_FORMAT_LABELS } from '../utils/formatLabels';

/**
 * The playoffs: several brackets at once, one per player on a team, each in
 * its own format and each advancing on its own.
 */
export default function PlayoffsPage() {
  const leagueId = useLeagueNumericId();
  const navigate = useNavigate();

  const [league, setLeague] = useState<LeagueDetail | null>(null);
  const [setup, setSetup] = useState<PlayoffSetup | null>(null);
  const [tree, setTree] = useState<PlayoffTree | null>(null);
  const [sets, setSets] = useState<KeyforgeSetInfo[]>([]);
  const [rlVersions, setRlVersions] = useState<{ id: number; version: number }[]>([]);
  const [cardCategoryOptions, setCardCategoryOptions] = useState<{ presets: CardCategoryPreset[] }>(
    { presets: [] },
  );
  const [standings, setStandings] = useState<PlayoffStandings | null>(null);
  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const refresh = useCallback(() => {
    Promise.all([
      getLeague(leagueId),
      getPlayoffSetup(leagueId),
      getPlayoffTree(leagueId),
      getPlayoffStandings(leagueId).catch(() => null),
    ])
      .then(([l, s, t, st]) => {
        setLeague(l);
        setSetup(s);
        setTree(t);
        setStandings(st);
      })
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    getSets().then(setSets).catch(() => {});
    getRestrictedListVersions().then(setRlVersions).catch(() => {});
    getCardCategoryOptions().then(setCardCategoryOptions).catch(() => {});
  }, []);

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (!league || !setup) {
    return (
      <Container sx={{ mt: 3 }}>
        <Alert severity="error">{error || 'Could not load the playoffs'}</Alert>
      </Container>
    );
  }

  const teamName = (id: number | null) =>
    id == null ? null : tree?.teams?.[String(id)] ?? league.teams.find((t) => t.id === id)?.name ?? null;
  const drawn = Boolean(setup.config.drawn_at);
  const rounds = tree?.rounds || 0;

  const roundLabel = (n: number) => {
    if (!rounds) return `Round ${n}`;
    if (n === rounds) return 'Final';
    if (n === rounds - 1) return 'Semi-final';
    return `Round ${n}`;
  };

  const act = async (what: () => Promise<unknown>, done: string) => {
    setError('');
    setSuccess('');
    try {
      await what();
      setSuccess(done);
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
        <IconButton onClick={() => navigate('..')} size="small" sx={{ mr: 1 }}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h4">{league.name}</Typography>
      </Box>
      <Typography variant="h5" gutterBottom>Playoffs</Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      {!drawn && (
        <Alert severity="info" sx={{ mb: 2 }}>
          The brackets have not been drawn yet.
          {setup.config.expected_brackets
            ? ` There will be ${setup.config.expected_brackets}, one per player on a team, each in its own format.`
            : ''}
        </Alert>
      )}

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }} variant="scrollable" scrollButtons="auto">
        <Tab label="Brackets" />
        <Tab label="Standings" />
        {(setup.is_admin || setup.is_captain) && <Tab label="Setup" />}
      </Tabs>

      {tab === 0 && (
        <Box>
          {!drawn && <Typography color="text.secondary">Nothing to show until the draw.</Typography>}
          {drawn && (tree?.brackets || []).map((bracket) => {
            const byRound = new Map<number, typeof bracket.matches>();
            for (const m of bracket.matches || []) {
              const key = m.is_consolation ? -1 : m.round_number;
              byRound.set(key, [...(byRound.get(key) || []), m]);
            }
            const ordered = [...byRound.entries()].sort((a, b) => a[0] - b[0]);
            return (
              <Card key={bracket.id} sx={{ mb: 2 }}>
                <CardContent>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1, flexWrap: 'wrap' }}>
                    <Typography variant="h6">
                      {bracket.name || `Bracket ${bracket.bracket_number}`}
                    </Typography>
                    <Chip size="small" variant="outlined"
                      label={WEEK_FORMAT_LABELS[bracket.format_type] || bracket.format_type} />
                    <Chip size="small" variant="outlined" label={`Bo${bracket.best_of_n}`} />
                  </Box>
                  <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                    {ordered.map(([key, matches]) => (
                      <Box key={key} sx={{ minWidth: 210 }}>
                        <Typography variant="caption" color="text.secondary">
                          {key === -1 ? 'Third place' : roundLabel(key)}
                        </Typography>
                        {(matches || []).map((m) => (
                          <Box
                            key={m.id}
                            sx={(theme) => ({
                              mt: 0.5, p: 1, borderRadius: 1,
                              border: 1, borderColor: 'divider',
                              bgcolor: m.winner_team_id
                                ? alpha(theme.palette.success.main, 0.06)
                                : 'transparent',
                            })}
                          >
                            {[m.team1_id, m.team2_id].map((side, i) => (
                              <Typography
                                key={i}
                                variant="body2"
                                sx={{
                                  fontWeight: side && side === m.winner_team_id ? 700 : 400,
                                  color: side ? 'text.primary' : 'text.disabled',
                                }}
                              >
                                {teamName(side) || 'to be decided'}
                              </Typography>
                            ))}
                            {m.is_bye && <Chip size="small" label="Bye" sx={{ mt: 0.5 }} />}
                          </Box>
                        ))}
                      </Box>
                    ))}
                  </Box>
                </CardContent>
              </Card>
            );
          })}
        </Box>
      )}

      {tab === 1 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Playoff standings</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              These start from zero: the regular season decided who is here, not who is ahead.
              A bye scores the round it came through.
              {standings?.points_per_round?.length
                ? ` A win is worth ${standings.points_per_round.join(', then ')} by round`
                : ''}
              {standings && setup.config.consolation_enabled
                ? `, and ${standings.consolation_points} for third place.`
                : '.'}
            </Typography>
            {(standings?.standings || []).length === 0 && (
              <Typography color="text.secondary">Nothing yet.</Typography>
            )}
            {(standings?.standings || []).map((row, index) => (
              <Box
                key={row.team_id}
                sx={{ display: 'flex', gap: 2, alignItems: 'center', py: 0.5,
                      borderBottom: '1px solid', borderColor: 'divider' }}
              >
                <Typography variant="body2" sx={{ width: 24 }}>{index + 1}</Typography>
                <Typography variant="body2" sx={{ flexGrow: 1 }}>{row.team_name}</Typography>
                <Chip size="small" label={`${row.points} pt${row.points === 1 ? '' : 's'}`} />
                <Typography variant="caption" color="text.secondary">
                  {row.wins} of {row.matches_played} won
                  {row.byes ? `, ${row.byes} bye${row.byes === 1 ? '' : 's'}` : ''}
                </Typography>
              </Box>
            ))}
          </CardContent>
        </Card>
      )}

      {tab === 2 && (setup.is_admin || setup.is_captain) && (
        <PlayoffSetupPanel
          league={league}
          setup={setup}
          rounds={rounds}
          onAct={act}
          leagueId={leagueId}
          sets={sets}
          rlVersions={rlVersions}
          cardPresets={cardCategoryOptions.presets}
          roundLabel={roundLabel}
        />
      )}
    </Container>
  );
}

function PlayoffSetupPanel({
  league,
  setup,
  rounds,
  onAct,
  leagueId,
  sets,
  rlVersions,
  cardPresets,
  roundLabel,
}: {
  league: LeagueDetail;
  setup: PlayoffSetup;
  rounds: number;
  onAct: (what: () => Promise<unknown>, done: string) => Promise<void>;
  leagueId: number;
  sets: KeyforgeSetInfo[];
  rlVersions: { id: number; version: number }[];
  cardPresets: CardCategoryPreset[];
  roundLabel: (n: number) => string;
}) {
  const drawn = Boolean(setup.config.drawn_at);
  const published = Boolean(setup.config.published_at);
  // Which round the deadline dialog is for, if it is open.
  const [openingRound, setOpeningRound] = useState<number | null>(null);
  const [deckDeadline, setDeckDeadline] = useState('');
  const [matchDeadline, setMatchDeadline] = useState('');
  const [advancing, setAdvancing] = useState(setup.config.teams_advancing);
  const [points, setPoints] = useState(setup.config.points_per_round.join(', '));
  const [consolation, setConsolation] = useState(setup.config.consolation_enabled);
  const [consolationPoints, setConsolationPoints] = useState(setup.config.consolation_points);
  const [byePolicy, setByePolicy] = useState(setup.config.bye_policy);
  const [qualifiers, setQualifiers] = useState<number[]>(setup.qualifiers.map((q) => q.team_id));
  return (
    <Box>
      {setup.is_admin && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>Configuration</Typography>
            {drawn && <Alert severity="info" sx={{ mb: 1 }}>The brackets are drawn, so this is fixed.</Alert>}
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
              <TextField
                size="small" type="number" label="Teams advancing" sx={{ width: 150 }}
                value={advancing} disabled={drawn}
                onChange={(e) => setAdvancing(parseInt(e.target.value, 10) || 0)}
              />
              <TextField
                size="small" label="Points per round" sx={{ width: 190 }}
                helperText="e.g. 2, 1" value={points} disabled={drawn}
                onChange={(e) => setPoints(e.target.value)}
              />
              <FormControlLabel
                control={
                  <Switch checked={consolation} disabled={drawn}
                    onChange={(e) => setConsolation(e.target.checked)} />
                }
                label="Play for third"
              />
              <TextField
                size="small" type="number" label="Third-place points" sx={{ width: 160 }}
                value={consolationPoints} disabled={drawn || !consolation}
                onChange={(e) => setConsolationPoints(parseInt(e.target.value, 10) || 0)}
              />
              <FormControl size="small" sx={{ minWidth: 220 }} disabled={drawn}>
                <InputLabel>Byes</InputLabel>
                <Select label="Byes" value={byePolicy}
                  onChange={(e) => setByePolicy(e.target.value as typeof byePolicy)}>
                  <MenuItem value="random_even">Spread evenly at random</MenuItem>
                  <MenuItem value="team_record">Best regular season finish</MenuItem>
                  <MenuItem value="player_record">Best player record in that bracket</MenuItem>
                  <MenuItem value="admin">Assigned by hand</MenuItem>
                </Select>
              </FormControl>
              <Button
                variant="contained" disabled={drawn}
                onClick={() =>
                  onAct(
                    () => updatePlayoffConfig(leagueId, {
                      teams_advancing: advancing,
                      points_per_round: points.split(',').map((p) => parseInt(p.trim(), 10)).filter((n) => !isNaN(n)),
                      consolation_enabled: consolation,
                      consolation_points: consolationPoints,
                      bye_policy: byePolicy,
                    }),
                    'Configuration saved.',
                  )
                }
              >
                Save
              </Button>
            </Box>
          </CardContent>
        </Card>
      )}

      {setup.is_admin && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Qualifying teams ({qualifiers.length} of {setup.config.teams_advancing})
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              In finishing order. The order does not decide who plays whom — that is drawn per
              bracket — but it settles ties and feeds the record-based bye policies.
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
              {league.teams.map((team) => {
                const at = qualifiers.indexOf(team.id);
                return (
                  <Chip
                    key={team.id}
                    label={at >= 0 ? `${at + 1}. ${team.name}` : team.name}
                    color={at >= 0 ? 'primary' : 'default'}
                    variant={at >= 0 ? 'filled' : 'outlined'}
                    onClick={drawn ? undefined : () =>
                      setQualifiers((prev) =>
                        prev.includes(team.id) ? prev.filter((id) => id !== team.id) : [...prev, team.id])
                    }
                  />
                );
              })}
            </Box>
            <Button variant="contained" disabled={drawn}
              onClick={() => onAct(() => setPlayoffQualifiers(leagueId, qualifiers), 'Qualifiers saved.')}>
              Save qualifiers
            </Button>
          </CardContent>
        </Card>
      )}

      {setup.is_admin && (
        <BracketEditor
          setup={setup}
          drawn={drawn}
          leagueId={leagueId}
          onAct={onAct}
          sets={sets}
          rlVersions={rlVersions}
          cardPresets={cardPresets}
        />
      )}

      {setup.is_admin && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Running the playoffs</Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Button
                variant={published ? 'outlined' : 'contained'}
                disabled={setup.brackets.length === 0 || (published && drawn)}
                onClick={() =>
                  onAct(
                    () => publishPlayoffs(leagueId, !published),
                    published ? 'Setup hidden again.' : 'Setup published to the teams.',
                  )
                }
              >
                {published ? 'Unpublish' : 'Publish to the teams'}
              </Button>
              <Button
                variant="contained" disabled={drawn}
                onClick={() => onAct(() => drawPlayoffs(leagueId), 'Brackets drawn.')}
              >
                Draw the brackets
              </Button>
              {Array.from({ length: rounds }, (_, i) => i + 1).map((n) => (
                <Button
                  key={n} variant="outlined" disabled={!drawn}
                  onClick={() => {
                    setDeckDeadline('');
                    setMatchDeadline('');
                    setOpeningRound(n);
                  }}
                >
                  Open round {n}
                </Button>
              ))}
            </Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              Publishing shows the brackets to the teams and opens the Playoffs tab on My
              Team, where captains put a player in each bracket.
              Opening a round creates a week per bracket and its matches. A later round will not
              open until every result before it is reported and verified.
            </Typography>
          </CardContent>
        </Card>
      )}

      <Dialog open={openingRound !== null} onClose={() => setOpeningRound(null)} maxWidth="xs" fullWidth>
        <DialogTitle>
          Open {openingRound ? roundLabel(openingRound).toLowerCase() : 'round'}
        </DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <Typography variant="body2" color="text.secondary">
            A bracket runs for the whole playoffs, so its deadlines belong to the round
            rather than to it. These apply to every bracket in this round, and can be
            moved by opening the round again. Leave them blank for none.
          </Typography>
          <TextField
            label="Deck submission deadline"
            type="datetime-local"
            size="small"
            InputLabelProps={{ shrink: true }}
            value={deckDeadline}
            onChange={(e) => setDeckDeadline(e.target.value)}
          />
          <TextField
            label="Match completion deadline"
            type="datetime-local"
            size="small"
            InputLabelProps={{ shrink: true }}
            value={matchDeadline}
            onChange={(e) => setMatchDeadline(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpeningRound(null)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => {
              const n = openingRound!;
              setOpeningRound(null);
              onAct(
                () => startPlayoffRound(leagueId, n, {
                  deck_submission_deadline: localInputToIso(deckDeadline),
                  match_completion_deadline: localInputToIso(matchDeadline),
                }),
                `Round ${n} opened.`,
              );
            }}
          >
            Open
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

interface BracketRow {
  name: string;
  format_type: string;
  best_of_n: number;
  max_sas: number | null;
  sas_floor: number | null;
  combined_max_sas: number | null;
  set_diversity: boolean;
  house_diversity: boolean;
  decks_per_player: number | null;
  no_keycheat: boolean;
  team_max_raw_amber: number | null;
  team_min_raw_amber: number | null;
  allowed_sets: number[];
  required_card_names: string[];
  required_card_categories: RequiredCardCategory[];
  alliance_restricted_list_version_id: number | '';
  custom_description: string;
  hide_standard_description: boolean;
}

const EMPTY_BRACKET: BracketRow = {
  name: '',
  format_type: 'archon_standard',
  best_of_n: 1,
  max_sas: null,
  sas_floor: null,
  combined_max_sas: null,
  set_diversity: false,
  house_diversity: false,
  decks_per_player: null,
  no_keycheat: false,
  team_max_raw_amber: null,
  team_min_raw_amber: null,
  allowed_sets: [],
  required_card_names: [],
  required_card_categories: [],
  alliance_restricted_list_version_id: '',
  custom_description: '',
  hide_standard_description: false,
};

/**
 * Formats a bracket cannot be run in. The SAS ladder spreads a whole team over
 * rungs, where a bracket is one player from each team playing one opponent.
 */
const NON_BRACKET_FORMATS = ['sas_ladder'];

/** Formats played with alliance decks, which a restricted list applies to. */
function isAllianceFormat(formatType: string): boolean {
  return formatType.includes('alliance');
}

/** A number field that means "unset" when it is empty, not zero. */
function numberOrNull(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const value = parseInt(trimmed, 10);
  return isNaN(value) ? null : value;
}

function BracketEditor({
  setup,
  drawn,
  leagueId,
  onAct,
  sets,
  rlVersions,
  cardPresets,
}: {
  setup: PlayoffSetup;
  drawn: boolean;
  leagueId: number;
  onAct: (what: () => Promise<unknown>, done: string) => Promise<void>;
  sets: KeyforgeSetInfo[];
  rlVersions: { id: number; version: number }[];
  cardPresets: CardCategoryPreset[];
}) {
  const expected = setup.config.expected_brackets;
  const [rows, setRows] = useState<BracketRow[]>(() =>
    setup.brackets.length > 0
      ? setup.brackets.map((b) => ({
          ...EMPTY_BRACKET,
          name: b.name || '',
          format_type: b.format_type,
          best_of_n: b.best_of_n,
          max_sas: b.max_sas ?? null,
          sas_floor: b.sas_floor ?? null,
          combined_max_sas: b.combined_max_sas ?? null,
          set_diversity: Boolean(b.set_diversity),
          house_diversity: Boolean(b.house_diversity),
          decks_per_player: b.decks_per_player ?? null,
          no_keycheat: Boolean(b.no_keycheat),
          team_max_raw_amber: b.team_max_raw_amber ?? null,
          team_min_raw_amber: b.team_min_raw_amber ?? null,
          allowed_sets: b.allowed_sets || [],
          required_card_names: b.required_card_names || [],
          required_card_categories: b.required_card_categories || [],
          alliance_restricted_list_version_id: b.alliance_restricted_list_version_id ?? '',
          custom_description: b.custom_description || '',
          hide_standard_description: Boolean(b.hide_standard_description),
        }))
      : Array.from({ length: expected }, () => ({ ...EMPTY_BRACKET })),
  );

  const edit = (index: number, patch: Partial<BracketRow>) =>
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, ...patch } : r)));

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Brackets ({rows.length} of {expected})
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          One per player on a team, each in its own format. A bracket&apos;s settings are
          copied onto the week it plays each round, so they are set once here rather than
          every round.
        </Typography>
        {rows.map((row, index) => (
          <Accordion key={index} disableGutters sx={{ mb: 0.5 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                <Typography variant="body2" sx={{ width: 24 }}>{index + 1}</Typography>
                <Typography variant="body2" sx={{ minWidth: 140 }}>
                  {row.name || `Bracket ${index + 1}`}
                </Typography>
                <Chip size="small" variant="outlined"
                  label={WEEK_FORMAT_LABELS[row.format_type] || row.format_type} />
                <Chip size="small" variant="outlined" label={`Bo${row.best_of_n}`} />
                {row.max_sas != null && <Chip size="small" variant="outlined" label={`Max SAS ${row.max_sas}`} />}
                {row.allowed_sets.length > 0 && (
                  <Chip size="small" variant="outlined" label={`${row.allowed_sets.length} set(s)`} />
                )}
                {(row.required_card_names.length + row.required_card_categories.length) > 0 && (
                  <Chip size="small" variant="outlined" color="info"
                    label={`${row.required_card_names.length + row.required_card_categories.length} required`} />
                )}
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <Box sx={{ display: 'flex', gap: 1, mb: 1, flexWrap: 'wrap', alignItems: 'center' }}>
                <TextField
                  size="small" label="Name" sx={{ width: 180 }} disabled={drawn}
                  value={row.name}
                  onChange={(e) => edit(index, { name: e.target.value })}
                />
                <FormControl size="small" sx={{ minWidth: 220 }} disabled={drawn}>
                  <InputLabel>Format</InputLabel>
                  <Select
                    label="Format" value={row.format_type}
                    onChange={(e) => edit(index, { format_type: String(e.target.value) })}
                  >
                    {Object.entries(WEEK_FORMAT_LABELS)
                      .filter(([value]) => !NON_BRACKET_FORMATS.includes(value))
                      .map(([value, label]) => (
                        <MenuItem key={value} value={value}>{label}</MenuItem>
                      ))}
                  </Select>
                </FormControl>
                <TextField
                  size="small" type="number" label="Best of" sx={{ width: 100 }} disabled={drawn}
                  value={row.best_of_n}
                  onChange={(e) => edit(index, { best_of_n: parseInt(e.target.value, 10) || 1 })}
                />
                <TextField
                  size="small" type="number" label="Decks per player" sx={{ width: 150 }} disabled={drawn}
                  value={row.decks_per_player ?? ''}
                  onChange={(e) => edit(index, { decks_per_player: numberOrNull(e.target.value) })}
                />
              </Box>
              <Box sx={{ display: 'flex', gap: 1, mb: 1, flexWrap: 'wrap', alignItems: 'center' }}>
                <TextField
                  size="small" type="number" label="Max SAS" sx={{ width: 120 }} disabled={drawn}
                  value={row.max_sas ?? ''}
                  onChange={(e) => edit(index, { max_sas: numberOrNull(e.target.value) })}
                />
                <TextField
                  size="small" type="number" label="SAS floor" sx={{ width: 120 }} disabled={drawn}
                  value={row.sas_floor ?? ''}
                  onChange={(e) => edit(index, { sas_floor: numberOrNull(e.target.value) })}
                />
                <TextField
                  size="small" type="number" label="Combined max SAS" sx={{ width: 170 }} disabled={drawn}
                  value={row.combined_max_sas ?? ''}
                  onChange={(e) => edit(index, { combined_max_sas: numberOrNull(e.target.value) })}
                />
                <TextField
                  size="small" type="number" label="Team max raw æmber" sx={{ width: 180 }} disabled={drawn}
                  value={row.team_max_raw_amber ?? ''}
                  onChange={(e) => edit(index, { team_max_raw_amber: numberOrNull(e.target.value) })}
                />
                <TextField
                  size="small" type="number" label="Team min raw æmber" sx={{ width: 180 }} disabled={drawn}
                  value={row.team_min_raw_amber ?? ''}
                  onChange={(e) => edit(index, { team_min_raw_amber: numberOrNull(e.target.value) })}
                />
              </Box>
              <Box sx={{ display: 'flex', gap: 1, mb: 1, flexWrap: 'wrap', alignItems: 'center' }}>
                <FormControl size="small" sx={{ minWidth: 260 }} disabled={drawn}>
                  <InputLabel>Allowed sets</InputLabel>
                  <Select
                    multiple label="Allowed sets" value={row.allowed_sets}
                    onChange={(e) => edit(index, { allowed_sets: e.target.value as number[] })}
                    renderValue={(selected) => (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {(selected as number[]).map((v) => (
                          <Chip key={v} size="small"
                            label={sets.find((x) => x.number === v)?.shortname || v} />
                        ))}
                      </Box>
                    )}
                  >
                    {sets.map((set) => (
                      <MenuItem key={set.number} value={set.number}>
                        {set.name} ({set.shortname})
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControlLabel
                  control={<Switch checked={row.set_diversity} disabled={drawn}
                    onChange={(e) => edit(index, { set_diversity: e.target.checked })} />}
                  label="Set diversity"
                />
                <FormControlLabel
                  control={<Switch checked={row.house_diversity} disabled={drawn}
                    onChange={(e) => edit(index, { house_diversity: e.target.checked })} />}
                  label="House diversity"
                />
                <FormControlLabel
                  control={<Switch checked={row.no_keycheat} disabled={drawn}
                    onChange={(e) => edit(index, { no_keycheat: e.target.checked })} />}
                  label="No keycheat"
                />
              </Box>
              <RequiredCardsField
                disabled={drawn}
                presets={cardPresets}
                cards={row.required_card_names}
                categories={row.required_card_categories}
                onChange={(cards, categories) =>
                  edit(index, { required_card_names: cards, required_card_categories: categories })
                }
              />

              {isAllianceFormat(row.format_type) && rlVersions.length > 0 && (
                <FormControl size="small" sx={{ minWidth: 260, mb: 1 }} disabled={drawn}>
                  <InputLabel>Alliance restricted list</InputLabel>
                  <Select
                    label="Alliance restricted list"
                    value={row.alliance_restricted_list_version_id}
                    onChange={(e) =>
                      edit(index, {
                        alliance_restricted_list_version_id: e.target.value as number | '',
                      })
                    }
                  >
                    <MenuItem value=""><em>Latest version</em></MenuItem>
                    {rlVersions.map((v) => (
                      <MenuItem key={v.id} value={v.id}>v{v.version}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}

              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
                <TextField
                  size="small" label="Custom description" sx={{ minWidth: 320, flexGrow: 1 }}
                  multiline maxRows={4} disabled={drawn}
                  value={row.custom_description}
                  onChange={(e) => edit(index, { custom_description: e.target.value })}
                />
                <FormControlLabel
                  control={<Switch checked={row.hide_standard_description} disabled={drawn}
                    onChange={(e) => edit(index, { hide_standard_description: e.target.checked })} />}
                  label="Hide standard description"
                />
              </Box>
            </AccordionDetails>
          </Accordion>
        ))}
        <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
          <Button variant="contained" disabled={drawn}
            onClick={() =>
              onAct(
                () => setPlayoffBrackets(
                  leagueId,
                  rows.map((row) => ({
                    ...row,
                    alliance_restricted_list_version_id:
                      row.alliance_restricted_list_version_id === ''
                        ? null
                        : row.alliance_restricted_list_version_id,
                  })),
                ),
                'Brackets saved.',
              )
            }>
            Save brackets
          </Button>
          <Button disabled={drawn} onClick={() => setRows((prev) => [...prev, { ...EMPTY_BRACKET }])}>
            Add one
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
}


/**
 * Cards a deck in this bracket must contain, individually or by group.
 *
 * The same control as the week editor's: a group like a Skybeast is a
 * requirement in the same sense a named card is, so both are searched for in
 * one box rather than two.
 */
function RequiredCardsField({
  disabled,
  presets,
  cards,
  categories,
  onChange,
}: {
  disabled: boolean;
  presets: CardCategoryPreset[];
  cards: string[];
  categories: RequiredCardCategory[];
  onChange: (cards: string[], categories: RequiredCardCategory[]) => void;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  return (
    <Box sx={{ mb: 1 }}>
      <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
        Required cards {cards.length + categories.length > 0 ? `(${cards.length + categories.length})` : ''}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
        Each deck must contain at least one card from this list. Within a team, each card
        can only appear in one player&apos;s deck.
      </Typography>
      <Autocomplete
        freeSolo
        disabled={disabled}
        options={[
          ...presets
            .filter(
              (p) =>
                query.length >= 2 &&
                p.name.toLowerCase().includes(query.toLowerCase()) &&
                !categories.some((c) => c.preset === p.key),
            )
            .map((p) => `group:${p.key}`),
          ...results,
        ]}
        getOptionLabel={(option) => {
          if (typeof option !== 'string') return '';
          if (!option.startsWith('group:')) return option;
          const preset = presets.find((p) => p.key === option.slice('group:'.length));
          const size = preset?.category.card_titles?.length;
          return preset ? `${preset.name}${size ? ` (${size} cards)` : ''}` : option;
        }}
        inputValue={query}
        onInputChange={(_e, value) => {
          setQuery(value);
          if (value.length >= 2) {
            setLoading(true);
            searchCards(value).then(setResults).finally(() => setLoading(false));
          } else {
            setResults([]);
          }
        }}
        onChange={(_e, value) => {
          if (value && typeof value === 'string') {
            if (value.startsWith('group:')) {
              const preset = presets.find((p) => p.key === value.slice('group:'.length));
              if (preset) onChange(cards, [...categories, { ...preset.category }]);
            } else if (!cards.includes(value)) {
              onChange([...cards, value], categories);
            }
          }
          setQuery('');
          setResults([]);
        }}
        loading={loading}
        renderInput={(params) => (
          <TextField
            {...params}
            label="Search cards or groups to add"
            size="small"
            helperText="Individual cards, or a known group like a Skybeast or an X-Y Mutant"
          />
        )}
        size="small"
      />
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
        {categories.map((cat, idx) => (
          <Chip
            key={`cat-${idx}`}
            color="info"
            size="small"
            label={(cat.label || 'card group') + (cat.card_titles ? ` · ${cat.card_titles.length} cards` : '')}
            onDelete={disabled ? undefined : () => onChange(cards, categories.filter((_c, i) => i !== idx))}
          />
        ))}
        {cards.map((card) => (
          <Chip
            key={card}
            size="small"
            label={card}
            onDelete={disabled ? undefined : () => onChange(cards.filter((c) => c !== card), categories)}
          />
        ))}
      </Box>
      {categories.length > 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
          A group counts once per team: if one player brings a card from it, nobody else on
          that team can.
        </Typography>
      )}
    </Box>
  );
}
