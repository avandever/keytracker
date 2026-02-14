import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Container, Typography, CircularProgress, Alert, Box, Chip } from '@mui/material';
import { getUser } from '../api/users';
import type { UserStats } from '../types';
import GameListing from '../components/GameListing';

export default function UserProfilePage() {
  const { username } = useParams<{ username: string }>();
  const [user, setUser] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!username) return;
    getUser(username)
      .then(setUser)
      .catch((e) => {
        if (e.response?.status === 404) setError('No games found for this user');
        else setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [username]);

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;
  if (!user) return null;

  const total = user.games_won + user.games_lost;
  const winRate = total > 0 ? ((user.games_won / total) * 100).toFixed(1) : '0';

  return (
    <Container maxWidth="lg" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>{user.username}</Typography>
      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <Chip label={`${user.games_won} Wins`} color="primary" variant="outlined" />
        <Chip label={`${user.games_lost} Losses`} variant="outlined" />
        <Chip label={`${winRate}% Win Rate`} variant="outlined" />
      </Box>
      <Typography variant="h6" sx={{ mb: 1 }}>Games</Typography>
      {user.games.map((game) => (
        <GameListing key={game.crucible_game_id} game={game} highlightUser={username} />
      ))}
    </Container>
  );
}
