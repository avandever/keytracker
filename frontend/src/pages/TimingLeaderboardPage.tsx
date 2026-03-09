import { useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Container, Typography, CircularProgress, Alert,
  Table, TableHead, TableBody, TableRow, TableCell,
} from '@mui/material';
import { getTimingLeaderboard } from '../api/users';
import type { TimingLeaderboardEntry } from '../types';

export default function TimingLeaderboardPage() {
  const [rows, setRows] = useState<TimingLeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getTimingLeaderboard()
      .then(setRows)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;

  return (
    <Container maxWidth="md" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>Turn Timing Leaderboard</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Fastest average turn times (minimum 20 turns sampled). Measured from house selection to the next house selection.
      </Typography>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>#</TableCell>
            <TableCell>Player</TableCell>
            <TableCell align="right">Avg Turn (s)</TableCell>
            <TableCell align="right">Turns</TableCell>
            <TableCell align="right">Games</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} align="center">No data yet — play more games with the extension!</TableCell>
            </TableRow>
          ) : (
            rows.map((entry, idx) => (
              <TableRow key={entry.username}>
                <TableCell>{idx + 1}</TableCell>
                <TableCell>
                  <RouterLink to={`/user/${entry.username}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                    {entry.username}
                  </RouterLink>
                </TableCell>
                <TableCell align="right">{entry.avg_turn_seconds.toFixed(1)}</TableCell>
                <TableCell align="right">{entry.turn_count}</TableCell>
                <TableCell align="right">{entry.games_sampled}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </Container>
  );
}
