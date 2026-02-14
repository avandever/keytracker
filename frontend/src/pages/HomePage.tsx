import { useEffect, useState } from 'react';
import { Container, Typography, CircularProgress, Alert } from '@mui/material';
import { getRecentGames } from '../api/games';
import type { GameSummary } from '../types';
import GameListing from '../components/GameListing';

export default function HomePage() {
  const [games, setGames] = useState<GameSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getRecentGames(5)
      .then(setGames)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Container maxWidth="lg" sx={{ mt: 3 }}>
      <Typography variant="h4" gutterBottom>Bear Tracks</Typography>
      <Typography variant="subtitle1" gutterBottom color="text.secondary">
        KeyForge Game Records and Analysis
      </Typography>
      <Typography variant="h6" sx={{ mt: 3, mb: 1 }}>Recent Games</Typography>
      {loading && <CircularProgress />}
      {error && <Alert severity="error">{error}</Alert>}
      {games.map((game) => (
        <GameListing key={game.crucible_game_id} game={game} />
      ))}
    </Container>
  );
}
