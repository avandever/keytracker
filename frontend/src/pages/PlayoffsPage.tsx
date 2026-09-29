import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
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
import { useLeagueNumericId } from '../contexts/LeagueContext';
import { useAuth } from '../contexts/AuthContext';
import { getLeague, submitDeckSelection, getSets } from '../api/leagues';
import {
  drawPlayoffs,
  getPlayoffRoundDecks,
  getPlayoffSetup,
  getPlayoffStandings,
  getPlayoffTree,
  setPlayoffAssignments,
  setPlayoffBrackets,
  setPlayoffQualifiers,
  startPlayoffRound,
  updatePlayoffConfig,
} from '../api/playoffs';
import type {
  PlayoffRoundDecks,
  PlayoffSetup,
  PlayoffStandings,
  PlayoffTree,
} from '../api/playoffs';
import type { KeyforgeSetInfo, LeagueDetail } from '../types';
import WeekConstraints from '../components/WeekConstraints';
import HouseIcons from '../components/HouseIcons';
import { WEEK_FORMAT_LABELS } from '../utils/formatLabels';

/**
 * The playoffs: several brackets at once, one per player on a team, each in
 * its own format and each advancing on its own.
 */
export default function PlayoffsPage() {
  const leagueId = useLeagueNumericId();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [league, setLeague] = useState<LeagueDetail | null>(null);
  const [setup, setSetup] = useState<PlayoffSetup | null>(null);
  const [tree, setTree] = useState<PlayoffTree | null>(null);
  const [sets, setSets] = useState<KeyforgeSetInfo[]>([]);
  const [decks, setDecks] = useState<PlayoffRoundDecks | null>(null);
  const [standings, setStandings] = useState<PlayoffStandings | null>(null);
  const [round, setRound] = useState(1);
  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [deckUrls, setDeckUrls] = useState<Record<string, string>>({});

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
  useEffect(() => { getSets().then(setSets).catch(() => {}); }, []);

  useEffect(() => {
    const raw = searchParams.get('round');
    if (raw && !isNaN(parseInt(raw, 10))) setRound(parseInt(raw, 10));
  }, [searchParams]);

  const loadDecks = useCallback(() => {
    if (!setup?.my_team_id && !setup?.is_admin) return;
    getPlayoffRoundDecks(leagueId, round)
      .then(setDecks)
      .catch(() => setDecks(null));
  }, [leagueId, round, setup]);

  useEffect(() => { loadDecks(); }, [loadDecks]);

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
      loadDecks();
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
        {(setup.my_team_id || setup.is_admin) && <Tab label="My Team" />}
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

      {tab === 2 && (setup.my_team_id || setup.is_admin) && (
        <Box>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Round</InputLabel>
              <Select
                label="Round"
                value={round}
                onChange={(e) => {
                  const next = Number(e.target.value);
                  setRound(next);
                  setSearchParams((prev) => { prev.set('round', String(next)); return prev; }, { replace: true });
                }}
              >
                {Array.from({ length: Math.max(rounds, 1) }, (_, i) => i + 1).map((n) => (
                  <MenuItem key={n} value={n}>{roundLabel(n)}</MenuItem>
                ))}
              </Select>
            </FormControl>
            {decks?.team_name && <Typography variant="body2" color="text.secondary">{decks.team_name}</Typography>}
          </Box>

          {(!decks || decks.rows.length === 0) && (
            <Typography color="text.secondary">
              This round has not been opened yet.
            </Typography>
          )}

          {(decks?.rows || []).map((row) => {
            const key = `${row.bracket.id}`;
            const canSubmit = row.week.status === 'deck_selection'
              || row.week.status === 'team_paired'
              || row.week.status === 'pairing';
            return (
              <Card key={row.bracket.id} sx={{ mb: 2 }}>
                <CardContent>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 1 }}>
                    <Typography variant="subtitle1">
                      {row.bracket.name || `Bracket ${row.bracket.bracket_number}`}
                    </Typography>
                    <Chip size="small" variant="outlined"
                      label={WEEK_FORMAT_LABELS[row.bracket.format_type] || row.bracket.format_type} />
                    <Chip size="small" variant="outlined" label={`Bo${row.bracket.best_of_n}`} />
                    <Typography variant="body2" sx={{ ml: 1 }}>
                      {row.player?.name}
                      {row.opponent?.player ? ` vs ${row.opponent.player.name}` : ''}
                      {row.opponent?.team_name ? ` (${row.opponent.team_name})` : ''}
                    </Typography>
                  </Box>

                  <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 1 }}>
                    <WeekConstraints week={row.week} sets={sets} />
                  </Box>

                  {row.selections.length > 0 ? (
                    row.selections.map((sel: any) => (
                      <Box key={sel.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5, flexWrap: 'wrap' }}>
                        {row.max_slots > 1 && <Chip size="small" variant="outlined" label={`Slot ${sel.slot_number}`} />}
                        {sel.deck?.houses && <HouseIcons houses={sel.deck.houses} />}
                        <Typography variant="body2">{sel.deck?.name || 'Unknown deck'}</Typography>
                        {sel.deck?.sas_rating != null && (
                          <Chip size="small" variant="outlined" label={`SAS ${sel.deck.sas_rating}`} />
                        )}
                      </Box>
                    ))
                  ) : (
                    <Typography variant="body2" color="text.secondary">No deck entered yet.</Typography>
                  )}

                  {canSubmit && row.selections.length < row.max_slots && row.player && (
                    <Box sx={{ display: 'flex', gap: 1, mt: 1, flexWrap: 'wrap' }}>
                      <TextField
                        size="small"
                        sx={{ minWidth: 320, flexGrow: 1 }}
                        label={`Deck URL for ${row.player.name}`}
                        placeholder="https://decksofkeyforge.com/decks/..."
                        value={deckUrls[key] || ''}
                        onChange={(e) => setDeckUrls((prev) => ({ ...prev, [key]: e.target.value }))}
                      />
                      <Button
                        variant="outlined"
                        disabled={!deckUrls[key]?.trim()}
                        onClick={() =>
                          act(
                            () => submitDeckSelection(leagueId, row.week.id, {
                              deck_url: (deckUrls[key] || '').trim(),
                              slot_number: row.selections.length + 1,
                              user_id: row.player!.id === user?.id ? undefined : row.player!.id,
                            }).then(() => setDeckUrls((prev) => ({ ...prev, [key]: '' }))),
                            'Deck entered.',
                          )
                        }
                      >
                        Submit
                      </Button>
                    </Box>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </Box>
      )}

      {tab === 3 && (setup.is_admin || setup.is_captain) && (
        <PlayoffSetupPanel
          league={league}
          setup={setup}
          rounds={rounds}
          onAct={act}
          leagueId={leagueId}
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
}: {
  league: LeagueDetail;
  setup: PlayoffSetup;
  rounds: number;
  onAct: (what: () => Promise<unknown>, done: string) => Promise<void>;
  leagueId: number;
}) {
  const drawn = Boolean(setup.config.drawn_at);
  const [advancing, setAdvancing] = useState(setup.config.teams_advancing);
  const [points, setPoints] = useState(setup.config.points_per_round.join(', '));
  const [consolation, setConsolation] = useState(setup.config.consolation_enabled);
  const [consolationPoints, setConsolationPoints] = useState(setup.config.consolation_points);
  const [byePolicy, setByePolicy] = useState(setup.config.bye_policy);
  const [qualifiers, setQualifiers] = useState<number[]>(setup.qualifiers.map((q) => q.team_id));
  const [assignments, setAssignments] = useState<Record<number, number>>(() => {
    const mine: Record<number, number> = {};
    for (const b of setup.brackets) {
      const a = b.assignments.find((x) => x.team_id === setup.my_team_id);
      if (a) mine[b.id] = a.user_id;
    }
    return mine;
  });

  const myTeam = league.teams.find((t) => t.id === setup.my_team_id);

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
        />
      )}

      {setup.my_team_id && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              {myTeam?.name}: who plays in each bracket
            </Typography>
            {drawn && <Alert severity="info" sx={{ mb: 1 }}>Fixed now that the draw is made.</Alert>}
            {setup.brackets.length === 0 && (
              <Typography color="text.secondary">No brackets defined yet.</Typography>
            )}
            {setup.brackets.map((bracket) => (
              <Box key={bracket.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1, flexWrap: 'wrap' }}>
                <Typography variant="body2" sx={{ minWidth: 200 }}>
                  {bracket.name || `Bracket ${bracket.bracket_number}`}
                  {' — '}
                  {WEEK_FORMAT_LABELS[bracket.format_type] || bracket.format_type}
                </Typography>
                <FormControl size="small" sx={{ minWidth: 200 }} disabled={drawn}>
                  <InputLabel>Player</InputLabel>
                  <Select
                    label="Player"
                    value={assignments[bracket.id] || ''}
                    onChange={(e) =>
                      setAssignments((prev) => ({ ...prev, [bracket.id]: Number(e.target.value) }))
                    }
                  >
                    {(myTeam?.members || []).map((m) => (
                      <MenuItem key={m.user.id} value={m.user.id}>{m.user.name}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>
            ))}
            <Button
              variant="contained"
              disabled={drawn || !setup.is_captain}
              onClick={() =>
                onAct(
                  () => setPlayoffAssignments(
                    leagueId,
                    setup.my_team_id!,
                    Object.entries(assignments).map(([bracketId, userId]) => ({
                      bracket_id: Number(bracketId),
                      user_id: Number(userId),
                    })),
                  ),
                  'Assignments saved.',
                )
              }
            >
              Save assignments
            </Button>
            {!setup.is_captain && (
              <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                Only a captain can change these.
              </Typography>
            )}
          </CardContent>
        </Card>
      )}

      {setup.is_admin && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Running the playoffs</Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Button
                variant="contained" disabled={drawn}
                onClick={() => onAct(() => drawPlayoffs(leagueId), 'Brackets drawn.')}
              >
                Draw the brackets
              </Button>
              {Array.from({ length: rounds }, (_, i) => i + 1).map((n) => (
                <Button
                  key={n} variant="outlined" disabled={!drawn}
                  onClick={() => onAct(() => startPlayoffRound(leagueId, n), `Round ${n} opened.`)}
                >
                  Open round {n}
                </Button>
              ))}
            </Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              Opening a round creates a week per bracket and its matches. A later round will not
              open until every result before it is reported and verified.
            </Typography>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}

function BracketEditor({
  setup,
  drawn,
  leagueId,
  onAct,
}: {
  setup: PlayoffSetup;
  drawn: boolean;
  leagueId: number;
  onAct: (what: () => Promise<unknown>, done: string) => Promise<void>;
}) {
  const expected = setup.config.expected_brackets;
  const [rows, setRows] = useState(() =>
    setup.brackets.length > 0
      ? setup.brackets.map((b) => ({ name: b.name || '', format_type: b.format_type, best_of_n: b.best_of_n }))
      : Array.from({ length: expected }, () => ({ name: '', format_type: 'archon_standard', best_of_n: 1 })),
  );

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Brackets ({rows.length} of {expected})
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          One per player on a team, each in its own format.
        </Typography>
        {rows.map((row, index) => (
          <Box key={index} sx={{ display: 'flex', gap: 1, mb: 1, flexWrap: 'wrap', alignItems: 'center' }}>
            <Typography variant="body2" sx={{ width: 24 }}>{index + 1}</Typography>
            <TextField
              size="small" label="Name" sx={{ width: 180 }} disabled={drawn}
              value={row.name}
              onChange={(e) => setRows((prev) => prev.map((r, i) => i === index ? { ...r, name: e.target.value } : r))}
            />
            <FormControl size="small" sx={{ minWidth: 220 }} disabled={drawn}>
              <InputLabel>Format</InputLabel>
              <Select
                label="Format" value={row.format_type}
                onChange={(e) => setRows((prev) => prev.map((r, i) => i === index ? { ...r, format_type: String(e.target.value) } : r))}
              >
                {Object.entries(WEEK_FORMAT_LABELS).map(([value, label]) => (
                  <MenuItem key={value} value={value}>{label}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              size="small" type="number" label="Best of" sx={{ width: 100 }} disabled={drawn}
              value={row.best_of_n}
              onChange={(e) => setRows((prev) => prev.map((r, i) => i === index ? { ...r, best_of_n: parseInt(e.target.value, 10) || 1 } : r))}
            />
          </Box>
        ))}
        <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
          <Button variant="contained" disabled={drawn}
            onClick={() => onAct(() => setPlayoffBrackets(leagueId, rows), 'Brackets saved.')}>
            Save brackets
          </Button>
          <Button disabled={drawn} onClick={() => setRows((prev) => [...prev, { name: '', format_type: 'archon_standard', best_of_n: 1 }])}>
            Add one
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
}
