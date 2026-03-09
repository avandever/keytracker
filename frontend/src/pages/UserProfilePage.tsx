import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Container, Typography, CircularProgress, Alert, Box, Chip,
  Table, TableHead, TableBody, TableRow, TableCell, LinearProgress,
} from '@mui/material';
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
      <Box sx={{ display: 'flex', gap: 1, mb: 3, flexWrap: 'wrap' }}>
        <Chip label={`${user.games_won} Wins`} color="primary" variant="outlined" />
        <Chip label={`${user.games_lost} Losses`} variant="outlined" />
        <Chip label={`${winRate}% Win Rate`} variant="outlined" />
        {user.discord_username && (
          <Chip label={`Discord: @${user.discord_username}`} />
        )}
        {user.dok_profile_url && (
          <Chip
            component="a"
            href={user.dok_profile_url}
            target="_blank"
            rel="noopener noreferrer"
            label="DoK Collection"
            clickable
          />
        )}
      </Box>
      {user.timing_stats && (() => {
        const ts = user.timing_stats;
        const maxAvg = Math.max(...ts.house_breakdown.map((h) => h.avg_seconds), 1);
        return (
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" sx={{ mb: 1 }}>Turn Timing</Typography>
            <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
              <Chip label={`Avg ${ts.avg_turn_seconds.toFixed(1)}s / turn`} variant="outlined" />
              <Chip label={`${ts.turn_count} turns sampled`} variant="outlined" />
              <Chip label={`${ts.games_sampled} games`} variant="outlined" />
            </Box>
            <Table size="small" sx={{ maxWidth: 480 }}>
              <TableHead>
                <TableRow>
                  <TableCell>House</TableCell>
                  <TableCell align="right">Avg (s)</TableCell>
                  <TableCell sx={{ minWidth: 120 }}>Speed</TableCell>
                  <TableCell align="right">Turns</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {ts.house_breakdown.map((hb) => (
                  <TableRow key={hb.house}>
                    <TableCell>{hb.house}</TableCell>
                    <TableCell align="right">{hb.avg_seconds.toFixed(1)}</TableCell>
                    <TableCell>
                      <LinearProgress
                        variant="determinate"
                        value={(hb.avg_seconds / maxAvg) * 100}
                        sx={{ height: 8, borderRadius: 4 }}
                      />
                    </TableCell>
                    <TableCell align="right">{hb.turn_count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        );
      })()}
      <Typography variant="h6" sx={{ mb: 1 }}>Games</Typography>
      {user.games.map((game) => (
        <GameListing key={game.crucible_game_id} game={game} highlightUser={username} />
      ))}
    </Container>
  );
}
