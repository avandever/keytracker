import { useEffect, useState, useCallback } from 'react';
import { useParams, Link as RouterLink } from 'react-router-dom';
import {
  Container,
  Typography,
  CircularProgress,
  Alert,
  Box,
  Chip,
  Button,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Divider,
} from '@mui/material';
import { getLeague, signup, withdraw } from '../api/leagues';
import { useAuth } from '../contexts/AuthContext';
import type { LeagueDetail } from '../types';

export default function LeagueDetailPage() {
  const { leagueId } = useParams<{ leagueId: string }>();
  const { user } = useAuth();
  const [league, setLeague] = useState<LeagueDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const refresh = useCallback(() => {
    if (!leagueId) return;
    getLeague(parseInt(leagueId, 10))
      .then(setLeague)
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  useEffect(() => { refresh(); }, [refresh]);

  const handleSignup = async () => {
    if (!leagueId) return;
    setActionLoading(true);
    try {
      await signup(parseInt(leagueId, 10));
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleWithdraw = async () => {
    if (!leagueId) return;
    setActionLoading(true);
    try {
      await withdraw(parseInt(leagueId, 10));
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error && !league) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;
  if (!league) return null;

  return (
    <Container maxWidth="md" sx={{ mt: 3 }}>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
        <Box>
          <Typography variant="h4">{league.name}</Typography>
          {league.description && (
            <Typography color="text.secondary" sx={{ mt: 1 }}>{league.description}</Typography>
          )}
        </Box>
        <Chip label={league.status} color={league.status === 'active' ? 'success' : league.status === 'drafting' ? 'warning' : 'info'} />
      </Box>

      <Box sx={{ display: 'flex', gap: 1, mb: 3, flexWrap: 'wrap' }}>
        <Chip label={`${league.num_teams} teams`} variant="outlined" />
        <Chip label={`${league.team_size} per team`} variant="outlined" />
        {league.fee_amount != null && <Chip label={`$${league.fee_amount} fee`} variant="outlined" />}
        <Chip label={`${league.signup_count} signups`} variant="outlined" />
      </Box>

      {/* Action buttons */}
      <Box sx={{ display: 'flex', gap: 1, mb: 3, flexWrap: 'wrap' }}>
        {user && league.status === 'setup' && !league.is_signed_up && (
          <Button variant="contained" onClick={handleSignup} disabled={actionLoading}>
            Sign Up
          </Button>
        )}
        {user && league.status === 'setup' && league.is_signed_up && (
          <Button variant="outlined" color="warning" onClick={handleWithdraw} disabled={actionLoading}>
            Withdraw
          </Button>
        )}
        {league.is_admin && (
          <Button variant="outlined" component={RouterLink} to={`/league/${league.id}/admin`}>
            Admin
          </Button>
        )}
        {(league.is_admin || league.is_captain) && (league.status === 'drafting' || league.status === 'active') && (
          <Button variant="outlined" component={RouterLink} to={`/league/${league.id}/draft`}>
            Draft Board
          </Button>
        )}
        {league.my_team_id && (
          <>
            <Button variant="outlined" component={RouterLink} to={`/league/${league.id}/my-info`}>
              My Info
            </Button>
            {league.is_captain && (
              <Button variant="outlined" component={RouterLink} to={`/league/${league.id}/my-team`}>
                My Team
              </Button>
            )}
          </>
        )}
      </Box>

      {/* Teams */}
      <Typography variant="h5" sx={{ mb: 2 }}>Teams</Typography>
      {league.teams.length === 0 && (
        <Typography color="text.secondary" sx={{ mb: 2 }}>No teams created yet.</Typography>
      )}
      {league.teams.map((team) => (
        <Card key={team.id} sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6">{team.name}</Typography>
            <List dense>
              {team.members.map((m) => (
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
                        {league.fee_amount != null && (
                          <Chip
                            label={m.has_paid ? 'Paid' : 'Unpaid'}
                            size="small"
                            color={m.has_paid ? 'success' : 'default'}
                            variant="outlined"
                          />
                        )}
                      </Box>
                    }
                  />
                </ListItem>
              ))}
              {team.members.length === 0 && (
                <ListItem>
                  <ListItemText secondary="No members yet" />
                </ListItem>
              )}
            </List>
          </CardContent>
        </Card>
      ))}

      {/* Signups */}
      <Divider sx={{ my: 3 }} />
      <Typography variant="h5" sx={{ mb: 2 }}>Signups ({league.signups.length})</Typography>
      <List dense>
        {league.signups.map((s) => (
          <ListItem key={s.id}>
            <ListItemAvatar>
              <Avatar src={s.user.avatar_url || undefined} sx={{ width: 28, height: 28 }}>
                {s.user.name?.[0]}
              </Avatar>
            </ListItemAvatar>
            <ListItemText
              primary={s.user.name}
              secondary={`#${s.signup_order} - ${s.status}`}
            />
          </ListItem>
        ))}
      </List>
    </Container>
  );
}
