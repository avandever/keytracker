import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
  Tab,
  Tabs,
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
  reassignMember,
  startDraft,
  createWeek,
  openDeckSelection,
  generateMatchups,
  publishWeek,
  generateSealedPools,
  generateTeamPairings,
  generatePlayerMatchups,
  getSets,
  deleteLeague,
  deleteWeek,
} from '../api/leagues';
import { useAuth } from '../contexts/AuthContext';
import WeekConstraints from '../components/WeekConstraints';
import type { LeagueDetail, KeyforgeSetInfo, LeagueWeek } from '../types';

const FORMAT_LABELS: Record<string, string> = {
  archon_standard: 'Archon Standard',
  triad: 'Triad',
  sealed_archon: 'Sealed Archon',
};

const STATUS_COLORS: Record<string, 'default' | 'info' | 'warning' | 'success'> = {
  setup: 'default',
  deck_selection: 'info',
  team_paired: 'info',
  pairing: 'warning',
  published: 'success',
  completed: 'success',
};

export default function LeagueAdminPage() {
  const { leagueId } = useParams<{ leagueId: string }>();
  const navigate = useNavigate();
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

  // Member reassignment: key is `${teamId}-${userId}`, value is the new user id
  const [reassignSelections, setReassignSelections] = useState<Record<string, number>>({});
  const [reassigningMember, setReassigningMember] = useState<string | null>(null);

  // Start draft dialog
  const [draftDialogOpen, setDraftDialogOpen] = useState(false);

  // Week creation
  const [weekDialogOpen, setWeekDialogOpen] = useState(false);
  const [weekName, setWeekName] = useState('');
  const [weekFormat, setWeekFormat] = useState('archon_standard');
  const [weekBestOf, setWeekBestOf] = useState('1');
  const [weekMaxSas, setWeekMaxSas] = useState('');
  const [weekAllowedSets, setWeekAllowedSets] = useState<number[]>([]);
  // Triad-specific
  const [weekCombinedMaxSas, setWeekCombinedMaxSas] = useState('');
  const [weekSetDiversity, setWeekSetDiversity] = useState(false);
  const [weekHouseDiversity, setWeekHouseDiversity] = useState(false);
  // Sealed-specific
  const [weekDecksPerPlayer, setWeekDecksPerPlayer] = useState('4');
  const [availableSets, setAvailableSets] = useState<KeyforgeSetInfo[]>([]);

  // Week expanded
  const [expandedWeeks, setExpandedWeeks] = useState<Record<number, boolean>>({});

  // Tabs
  const [activeTab, setActiveTab] = useState(0);

  // Delete dialogs
  const [deleteLeagueDialogOpen, setDeleteLeagueDialogOpen] = useState(false);
  const [deleteWeekId, setDeleteWeekId] = useState<number | null>(null);

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

  const handleReassignMember = async (teamId: number, memberUserId: number) => {
    const key = `${teamId}-${memberUserId}`;
    const newUserId = reassignSelections[key];
    if (!newUserId) return;
    setError('');
    try {
      await reassignMember(league.id, teamId, memberUserId, newUserId);
      setReassigningMember(null);
      setReassignSelections((prev) => ({ ...prev, [key]: 0 }));
      setSuccess('Member reassigned');
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
        name: weekName.trim() || undefined,
        format_type: weekFormat,
        best_of_n: parseInt(weekBestOf, 10) || 1,
        max_sas: weekMaxSas ? parseInt(weekMaxSas, 10) : null,
        allowed_sets: weekAllowedSets.length > 0 ? weekAllowedSets : null,
        combined_max_sas: weekCombinedMaxSas ? parseInt(weekCombinedMaxSas, 10) : null,
        set_diversity: weekSetDiversity || undefined,
        house_diversity: weekHouseDiversity || undefined,
        decks_per_player: weekFormat === 'sealed_archon' ? parseInt(weekDecksPerPlayer, 10) || 4 : null,
      });
      setSuccess('Week created!');
      setWeekName('');
      setWeekFormat('archon_standard');
      setWeekBestOf('1');
      setWeekMaxSas('');
      setWeekAllowedSets([]);
      setWeekCombinedMaxSas('');
      setWeekSetDiversity(false);
      setWeekHouseDiversity(false);
      setWeekDecksPerPlayer('4');
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
      } else if (action === 'generate_team_pairings') {
        await generateTeamPairings(league.id, weekId);
        setSuccess('Team pairings generated');
      } else if (action === 'generate_player_matchups') {
        await generatePlayerMatchups(league.id, weekId);
        setSuccess('Player matchups generated');
      } else if (action === 'publish') {
        await publishWeek(league.id, weekId);
        setSuccess('Week published');
      } else if (action === 'generate_sealed_pools') {
        await generateSealedPools(league.id, weekId);
        setSuccess('Sealed pools generated!');
      }
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleDeleteLeague = async () => {
    setDeleteLeagueDialogOpen(false);
    setError('');
    try {
      await deleteLeague(league.id);
      navigate('/leagues');
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleDeleteWeek = async (weekId: number) => {
    setDeleteWeekId(null);
    setError('');
    try {
      await deleteWeek(league.id, weekId);
      setSuccess('Week deleted');
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

  // All user IDs currently on teams
  const allTeamMemberIds = new Set(
    league.teams.flatMap((t) => t.members.map((m) => m.user.id))
  );

  // Signed-up users not on any team (available for reassignment)
  const availableForReassign = league.signups.filter((s) => !allTeamMemberIds.has(s.user.id));

  const toggleSet = (setNumber: number) => {
    setWeekAllowedSets((prev) =>
      prev.includes(setNumber) ? prev.filter((s) => s !== setNumber) : [...prev, setNumber]
    );
  };

  const renderWeekActions = (week: LeagueWeek) => {
    const actions: React.ReactNode[] = [];

    // Sealed pool generation
    if (week.format_type === 'sealed_archon' && !week.sealed_pools_generated &&
        (week.status === 'setup' || week.status === 'deck_selection')) {
      actions.push(
        <Button key="sealed" size="small" variant="contained" color="secondary"
          onClick={() => handleWeekAction(week.id, 'generate_sealed_pools')}>
          Generate Sealed Pools
        </Button>
      );
    }

    switch (week.status) {
      case 'setup':
        actions.push(
          <Button key="open" size="small" variant="contained" onClick={() => handleWeekAction(week.id, 'open_deck_selection')}>
            Open Deck Selection
          </Button>
        );
        actions.push(
          <Button key="delete" size="small" variant="outlined" color="error" onClick={() => setDeleteWeekId(week.id)}>
            Delete Week
          </Button>
        );
        break;
      case 'deck_selection':
        actions.push(
          <Button key="team-pairings" size="small" variant="contained" color="warning" onClick={() => handleWeekAction(week.id, 'generate_team_pairings')}>
            Generate Team Pairings
          </Button>
        );
        break;
      case 'team_paired':
        actions.push(
          <Button key="player-matchups" size="small" variant="contained" color="warning" onClick={() => handleWeekAction(week.id, 'generate_player_matchups')}>
            Generate Player Matchups
          </Button>
        );
        break;
      case 'pairing':
        actions.push(
          <Button key="publish" size="small" variant="contained" color="success" onClick={() => handleWeekAction(week.id, 'publish')}>
            Publish Pairings
          </Button>
        );
        break;
    }

    return actions.length > 0 ? <Box sx={{ display: 'flex', gap: 1 }}>{actions}</Box> : null;
  };

  return (
    <Container maxWidth="md" sx={{ mt: 3 }}>
      <Typography variant="h4" gutterBottom>Admin: {league.name}</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      <Tabs
        value={activeTab}
        onChange={(_, v) => setActiveTab(v)}
        sx={{ mb: 2 }}
        variant="scrollable"
        scrollButtons="auto"
      >
        <Tab label="Teams" />
        <Tab label={`Signups (${league.signups.length})`} />
        <Tab label={`Weeks (${league.weeks?.length || 0})`} />
      </Tabs>

      {/* Teams tab */}
      {activeTab === 0 && (
        <>
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
                    {captain && (
                      <Typography variant="body2" color="text.secondary">
                        Captain: {captain.user.name}
                      </Typography>
                    )}
                    <Box sx={{ display: 'flex', gap: 1, mt: 1, alignItems: 'center' }}>
                      <FormControl size="small" sx={{ minWidth: 200 }}>
                        <InputLabel>{captain ? 'Reassign Captain' : 'Assign Captain'}</InputLabel>
                        <Select
                          value={captainSelections[team.id] || ''}
                          label={captain ? 'Reassign Captain' : 'Assign Captain'}
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
                    {team.members.length > 0 && (
                      <List dense>
                        {team.members.map((m) => {
                          const reassignKey = `${team.id}-${m.user.id}`;
                          const isReassigning = reassigningMember === reassignKey;
                          return (
                            <ListItem key={m.id} sx={{ py: 0.5, flexWrap: 'wrap' }}>
                              <ListItemAvatar>
                                <Avatar src={m.user.avatar_url || undefined} sx={{ width: 24, height: 24 }}>
                                  {m.user.name?.[0]}
                                </Avatar>
                              </ListItemAvatar>
                              <ListItemText
                                primary={`${m.user.name}${m.is_captain ? ' (Captain)' : ''}`}
                              />
                              {!isReassigning ? (
                                <Button
                                  size="small"
                                  variant="text"
                                  onClick={() => setReassigningMember(reassignKey)}
                                >
                                  Replace
                                </Button>
                              ) : (
                                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', width: '100%', ml: 7, mt: 0.5 }}>
                                  <FormControl size="small" sx={{ minWidth: 180 }}>
                                    <InputLabel>Replace with</InputLabel>
                                    <Select
                                      value={reassignSelections[reassignKey] || ''}
                                      label="Replace with"
                                      onChange={(e) => setReassignSelections((prev) => ({
                                        ...prev,
                                        [reassignKey]: e.target.value as number,
                                      }))}
                                    >
                                      {availableForReassign.map((s) => (
                                        <MenuItem key={s.user.id} value={s.user.id}>
                                          {s.user.name}
                                        </MenuItem>
                                      ))}
                                    </Select>
                                  </FormControl>
                                  <Button
                                    size="small"
                                    variant="outlined"
                                    onClick={() => handleReassignMember(team.id, m.user.id)}
                                    disabled={!reassignSelections[reassignKey]}
                                  >
                                    Confirm
                                  </Button>
                                  <Button
                                    size="small"
                                    onClick={() => setReassigningMember(null)}
                                  >
                                    Cancel
                                  </Button>
                                </Box>
                              )}
                            </ListItem>
                          );
                        })}
                      </List>
                    )}
                  </Box>
                );
              })}
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

          {/* Delete league button - test leagues only */}
          {league.is_test && (
            <Box sx={{ mt: 3, mb: 3 }}>
              <Button variant="outlined" color="error" onClick={() => setDeleteLeagueDialogOpen(true)}>
                Delete League
              </Button>
            </Box>
          )}
        </>
      )}

      {/* Signups tab */}
      {activeTab === 1 && (
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
      )}

      {/* Weeks tab */}
      {activeTab === 2 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">Weeks ({league.weeks?.length || 0})</Typography>
              {isActive && (
                <Button variant="contained" size="small" onClick={() => setWeekDialogOpen(true)}>
                  Add Week
                </Button>
              )}
            </Box>
            {!isActive && (league.weeks || []).length === 0 && (
              <Typography color="text.secondary">Weeks can be added after the draft is complete.</Typography>
            )}
            {(league.weeks || []).map((week) => (
              <Box key={week.id} sx={{ mb: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                <ListItemButton onClick={() => toggleWeekExpanded(week.id)} sx={{ py: 1 }}>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flex: 1, flexWrap: 'wrap' }}>
                    <Typography variant="subtitle1">{week.name || `Week ${week.week_number}`}</Typography>
                    <Chip label={FORMAT_LABELS[week.format_type] || week.format_type} size="small" />
                    <Chip label={week.status.replace('_', ' ')} size="small" color={STATUS_COLORS[week.status] || 'default'} />
                    <Typography variant="body2" color="text.secondary">
                      Bo{week.best_of_n}
                    </Typography>
                    <WeekConstraints week={week} />
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
            <TextField
              label="Week Name (optional)"
              value={weekName}
              onChange={(e) => setWeekName(e.target.value)}
              placeholder="e.g. Round 1, Finals, etc."
            />
            <FormControl fullWidth>
              <InputLabel>Format</InputLabel>
              <Select value={weekFormat} label="Format" onChange={(e) => {
                const fmt = e.target.value;
                setWeekFormat(fmt);
                if (fmt === 'triad') setWeekBestOf('3');
              }}>
                <MenuItem value="archon_standard">Archon Standard</MenuItem>
                <MenuItem value="triad">Triad</MenuItem>
                <MenuItem value="sealed_archon">Sealed Archon</MenuItem>
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>Best of</InputLabel>
              <Select
                value={weekBestOf}
                label="Best of"
                onChange={(e) => setWeekBestOf(e.target.value)}
                disabled={weekFormat === 'triad'}
              >
                <MenuItem value="1">Best of 1</MenuItem>
                <MenuItem value="3">Best of 3</MenuItem>
                <MenuItem value="5">Best of 5</MenuItem>
              </Select>
              {weekFormat === 'triad' && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
                  Triad is always Best of 3
                </Typography>
              )}
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
            {weekFormat === 'sealed_archon' && (
              <TextField
                label="Decks per Player"
                value={weekDecksPerPlayer}
                onChange={(e) => setWeekDecksPerPlayer(e.target.value)}
                type="number"
                inputProps={{ min: '2' }}
                helperText="Number of random decks each player receives in their sealed pool"
              />
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

      <Dialog open={deleteLeagueDialogOpen} onClose={() => setDeleteLeagueDialogOpen(false)}>
        <DialogTitle>Delete Test League?</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete this test league? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteLeagueDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDeleteLeague} variant="contained" color="error">Delete</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={deleteWeekId !== null} onClose={() => setDeleteWeekId(null)}>
        <DialogTitle>Delete Week?</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete this week? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteWeekId(null)}>Cancel</Button>
          <Button onClick={() => deleteWeekId && handleDeleteWeek(deleteWeekId)} variant="contained" color="error">Delete</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
