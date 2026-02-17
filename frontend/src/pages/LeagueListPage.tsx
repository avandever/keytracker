import { useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Container,
  Typography,
  CircularProgress,
  Alert,
  Box,
  Card,
  CardContent,
  CardActionArea,
  Chip,
  Button,
} from '@mui/material';
import { listLeagues } from '../api/leagues';
import { useAuth } from '../contexts/AuthContext';
import type { LeagueSummary } from '../types';

const STATUS_COLORS: Record<string, 'default' | 'info' | 'success' | 'warning'> = {
  setup: 'info',
  drafting: 'warning',
  active: 'success',
  completed: 'default',
};

export default function LeagueListPage() {
  const { user } = useAuth();
  const [leagues, setLeagues] = useState<LeagueSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    listLeagues()
      .then(setLeagues)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;

  return (
    <Container maxWidth="md" sx={{ mt: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5">Leagues</Typography>
        {user?.is_league_admin && (
          <Button variant="contained" component={RouterLink} to="/leagues/new">
            Create League
          </Button>
        )}
      </Box>
      {leagues.length === 0 && (
        <Typography color="text.secondary">No leagues yet.</Typography>
      )}
      {leagues.map((league) => (
        <Card key={league.id} sx={{ mb: 2 }}>
          <CardActionArea component={RouterLink} to={`/league/${league.id}`}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="h6">{league.name}</Typography>
                <Chip
                  label={league.status}
                  size="small"
                  color={STATUS_COLORS[league.status] || 'default'}
                />
              </Box>
              {league.description && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  {league.description}
                </Typography>
              )}
              <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
                <Chip label={`${league.signup_count} signups`} size="small" variant="outlined" />
                <Chip label={`${league.num_teams} teams`} size="small" variant="outlined" />
                <Chip label={`${league.team_size}/team`} size="small" variant="outlined" />
                {league.fee_amount != null && (
                  <Chip label={`$${league.fee_amount}`} size="small" variant="outlined" />
                )}
              </Box>
            </CardContent>
          </CardActionArea>
        </Card>
      ))}
    </Container>
  );
}
