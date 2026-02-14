import { useState } from 'react';
import {
  Container,
  Typography,
  TextField,
  Button,
  Box,
  CircularProgress,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { searchDecks } from '../api/decks';
import type { DeckSummary } from '../types';

export default function DecksSearchPage() {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [decks, setDecks] = useState<DeckSummary[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    searchDecks(filters)
      .then(setDecks)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>Decks Search</Typography>
      <Box component="form" onSubmit={handleSearch} sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          label="SAS Min"
          size="small"
          type="number"
          value={filters.sas_min || ''}
          onChange={(e) => handleChange('sas_min', e.target.value)}
          sx={{ width: 100 }}
        />
        <TextField
          label="SAS Max"
          size="small"
          type="number"
          value={filters.sas_max || ''}
          onChange={(e) => handleChange('sas_max', e.target.value)}
          sx={{ width: 100 }}
        />
        <TextField
          label="AERC Min"
          size="small"
          type="number"
          value={filters.aerc_min || ''}
          onChange={(e) => handleChange('aerc_min', e.target.value)}
          sx={{ width: 100 }}
        />
        <TextField
          label="AERC Max"
          size="small"
          type="number"
          value={filters.aerc_max || ''}
          onChange={(e) => handleChange('aerc_max', e.target.value)}
          sx={{ width: 100 }}
        />
        <Button type="submit" variant="contained">Search</Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {loading && <CircularProgress />}
      {decks !== null && !loading && (
        <>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>{decks.length} results</Typography>
          {decks.length > 0 ? (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Name</TableCell>
                    <TableCell>Set</TableCell>
                    <TableCell align="right">SAS</TableCell>
                    <TableCell align="right">AERC</TableCell>
                    <TableCell>Links</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {decks.map((deck) => (
                    <TableRow key={deck.kf_id}>
                      <TableCell>
                        <Typography
                          component={RouterLink}
                          to={`/deck/${deck.kf_id}`}
                          sx={{ color: 'primary.main', textDecoration: 'none' }}
                        >
                          {deck.name}
                        </Typography>
                      </TableCell>
                      <TableCell>{deck.expansion_name}</TableCell>
                      <TableCell align="right">{deck.sas_rating ?? '-'}</TableCell>
                      <TableCell align="right">{deck.aerc_score ?? '-'}</TableCell>
                      <TableCell>
                        <Typography component="a" href={deck.mv_url} target="_blank" rel="noopener" variant="body2" sx={{ mr: 1 }}>MV</Typography>
                        <Typography component="a" href={deck.dok_url} target="_blank" rel="noopener" variant="body2">DoK</Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <Alert severity="info">No decks found</Alert>
          )}
        </>
      )}
    </Container>
  );
}
