import { useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Container, Typography, CircularProgress, Alert, Box, Chip, Button } from '@mui/material';
import { getMyGames } from '../api/games';
import type { MyGamesResponse } from '../types';
import GameListing from '../components/GameListing';

export default function MyGamesPage() {
  const [data, setData] = useState<MyGamesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getMyGames()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;
  if (!data) return null;

  if (data.tco_usernames.length === 0) {
    return (
      <Container maxWidth="sm" sx={{ mt: 4, textAlign: 'center' }}>
        <Typography variant="h5" gutterBottom>My Games</Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          No TCO usernames configured. Link your Crucible Online usernames to see your games here.
        </Typography>
        <Button variant="contained" component={RouterLink} to="/account">
          Go to Account Settings
        </Button>
      </Container>
    );
  }

  const total = data.games_won + data.games_lost;
  const winRate = total > 0 ? ((data.games_won / total) * 100).toFixed(1) : '0';

  return (
    <Container maxWidth="lg" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>My Games</Typography>
      <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
        {data.tco_usernames.map((name) => (
          <Chip key={name} label={name} size="small" variant="outlined" />
        ))}
      </Box>
      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <Chip label={`${data.games_won} Wins`} color="primary" variant="outlined" />
        <Chip label={`${data.games_lost} Losses`} variant="outlined" />
        <Chip label={`${winRate}% Win Rate`} variant="outlined" />
      </Box>
      <Typography variant="h6" sx={{ mb: 1 }}>Games</Typography>
      {data.games.map((game) => (
        <GameListing
          key={game.crucible_game_id}
          game={game}
          highlightUser={
            data.tco_usernames.includes(game.winner)
              ? game.winner
              : data.tco_usernames.includes(game.loser)
                ? game.loser
                : undefined
          }
        />
      ))}
      {data.games.length === 0 && (
        <Typography color="text.secondary">No games found for your TCO usernames.</Typography>
      )}
    </Container>
  );
}
