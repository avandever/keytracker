import { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import {
  Container,
  Typography,
  CircularProgress,
  Alert,
  Paper,
  Box,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Link,
} from '@mui/material';
import { getDeck } from '../api/decks';
import type { DeckDetail } from '../types';
import GameListing from '../components/GameListing';

export default function DeckDetailPage() {
  const { deckId } = useParams<{ deckId: string }>();
  const [searchParams] = useSearchParams();
  const username = searchParams.get('username') || undefined;
  const [deck, setDeck] = useState<DeckDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!deckId) return;
    getDeck(deckId, username)
      .then(setDeck)
      .catch((e) => {
        if (e.response?.status === 404) setError('Deck not found');
        else setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [deckId, username]);

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;
  if (!deck) return null;

  return (
    <Container maxWidth="lg" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>{deck.name}</Typography>
      <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
        <Chip label={deck.expansion_name} variant="outlined" />
        <Chip label={`${deck.sas_rating ?? '?'} SAS`} color="primary" variant="outlined" />
        <Chip label={`${deck.aerc_score ?? '?'} AERC`} color="secondary" variant="outlined" />
        <Chip label={`${deck.games_won}W - ${deck.games_lost}L`} variant="outlined" />
        <Chip label={deck.houses.join(' / ')} variant="outlined" />
      </Box>
      <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
        <Link href={deck.mv_url} target="_blank" rel="noopener">Master Vault</Link>
        <Link href={deck.dok_url} target="_blank" rel="noopener">Decks of Keyforge</Link>
      </Box>

      {deck.pod_stats.length > 0 && (
        <>
          <Typography variant="h6" sx={{ mb: 1 }}>Pod Stats</Typography>
          <TableContainer component={Paper} sx={{ mb: 3 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>House</TableCell>
                  <TableCell align="right">SAS</TableCell>
                  <TableCell align="right">AERC</TableCell>
                  <TableCell align="right">Creatures</TableCell>
                  <TableCell align="right">Raw Amber</TableCell>
                  <TableCell align="right">Total Amber</TableCell>
                  <TableCell align="right">Enhancements</TableCell>
                  <TableCell align="right">Mutants</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {deck.pod_stats.map((ps) => (
                  <TableRow key={ps.house}>
                    <TableCell>{ps.house}</TableCell>
                    <TableCell align="right">{ps.sas_rating}</TableCell>
                    <TableCell align="right">{ps.aerc_score}</TableCell>
                    <TableCell align="right">{ps.creatures}</TableCell>
                    <TableCell align="right">{ps.raw_amber}</TableCell>
                    <TableCell align="right">{ps.total_amber}</TableCell>
                    <TableCell align="right">{ps.num_enhancements}</TableCell>
                    <TableCell align="right">{ps.num_mutants}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      <Typography variant="h6" sx={{ mb: 1 }}>Games ({deck.games.length})</Typography>
      {deck.games.map((game) => (
        <GameListing key={game.crucible_game_id} game={game} highlightDeckId={deckId} />
      ))}
    </Container>
  );
}
