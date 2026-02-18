import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  Container,
  Typography,
  CircularProgress,
  Alert,
  Box,
  Button,
  TextField,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  ListItemButton,
  Collapse,
  Checkbox,
  FormControlLabel,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import {
  getLeague,
  updateLeague,
  createTeam,
  deleteTeam,
  assignCaptain,
  startDraft,
  createWeek,
  openDeckSelection,
  generateMatchups,
  publishWeek,
  getSets,
} from '../api/leagues';
import { useAuth } from '../contexts/AuthContext';
import type { LeagueDetail, KeyforgeSetInfo, LeagueWeek } from '../types';

const FORMAT_LABELS: Record<string, string> = {
  archon_standard: 'Archon Standard',
  triad: 'Triad',
  sealed_archon: 'Sealed Archon',
};

const STATUS_COLORS: Record<string, 'default' | 'info' | 'warning' | 'success'> = {
  setup: 'default',
  deck_selection: 'info',
  pairing: 'warning',
  published: 'success',
  completed: 'success',
};

export default function LeagueAdminPage() {
  const { leagueId } = useParams<{ leagueId: string }>();
  useAuth();
  const [league, setLeague] = useState<LeagueDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Settings form
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editFee, setEditFee] = useState('');
  const [editTeamSize, setEditTeamSize] = useState('');
  const [editNumTeams, setEditNumTeams] = useState('');

  // Team creation
  const [newTeamName, setNewTeamName] = useState('');

  // Captain assignment
  const [captainSelections, setCaptainSelections] = useState<Record<number, number>>({});

  // Start draft dialog
  const [draftDialogOpen, setDraftDialogOpen] = useState(false);

  // Week creation
  const [weekDialogOpen, setWeekDialogOpen] = useState(false);
  const [weekFormat, setWeekFormat] = useState('archon_standard');
  const [weekBestOf, setWeekBestOf] = useState('1');
  const [weekMaxSas, setWeekMaxSas] = useState('');
  const [weekAllowedSets, setWeekAllowedSets] = useState<number[]>([]);
  // Triad-specific
  const [weekCombinedMaxSas, setWeekCombinedMaxSas] = useState('');
  const [weekSetDiversity, setWeekSetDiversity] = useState(false);
  const [weekHouseDiversity, setWeekHouseDiversity] = useState(false);
  const [availableSets, setAvailableSets] = useState<KeyforgeSetInfo[]>([]);

  // Week expanded
  const [expandedWeeks, setExpandedWeeks] = useState<Record<number, boolean>>({});

  const refresh = useCallback(() => {
    if (!leagueId) return;
    getLeague(parseInt(leagueId, 10))
      .then((l) => {
        setLeague(l);
        setEditName(l.name);
        setEditDescription(l.description || '');
        setEditFee(l.fee_amount != null ? String(l.fee_amount) : '');
        setEditTeamSize(String(l.team_size));
        setEditNumTeams(String(l.num_teams));
      })
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    getSets().then(setAvailableSets).catch(() => {});
  }, []);

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (!league) return <Container sx={{ mt: 3 }}><Alert severity="error">{error || 'League not found'}</Alert></Container>;
  if (!league.is_admin) return <Container sx={{ mt: 3 }}><Alert severity="error">Admin access required</Alert></Container>;

  const isSetup = league.status === 'setup';
  const isActive = league.status === 'active';

  const handleSaveSettings = async () => {
    setError('');
    setSuccess('');
    try {
      const updated = await updateLeague(league.id, {
        name: editName,
        description: editDescription,
        fee_amount: editFee ? parseFloat(editFee) : null,
        team_size: parseInt(editTeamSize, 10),
        num_teams: parseInt(editNumTeams, 10),
      });
      setLeague({ ...league, ...updated });
      setSuccess('Settings saved');
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleCreateTeam = async () => {
    if (!newTeamName.trim()) return;
    setError('');
    try {
      await createTeam(league.id, newTeamName.trim());
      setNewTeamName('');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleDeleteTeam = async (teamId: number) => {
    setError('');
    try {
      await deleteTeam(league.id, teamId);
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleAssignCaptain = async (teamId: number) => {
    const userId = captainSelections[teamId];
    if (!userId) return;
    setError('');
    try {
      await assignCaptain(league.id, teamId, userId);
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleStartDraft = async () => {
    setError('');
    setDraftDialogOpen(false);
    try {
      await startDraft(league.id);
      refresh();
      setSuccess('Draft started!');
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleCreateWeek = async () => {
    setError('');
    setWeekDialogOpen(false);
    try {
      await createWeek(league.id, {
        format_type: weekFormat,
        best_of_n: parseInt(weekBestOf, 10) || 1,
        max_sas: weekMaxSas ? parseInt(weekMaxSas, 10) : null,
        allowed_sets: weekAllowedSets.length > 0 ? weekAllowedSets : null,
        combined_max_sas: weekCombinedMaxSas ? parseInt(weekCombinedMaxSas, 10) : null,
        set_diversity: weekSetDiversity || undefined,
        house_diversity: weekHouseDiversity || undefined,
      });
      setSuccess('Week created!');
      setWeekFormat('archon_standard');
      setWeekBestOf('1');
      setWeekMaxSas('');
      setWeekAllowedSets([]);
      setWeekCombinedMaxSas('');
      setWeekSetDiversity(false);
      setWeekHouseDiversity(false);
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleWeekAction = async (weekId: number, action: string) => {
    setError('');
    setSuccess('');
    try {
      if (action === 'open_deck_selection') {
        await openDeckSelection(league.id, weekId);
        setSuccess('Deck selection opened');
      } else if (action === 'generate_matchups') {
        await generateMatchups(league.id, weekId);
        setSuccess('Matchups generated');
      } else if (action === 'publish') {
        await publishWeek(league.id, weekId);
        setSuccess('Week published');
      }
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const toggleWeekExpanded = (weekId: number) => {
    setExpandedWeeks((prev) => ({ ...prev, [weekId]: !prev[weekId] }));
  };

  // Get captain IDs so we can exclude them from captain dropdown for other teams
  const assignedCaptainIds = new Set(
    league.teams.flatMap((t) => t.members.filter((m) => m.is_captain).map((m) => m.user.id))
  );

  const toggleSet = (setNumber: number) => {
    setWeekAllowedSets((prev) =>
      prev.includes(setNumber) ? prev.filter((s) => s !== setNumber) : [...prev, setNumber]
    );
  };

  const renderWeekActions = (week: LeagueWeek) => {
    switch (week.status) {
      case 'setup':
        return (
          <Button size="small" variant="contained" onClick={() => handleWeekAction(week.id, 'open_deck_selection')}>
            Open Deck Selection
          </Button>
        );
      case 'deck_selection':
        return (
          <Button size="small" variant="contained" color="warning" onClick={() => handleWeekAction(week.id, 'generate_matchups')}>
            Generate Matchups
          </Button>
        );
      case 'pairing':
        return (
          <Button size="small" variant="contained" color="success" onClick={() => handleWeekAction(week.id, 'publish')}>
            Publish Pairings
          </Button>
        );
      default:
        return null;
    }
  };

  return (
    <Container maxWidth="md" sx={{ mt: 3 }}>
      <Typography variant="h4" gutterBottom>Admin: {league.name}</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      {/* League settings */}
      {isSetup && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>League Settings</Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <TextField label="Name" value={editName} onChange={(e) => setEditName(e.target.value)} />
              <TextField label="Description" value={editDescription} onChange={(e) => setEditDescription(e.target.value)} multiline rows={2} />
              <TextField label="Entry Fee" value={editFee} onChange={(e) => setEditFee(e.target.value)} type="number" inputProps={{ step: '0.01', min: '0' }} />
              <TextField label="Team Size" value={editTeamSize} onChange={(e) => setEditTeamSize(e.target.value)} type="number" inputProps={{ min: '2' }} />
              <TextField label="Number of Teams" value={editNumTeams} onChange={(e) => setEditNumTeams(e.target.value)} type="number" inputProps={{ min: '2' }} />
              <Button variant="contained" onClick={handleSaveSettings}>Save Settings</Button>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Team management */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>Teams ({league.teams.length}/{league.num_teams})</Typography>
          {isSetup && league.teams.length < league.num_teams && (
            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
              <TextField
                label="Team Name"
                value={newTeamName}
                onChange={(e) => setNewTeamName(e.target.value)}
                size="small"
              />
              <Button variant="contained" onClick={handleCreateTeam}>Add Team</Button>
            </Box>
          )}
          {league.teams.map((team) => {
            const captain = team.members.find((m) => m.is_captain);
            return (
              <Box key={team.id} sx={{ mb: 2, p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="subtitle1">{team.name}</Typography>
                  {isSetup && (
                    <IconButton size="small" onClick={() => handleDeleteTeam(team.id)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  )}
                </Box>
                {captain ? (
                  <Typography variant="body2" color="text.secondary">
                    Captain: {captain.user.name}
                  </Typography>
                ) : (
                  isSetup && (
                    <Box sx={{ display: 'flex', gap: 1, mt: 1, alignItems: 'center' }}>
                      <FormControl size="small" sx={{ minWidth: 200 }}>
                        <InputLabel>Assign Captain</InputLabel>
                        <Select
                          value={captainSelections[team.id] || ''}
                          label="Assign Captain"
                          onChange={(e) => setCaptainSelections({ ...captainSelections, [team.id]: e.target.value as number })}
                        >
                          {league.signups
                            .filter((s) => !assignedCaptainIds.has(s.user.id))
                            .map((s) => (
                              <MenuItem key={s.user.id} value={s.user.id}>
                                {s.user.name}
                              </MenuItem>
                            ))}
                        </Select>
                      </FormControl>
                      <Button size="small" variant="outlined" onClick={() => handleAssignCaptain(team.id)}>
                        Assign
                      </Button>
                    </Box>
                  )
                )}
                {team.members.length > 0 && (
                  <List dense>
                    {team.members.map((m) => (
                      <ListItem key={m.id} sx={{ py: 0 }}>
                        <ListItemAvatar>
                          <Avatar src={m.user.avatar_url || undefined} sx={{ width: 24, height: 24 }}>
                            {m.user.name?.[0]}
                          </Avatar>
                        </ListItemAvatar>
                        <ListItemText
                          primary={`${m.user.name}${m.is_captain ? ' (Captain)' : ''}`}
                        />
                      </ListItem>
                    ))}
                  </List>
                )}
              </Box>
            );
          })}
        </CardContent>
      </Card>

      {/* Signup list */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>Signups ({league.signups.length})</Typography>
          <List dense>
            {league.signups.map((s) => (
              <ListItem key={s.id}>
                <ListItemAvatar>
                  <Avatar src={s.user.avatar_url || undefined} sx={{ width: 28, height: 28 }}>
                    {s.user.name?.[0]}
                  </Avatar>
                </ListItemAvatar>
                <ListItemText primary={s.user.name} secondary={`#${s.signup_order} - ${s.status}`} />
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>

      {/* Start draft */}
      {isSetup && (
        <Box sx={{ mb: 3 }}>
          <Button variant="contained" color="warning" onClick={() => setDraftDialogOpen(true)}>
            Start Draft
          </Button>
        </Box>
      )}

      {/* Weeks management */}
      {isActive && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">Weeks ({league.weeks?.length || 0})</Typography>
              <Button variant="contained" size="small" onClick={() => setWeekDialogOpen(true)}>
                Add Week
              </Button>
            </Box>
            {(league.weeks || []).map((week) => (
              <Box key={week.id} sx={{ mb: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                <ListItemButton onClick={() => toggleWeekExpanded(week.id)} sx={{ py: 1 }}>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flex: 1 }}>
                    <Typography variant="subtitle1">Week {week.week_number}</Typography>
                    <Chip label={FORMAT_LABELS[week.format_type] || week.format_type} size="small" />
                    <Chip label={week.status.replace('_', ' ')} size="small" color={STATUS_COLORS[week.status] || 'default'} />
                    <Typography variant="body2" color="text.secondary">
                      Bo{week.best_of_n}
                    </Typography>
                    {week.max_sas && (
                      <Typography variant="body2" color="text.secondary">
                        Max SAS: {week.max_sas}
                      </Typography>
                    )}
                  </Box>
                  {expandedWeeks[week.id] ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </ListItemButton>
                <Collapse in={expandedWeeks[week.id]}>
                  <Box sx={{ p: 2, pt: 0 }}>
                    {/* Week actions */}
                    <Box sx={{ mb: 2 }}>
                      {renderWeekActions(week)}
                    </Box>

                    {/* Deck selections summary */}
                    {week.deck_selections.length > 0 && (
                      <Box sx={{ mb: 2 }}>
                        <Typography variant="subtitle2" gutterBottom>Deck Selections ({week.deck_selections.length})</Typography>
                        {week.deck_selections.map((ds) => (
                          <Typography key={ds.id} variant="body2" color="text.secondary">
                            User #{ds.user_id} slot {ds.slot_number}: {ds.deck?.name || 'Unknown'}
                            {ds.deck?.sas_rating != null && ` (SAS: ${ds.deck.sas_rating})`}
                          </Typography>
                        ))}
                      </Box>
                    )}

                    {/* Matchups */}
                    {week.matchups.length > 0 && (
                      <Box>
                        <Typography variant="subtitle2" gutterBottom>Matchups</Typography>
                        {week.matchups.map((m) => (
                          <Box key={m.id} sx={{ mb: 1, p: 1, bgcolor: 'action.hover', borderRadius: 1 }}>
                            <Typography variant="body2" fontWeight="bold">
                              {m.team1.name} vs {m.team2.name}
                            </Typography>
                            {m.player_matchups.map((pm) => (
                              <Typography key={pm.id} variant="body2" color="text.secondary" sx={{ ml: 2 }}>
                                {pm.player1.name} vs {pm.player2.name}
                                {pm.games.length > 0 && ` (${pm.games.length} game${pm.games.length !== 1 ? 's' : ''} played)`}
                              </Typography>
                            ))}
                          </Box>
                        ))}
                      </Box>
                    )}
                  </Box>
                </Collapse>
              </Box>
            ))}
          </CardContent>
        </Card>
      )}

      <Dialog open={draftDialogOpen} onClose={() => setDraftDialogOpen(false)}>
        <DialogTitle>Start Draft?</DialogTitle>
        <DialogContent>
          <Typography>
            This will transition the league to drafting mode. Make sure all teams have captains assigned.
            Players beyond available draft spots will be waitlisted.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDraftDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleStartDraft} variant="contained" color="warning">Start Draft</Button>
        </DialogActions>
      </Dialog>

      {/* Add Week dialog */}
      <Dialog open={weekDialogOpen} onClose={() => setWeekDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Week</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <FormControl fullWidth>
              <InputLabel>Format</InputLabel>
              <Select value={weekFormat} label="Format" onChange={(e) => setWeekFormat(e.target.value)}>
                <MenuItem value="archon_standard">Archon Standard</MenuItem>
                <MenuItem value="triad">Triad</MenuItem>
                <MenuItem value="sealed_archon">Sealed Archon</MenuItem>
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>Best of</InputLabel>
              <Select value={weekBestOf} label="Best of" onChange={(e) => setWeekBestOf(e.target.value)}>
                <MenuItem value="1">Best of 1</MenuItem>
                <MenuItem value="3">Best of 3</MenuItem>
                <MenuItem value="5">Best of 5</MenuItem>
              </Select>
            </FormControl>
            <TextField
              label="Max SAS (optional)"
              value={weekMaxSas}
              onChange={(e) => setWeekMaxSas(e.target.value)}
              type="number"
            />
            {weekFormat === 'triad' && (
              <>
                <TextField
                  label="Combined Max SAS (optional)"
                  value={weekCombinedMaxSas}
                  onChange={(e) => setWeekCombinedMaxSas(e.target.value)}
                  type="number"
                  helperText="Sum of all 3 decks' SAS must be at or below this"
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={weekSetDiversity}
                      onChange={(e) => setWeekSetDiversity(e.target.checked)}
                    />
                  }
                  label="Set diversity (no two decks from same expansion)"
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={weekHouseDiversity}
                      onChange={(e) => setWeekHouseDiversity(e.target.checked)}
                    />
                  }
                  label="House diversity (no two decks share a house)"
                />
              </>
            )}
            {availableSets.length > 0 && (
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Allowed Sets {weekAllowedSets.length > 0 ? `(${weekAllowedSets.length} selected)` : '(all)'}
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {availableSets.map((s) => (
                    <Chip
                      key={s.number}
                      label={s.shortname}
                      size="small"
                      variant={weekAllowedSets.includes(s.number) ? 'filled' : 'outlined'}
                      color={weekAllowedSets.includes(s.number) ? 'primary' : 'default'}
                      onClick={() => toggleSet(s.number)}
                    />
                  ))}
                </Box>
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setWeekDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleCreateWeek} variant="contained">Create Week</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
