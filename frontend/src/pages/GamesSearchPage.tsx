import { useState } from 'react';
import {
  Container,
  Typography,
  Button,
  Box,
  CircularProgress,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { searchGames } from '../api/games';
import type { GameSummary } from '../types';
import GameListing from '../components/GameListing';
import PlayerFilterGroup from '../components/PlayerFilterGroup';

const SORT_OPTIONS: Record<string, string> = {
  date: 'Date',
  loser_keys: 'Keys forged by loser',
  combined_sas_rating: 'Total SAS',
  winner_sas_rating: 'Winner SAS',
  loser_sas_rating: 'Loser SAS',
  combined_aerc_score: 'Total AERC',
  winner_aerc_score: 'Winner AERC',
  loser_aerc_score: 'Loser AERC',
};

export default function GamesSearchPage() {
  const [filters, setFilters] = useState<Record<string, string>>({
    sort1: 'date',
    direction1: 'desc',
  });
  const [games, setGames] = useState<GameSummary[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!filters.user1 && !filters.deck1) {
      setError('Enter at least a username or deck ID for Player 1');
      return;
    }
    setLoading(true);
    setError('');
    searchGames(filters)
      .then(setGames)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>Games Search</Typography>
      <Box component="form" onSubmit={handleSearch}>
        <PlayerFilterGroup
          label="Player 1"
          prefix="1"
          values={filters}
          onChange={handleChange}
        />
        <PlayerFilterGroup
          label="Player 2 (optional)"
          prefix="2"
          values={filters}
          onChange={handleChange}
        />
        <Box sx={{ display: 'flex', gap: 2, mb: 2, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Sort By</InputLabel>
            <Select
              value={filters.sort1 || 'date'}
              label="Sort By"
              onChange={(e) => handleChange('sort1', e.target.value)}
            >
              {Object.entries(SORT_OPTIONS).map(([key, label]) => (
                <MenuItem key={key} value={key}>{label}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Direction</InputLabel>
            <Select
              value={filters.direction1 || 'desc'}
              label="Direction"
              onChange={(e) => handleChange('direction1', e.target.value)}
            >
              <MenuItem value="desc">Descending</MenuItem>
              <MenuItem value="asc">Ascending</MenuItem>
            </Select>
          </FormControl>
          <Button type="submit" variant="contained">Search</Button>
        </Box>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {loading && <CircularProgress />}
      {games !== null && !loading && (
        <>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>{games.length} results</Typography>
          {games.map((game) => (
            <GameListing key={game.crucible_game_id} game={game} />
          ))}
          {games.length === 0 && <Alert severity="info">No games found</Alert>}
        </>
      )}
    </Container>
  );
}
