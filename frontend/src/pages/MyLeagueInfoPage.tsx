import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Container,
  Typography,
  CircularProgress,
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
} from '@mui/material';
import { getLeague } from '../api/leagues';
import { useAuth } from '../contexts/AuthContext';
import type { LeagueDetail, TeamDetail } from '../types';

export default function MyLeagueInfoPage() {
  const { leagueId } = useParams<{ leagueId: string }>();
  const { user } = useAuth();
  const [league, setLeague] = useState<LeagueDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!leagueId) return;
    getLeague(parseInt(leagueId, 10))
      .then(setLeague)
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;
  if (!league || !user) return null;

  const myTeam = league.teams.find((t) => t.id === league.my_team_id);
  if (!myTeam) {
    return (
      <Container sx={{ mt: 3 }}>
        <Alert severity="info">You are not on a team in this league yet.</Alert>
      </Container>
    );
  }

  const captain = myTeam.members.find((m) => m.is_captain);
  const myMember = myTeam.members.find((m) => m.user.id === user.id);

  return (
    <Container maxWidth="sm" sx={{ mt: 3 }}>
      <Typography variant="h4" gutterBottom>{league.name}</Typography>
      <Typography variant="h5" gutterBottom>My Info</Typography>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6">{myTeam.name}</Typography>
          {captain && (
            <Typography color="text.secondary" sx={{ mb: 1 }}>
              Captain: {captain.user.name}
            </Typography>
          )}
          <List dense>
            {myTeam.members.map((m) => (
              <ListItem key={m.id}>
                <ListItemAvatar>
                  <Avatar src={m.user.avatar_url || undefined} sx={{ width: 28, height: 28 }}>
                    {m.user.name?.[0]}
                  </Avatar>
                </ListItemAvatar>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                      {m.user.name}
                      {m.is_captain && <Chip label="Captain" size="small" color="primary" />}
                      {m.user.id === user.id && <Chip label="You" size="small" variant="outlined" />}
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>

      {league.fee_amount != null && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Fee Status</Typography>
            <Typography>
              Fee: ${league.fee_amount}
            </Typography>
            <Chip
              label={myMember?.has_paid ? 'Paid' : 'Unpaid'}
              color={myMember?.has_paid ? 'success' : 'warning'}
              sx={{ mt: 1 }}
            />
          </CardContent>
        </Card>
      )}
    </Container>
  );
}
