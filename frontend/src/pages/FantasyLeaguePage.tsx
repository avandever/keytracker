import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
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
  IconButton,
  LinearProgress,
  MenuItem,
  Select,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
  alpha,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import StarIcon from '@mui/icons-material/Star';
import type {
  FantasyLeague,
  FantasyPlayerCost,
  FantasyStandingRow,
  FantasyTeam,
} from '../api/fantasy';
import {
  addFantasyCommissioner,
  removeFantasyCommissioner,
  listFantasyLeagues,
  getFantasyCosts,
  getFantasyLeague,
  getFantasyStandings,
  getMyFantasyTeam,
  regenerateFantasyCosts,
  setFantasyStatus,
  submitFantasyEntry,
  updateFantasyCost,
  withdrawFantasyEntry,
} from '../api/fantasy';
import { useAuth } from '../contexts/AuthContext';
import { useLeagueNumericId } from '../contexts/LeagueContext';
import { formatDeadline } from '../utils/deadlines';

const STATUS_HELP: Record<string, string> = {
  setup: 'The commissioner is still setting player costs. Entries are not open yet.',
  open: 'Entries are open. Rosters stay private until the league locks.',
  locked: 'Rosters are locked and public. Standings update as results are verified.',
  completed: 'This fantasy season has finished.',
};

