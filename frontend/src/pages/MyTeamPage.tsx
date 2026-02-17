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
  Switch,
  Chip,
} from '@mui/material';
import { getLeague, updateTeam, toggleFeePaid } from '../api/leagues';
import { useAuth } from '../contexts/AuthContext';
import type { LeagueDetail } from '../types';

export default function MyTeamPage() {
  const { leagueId } = useParams<{ leagueId: string }>();
  const { user } = useAuth();
  const [league, setLeague] = useState<LeagueDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [editName, setEditName] = useState('');

  const refresh = useCallback(() => {
    if (!leagueId) return;
    getLeague(parseInt(leagueId, 10))
      .then((l) => {
        setLeague(l);
        const myTeam = l.teams.find((t) => t.id === l.my_team_id);
        if (myTeam) setEditName(myTeam.name);
      })
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  useEffect(() => { refresh(); }, [refresh]);

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error && !league) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;
  if (!league || !user) return null;

  if (!league.is_captain) {
    return (
      <Container sx={{ mt: 3 }}>
        <Alert severity="error">Captain access required</Alert>
      </Container>
    );
  }

  const myTeam = league.teams.find((t) => t.id === league.my_team_id);
  if (!myTeam) return null;

  const handleUpdateName = async () => {
    setError('');
    setSuccess('');
    try {
      await updateTeam(league.id, myTeam.id, editName);
      setSuccess('Team name updated');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleToggleFee = async (userId: number, currentPaid: boolean) => {
    setError('');
    try {
      await toggleFeePaid(league.id, myTeam.id, userId, !currentPaid);
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 3 }}>
      <Typography variant="h4" gutterBottom>{league.name}</Typography>
      <Typography variant="h5" gutterBottom>My Team</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>Team Name</Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <TextField
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              size="small"
              fullWidth
            />
            <Button variant="contained" onClick={handleUpdateName}>Save</Button>
          </Box>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>Members</Typography>
          <List>
            {myTeam.members.map((m) => (
              <ListItem key={m.id}>
                <ListItemAvatar>
                  <Avatar src={m.user.avatar_url || undefined} sx={{ width: 32, height: 32 }}>
                    {m.user.name?.[0]}
                  </Avatar>
                </ListItemAvatar>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                      {m.user.name}
                      {m.is_captain && <Chip label="Captain" size="small" color="primary" />}
                    </Box>
                  }
                />
                {league.fee_amount != null && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      {m.has_paid ? 'Paid' : 'Unpaid'}
                    </Typography>
                    <Switch
                      checked={m.has_paid}
                      onChange={() => handleToggleFee(m.user.id, m.has_paid)}
                      size="small"
                    />
                  </Box>
                )}
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>
    </Container>
  );
}
