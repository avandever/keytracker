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
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import {
  getLeague,
  updateLeague,
  createTeam,
  deleteTeam,
  assignCaptain,
  startDraft,
} from '../api/leagues';
import { useAuth } from '../contexts/AuthContext';
import type { LeagueDetail } from '../types';

export default function LeagueAdminPage() {
  const { leagueId } = useParams<{ leagueId: string }>();
  const { user } = useAuth();
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

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (!league) return <Container sx={{ mt: 3 }}><Alert severity="error">{error || 'League not found'}</Alert></Container>;
  if (!league.is_admin) return <Container sx={{ mt: 3 }}><Alert severity="error">Admin access required</Alert></Container>;

  const isSetup = league.status === 'setup';

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

  // Get captain IDs so we can exclude them from captain dropdown for other teams
  const assignedCaptainIds = new Set(
    league.teams.flatMap((t) => t.members.filter((m) => m.is_captain).map((m) => m.user.id))
  );

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
    </Container>
  );
}