export default function FantasyLeaguePage() {
  // Scoped to the league this page hangs off, so it is reached from the league
  // rather than a separate section of the site.
  const leagueId = useLeagueNumericId();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  // Which fantasy league of this league's we are showing. A league will
  // normally have one; ?fl= picks among several.
  const [id, setId] = useState<number | null>(null);
  const [siblings, setSiblings] = useState<FantasyLeague[]>([]);
  const [league, setLeague] = useState<FantasyLeague | null>(null);
  const [costs, setCosts] = useState<FantasyPlayerCost[]>([]);
  const [standings, setStandings] = useState<FantasyStandingRow[]>([]);
  const [myTeam, setMyTeam] = useState<FantasyTeam | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [tab, setTab] = useState(0);

  // Entry form
  const [teamName, setTeamName] = useState('');
  const [picks, setPicks] = useState<number[]>([]);
  const [captainId, setCaptainId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [newCommissioner, setNewCommissioner] = useState<
    string | { label: string; id: number } | null
  >(null);

  // Resolve which fantasy league to show before anything else loads.
  useEffect(() => {
    if (!leagueId) return;
    listFantasyLeagues(leagueId)
      .then((rows) => {
        setSiblings(rows);
        const requested = Number(searchParams.get('fl'));
        const chosen =
          rows.find((r) => r.id === requested) ?? rows[0] ?? null;
        setId(chosen ? chosen.id : null);
        if (!chosen) setLoading(false);
      })
      .catch((e) => {
        setError(e.response?.data?.error || e.message);
        setLoading(false);
      });
  }, [leagueId, searchParams]);

  const refresh = useCallback(async () => {
    if (!id) return;
    try {
      const [fl, costRows, standingData] = await Promise.all([
        getFantasyLeague(id),
        getFantasyCosts(id),
        getFantasyStandings(id),
      ]);
      setLeague(fl);
      setCosts(costRows);
      setStandings(standingData.standings);
      if (user) {
        // Non-fatal: a stale session 401s here, and that should read as "not
        // signed in", not as a broken page. The rest of the view is public.
        try {
          const mine = await getMyFantasyTeam(id);
          setMyTeam(mine);
          if (mine) {
            setTeamName(mine.name);
            setPicks((mine.roster || []).map((s) => s.player_user_id));
            setCaptainId(
              (mine.roster || []).find((s) => s.is_captain)?.player_user_id ?? null,
            );
          }
        } catch {
          setMyTeam(null);
        }
      }
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setLoading(false);
    }
  }, [id, user]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const costById = useMemo(
    () => new Map(costs.map((c) => [c.player_user_id, c])),
    [costs],
  );
  const spent = useMemo(
    () => picks.reduce((sum, pid) => sum + (costById.get(pid)?.cost ?? 0), 0),
    [picks, costById],
  );

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }
  if (!league) {
    return (
      <Container maxWidth="md" sx={{ mt: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <IconButton onClick={() => navigate('..')} size="small" sx={{ mr: 1 }}>
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h4">Fantasy League</Typography>
        </Box>
        {error ? (
          <Alert severity="error">{error}</Alert>
        ) : (
          <Alert severity="info">
            This league does not have a fantasy competition yet.
          </Alert>
        )}
      </Container>
    );
  }

  const entriesOpen = league.status === 'open';
  const remaining = league.salary_cap - spent;
  const rosterFull = picks.length === league.roster_size;
  const canSubmit =
    entriesOpen && rosterFull && remaining >= 0 && !!teamName.trim() && captainId !== null;

  const togglePick = (playerId: number) => {
    setPicks((prev) => {
      if (prev.includes(playerId)) {
        if (captainId === playerId) setCaptainId(null);
        return prev.filter((p) => p !== playerId);
      }
      if (prev.length >= league.roster_size) return prev;
      return [...prev, playerId];
    });
  };

  const handleSubmit = async () => {
    if (!canSubmit || captainId === null) return;
    setSubmitting(true);
    setError('');
    setSuccess('');
    try {
      await submitFantasyEntry(league.id, {
        name: teamName.trim(),
        player_user_ids: picks,
        captain_user_id: captainId,
      });
      setSuccess(myTeam ? 'Entry updated.' : 'Entry submitted.');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleWithdraw = async () => {
    setWithdrawOpen(false);
    try {
      await withdrawFantasyEntry(league.id);
      setMyTeam(null);
      setPicks([]);
      setCaptainId(null);
      setTeamName('');
      setSuccess('Entry withdrawn.');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleStatus = async (status: FantasyLeague['status']) => {
    setError('');
    try {
      await setFantasyStatus(league.id, status);
      setSuccess(`Status changed to ${status}.`);
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const renderEntry = () => {
    if (!user) {
      return <Alert severity="info">Sign in to enter a team.</Alert>;
    }
    if (!entriesOpen && !myTeam) {
      return (
        <Alert severity="info">
          {league.status === 'setup'
            ? 'Entries have not opened yet.'
            : 'Entries are closed for this season.'}
        </Alert>
      );
    }
    return (
      <>
        {!entriesOpen && myTeam && (
          <Alert severity="info" sx={{ mb: 2 }}>
            Entries are closed — your roster is locked in.
          </Alert>
        )}
        <TextField
          label="Team name"
          value={teamName}
          onChange={(e) => setTeamName(e.target.value)}
          size="small"
          fullWidth
          disabled={!entriesOpen}
          sx={{ mb: 2 }}
        />

        <Box sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 0.5 }}>
            <Typography variant="subtitle2">
              {picks.length} of {league.roster_size} players
            </Typography>
            <Typography
              variant="body2"
              color={remaining < 0 ? 'error' : 'text.secondary'}
            >
              {spent} of {league.salary_cap} spent — {remaining} left
            </Typography>
            {remaining < 0 && <Chip label="Over cap" size="small" color="error" />}
          </Box>
          <LinearProgress
            variant="determinate"
            value={Math.min(100, (spent / league.salary_cap) * 100)}
            color={remaining < 0 ? 'error' : 'primary'}
            sx={{ height: 6, borderRadius: 3 }}
          />
        </Box>

        {picks.length > 0 && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Captain
            </Typography>
            <Select
              size="small"
              fullWidth
              value={captainId ?? ''}
              onChange={(e) => setCaptainId(Number(e.target.value))}
              disabled={!entriesOpen}
              displayEmpty
            >
              <MenuItem value="" disabled>
                Choose a captain
              </MenuItem>
              {picks.map((pid) => (
                <MenuItem key={pid} value={pid}>
                  {costById.get(pid)?.player_name ?? pid}
                </MenuItem>
              ))}
            </Select>
            <Typography variant="caption" color="text.secondary">
              Your captain scores a bonus point for every win above their cost.
            </Typography>
          </Box>
        )}

        <Typography variant="subtitle2" gutterBottom>
          Players
        </Typography>
        <Table size="small">
          <TableBody>
            {costs.map((c) => {
              const picked = picks.includes(c.player_user_id);
              const affordable = picked || c.cost <= remaining;
              const full = !picked && picks.length >= league.roster_size;
              return (
                <TableRow
                  key={c.player_user_id}
                  hover
                  onClick={() => entriesOpen && togglePick(c.player_user_id)}
                  sx={{
                    cursor: entriesOpen ? 'pointer' : 'default',
                    bgcolor: picked
                      ? (theme) => alpha(theme.palette.primary.main, 0.1)
                      : undefined,
                    opacity: !picked && (!affordable || full) ? 0.5 : 1,
                  }}
                >
                  <TableCell padding="checkbox" sx={{ width: 32 }}>
                    {picked ? '✓' : ''}
                  </TableCell>
                  <TableCell>
                    {c.player_name ?? `User ${c.player_user_id}`}
                    {c.is_new_player && (
                      <Tooltip title="New this season — scoring bonus depends on how many teams draft them">
                        <StarIcon
                          fontSize="inherit"
                          sx={{ ml: 0.5, verticalAlign: 'middle', color: 'warning.main' }}
                        />
                      </Tooltip>
                    )}
                  </TableCell>
                  <TableCell align="right" sx={{ width: 60 }}>
                    {c.cost}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>

        <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
          <Button
            variant="contained"
            disabled={!canSubmit || submitting}
            onClick={handleSubmit}
          >
            {myTeam ? 'Update Entry' : 'Submit Entry'}
          </Button>
          {myTeam && entriesOpen && (
            <Button color="error" onClick={() => setWithdrawOpen(true)}>
              Withdraw
            </Button>
          )}
        </Box>
      </>
    );
  };

  const renderStandings = () => {
    if (!league.rosters_public) {
      return (
        <Alert severity="info">
          Standings appear once the league locks. Until then, publishing them would
          give away the rosters they are computed from.
        </Alert>
      );
    }
    if (standings.length === 0) {
      return <Typography color="text.secondary">No entries.</Typography>;
    }
    return (
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>#</TableCell>
            <TableCell>Team</TableCell>
            <TableCell>Manager</TableCell>
            <TableCell align="right">Wins</TableCell>
            <TableCell align="right">Weekly</TableCell>
            <TableCell align="right">Captain</TableCell>
            {league.scarcity_bonus_enabled && <TableCell align="right">New</TableCell>}
            <TableCell align="right">Cost</TableCell>
            <TableCell align="right">
              <strong>Total</strong>
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {standings.map((row) => (
            <TableRow key={row.team_id}>
              <TableCell>{row.rank}</TableCell>
              <TableCell>
                {row.team_name}
                {row.joined_week_number && (
                  <Tooltip title={`Joined in week ${row.joined_week_number}`}>
                    <Chip label={`W${row.joined_week_number}`} size="small" sx={{ ml: 1 }} />
                  </Tooltip>
                )}
              </TableCell>
              <TableCell>{row.manager_name}</TableCell>
              <TableCell align="right">{row.match_wins}</TableCell>
              <TableCell align="right">{row.weekly_bonus}</TableCell>
              <TableCell align="right">{row.captain_bonus}</TableCell>
              {league.scarcity_bonus_enabled && (
                <TableCell align="right">{row.scarcity_bonus}</TableCell>
              )}
              <TableCell align="right">{row.roster_cost}</TableCell>
              <TableCell align="right">
                <strong>{row.total}</strong>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  };

  const renderTeams = () => {
    const teams = league.teams || [];
    if (teams.length === 0) {
      return <Typography color="text.secondary">No entries yet.</Typography>;
    }
    return (
      <>
        {!league.rosters_public && (
          <Alert severity="info" sx={{ mb: 2 }}>
            Rosters stay private until the league locks, so nobody can draft against
            what everyone else has already picked.
          </Alert>
        )}
        {teams.map((t) => (
          <Card key={t.id} sx={{ mb: 1 }}>
            <CardContent sx={{ py: 1.5 }}>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                <Typography variant="subtitle2">{t.name}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {t.manager_name}
                </Typography>
                {t.roster && (
                  <Chip label={`Cost ${t.roster_cost}`} size="small" variant="outlined" />
                )}
              </Box>
              {t.roster ? (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  {t.roster
                    .map(
                      (s) =>
                        `${s.player_name}${s.is_captain ? ' (C)' : ''} ${s.cost_at_draft}`,
                    )
                    .join(' · ')}
                </Typography>
              ) : (
                <Typography variant="caption" color="text.secondary">
                  Roster hidden until lock
                </Typography>
              )}
            </CardContent>
          </Card>
        ))}
      </>
    );
  };

  const renderCommissioner = () => (
    <>
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="subtitle2" gutterBottom>
            Status: {league.status}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {STATUS_HELP[league.status]}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {league.status === 'setup' && (
              <Button variant="contained" onClick={() => handleStatus('open')}>
                Open for Entries
              </Button>
            )}
            {league.status === 'open' && (
              <>
                <Button variant="contained" onClick={() => handleStatus('locked')}>
                  Lock Rosters
                </Button>
                <Button onClick={() => handleStatus('setup')}>Back to Setup</Button>
              </>
            )}
            {league.status === 'locked' && (
              <Button onClick={() => handleStatus('completed')}>Mark Completed</Button>
            )}
          </Box>
          {league.status === 'open' && (
            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
              Locking publishes every roster and freezes the scoring rules. It cannot be
              undone.
            </Typography>
          )}
        </CardContent>
      </Card>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="subtitle2" gutterBottom>
            Commissioners
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
            {league.commissioners.map((c) => (
              <Chip
                key={c.user_id}
                label={`${c.name ?? c.user_id}${c.is_creator ? ' (creator)' : ''}`}
                size="small"
                onDelete={
                  c.is_creator
                    ? undefined
                    : async () => {
                        setError('');
                        try {
                          setLeague(await removeFantasyCommissioner(league.id, c.user_id));
                          setSuccess('Co-commissioner removed.');
                        } catch (e: any) {
                          setError(e.response?.data?.error || e.message);
                        }
                      }
                }
              />
            ))}
          </Box>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
            <Autocomplete
              freeSolo
              size="small"
              sx={{ flex: 1 }}
              options={costs.map((c) => ({
                label: c.player_name ?? String(c.player_user_id),
                id: c.player_user_id,
              }))}
              value={newCommissioner}
              onChange={(_, v) => setNewCommissioner(v)}
              isOptionEqualToValue={(o, v) =>
                typeof o !== 'string' && typeof v !== 'string' && o.id === v.id
              }
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Add a co-commissioner"
                  helperText="A league player by name, or any user's id"
                />
              )}
            />
            <Button
              sx={{ mt: 0.5 }}
              onClick={async () => {
                // Either a picked player, or a raw id typed for someone who is
                // not playing in the league.
                const picked =
                  typeof newCommissioner === 'string'
                    ? parseInt(newCommissioner, 10)
                    : newCommissioner?.id;
                if (!picked || isNaN(picked)) {
                  setError('Pick a player or enter a numeric user id');
                  return;
                }
                setError('');
                try {
                  setLeague(await addFantasyCommissioner(league.id, picked));
                  setNewCommissioner(null);
                  setSuccess('Co-commissioner added.');
                } catch (e: any) {
                  setError(e.response?.data?.error || e.message);
                }
              }}
            >
              Add
            </Button>
          </Box>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="subtitle2">Player Costs ({costs.length})</Typography>
            {league.status === 'setup' && (
              <Button
                size="small"
                onClick={async () => {
                  setError('');
                  try {
                    setCosts(await regenerateFantasyCosts(league.id));
                    setSuccess('Costs regenerated from the source season.');
                  } catch (e: any) {
                    setError(e.response?.data?.error || e.message);
                  }
                }}
              >
                Regenerate
              </Button>
            )}
          </Box>
          {league.status !== 'setup' && (
            <Typography variant="caption" color="text.secondary">
              Costs can only be changed during setup.
            </Typography>
          )}
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Player</TableCell>
                <TableCell align="right">Prior wins</TableCell>
                <TableCell align="right">Cost</TableCell>
                <TableCell align="center">New</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {costs.map((c) => (
                <TableRow key={c.player_user_id}>
                  <TableCell>{c.player_name}</TableCell>
                  <TableCell align="right">
                    {c.source_wins === null ? '—' : c.source_wins}
                  </TableCell>
                  <TableCell align="right" sx={{ width: 90 }}>
                    {league.status === 'setup' ? (
                      <TextField
                        size="small"
                        type="number"
                        defaultValue={c.cost}
                        inputProps={{ style: { textAlign: 'right' }, min: 0 }}
                        sx={{ width: 70 }}
                        onBlur={async (e) => {
                          const next = parseInt(e.target.value, 10);
                          if (isNaN(next) || next === c.cost) return;
                          try {
                            await updateFantasyCost(league.id, c.player_user_id, {
                              cost: next,
                            });
                            setCosts(await getFantasyCosts(league.id));
                          } catch (err: any) {
                            setError(err.response?.data?.error || err.message);
                          }
                        }}
                      />
                    ) : (
                      c.cost
                    )}
                  </TableCell>
                  <TableCell align="center">
                    {c.is_new_player ? <StarIcon fontSize="inherit" color="warning" /> : ''}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </>
  );

  const tabs = ['Standings', 'My Entry', 'Teams'];
  if (league.viewer_is_commissioner) tabs.push('Commissioner');

  return (
    <Container maxWidth="md" sx={{ mt: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
        {/* Up to the league this fantasy competition belongs to. */}
        <IconButton onClick={() => navigate('..')} size="small" sx={{ mr: 1 }}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h4">{league.name}</Typography>
      </Box>
      {siblings.length > 1 && (
        <Box sx={{ display: 'flex', gap: 1, mb: 1, flexWrap: 'wrap' }}>
          {siblings.map((s) => (
            <Chip
              key={s.id}
              label={s.name}
              size="small"
              color={s.id === league.id ? 'primary' : 'default'}
              onClick={() => setId(s.id)}
            />
          ))}
        </Box>
      )}
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 2 }}>
        <Chip label={league.status} size="small" />
        <Typography variant="body2" color="text.secondary">
          {league.league_name} · {league.roster_size} players · cap {league.salary_cap} ·{' '}
          {league.team_count} {league.team_count === 1 ? 'entry' : 'entries'}
        </Typography>
        {league.roster_lock_at && (
          <Chip
            label={`Locks ${formatDeadline(league.roster_lock_at)}`}
            size="small"
            variant="outlined"
            color="warning"
          />
        )}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>
          {success}
        </Alert>
      )}

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        {tabs.map((label) => (
          <Tab key={label} label={label} />
        ))}
      </Tabs>

      {tab === 0 && renderStandings()}
      {tab === 1 && renderEntry()}
      {tab === 2 && renderTeams()}
      {tab === 3 && league.viewer_is_commissioner && renderCommissioner()}

      <Dialog open={withdrawOpen} onClose={() => setWithdrawOpen(false)}>
        <DialogTitle>Withdraw your entry?</DialogTitle>
        <DialogContent>
          <Typography>
            This deletes your roster. You can enter again while entries remain open.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setWithdrawOpen(false)}>Cancel</Button>
          <Button color="error" variant="contained" onClick={handleWithdraw}>
            Withdraw
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
