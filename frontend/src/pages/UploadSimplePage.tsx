import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Typography,
  TextField,
  Button,
  Box,
  Alert,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { uploadSimple } from '../api/upload';

export default function UploadSimplePage() {
  const [fields, setFields] = useState<Record<string, string>>({
    winner_keys: '3',
    first_player: 'winner',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleChange = (key: string, value: string) => {
    setFields((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    uploadSimple(fields)
      .then((res) => navigate(`/game/${res.crucible_game_id}`))
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>Simple Game Upload</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <TextField label="Game ID" size="small" required
          value={fields.crucible_game_id || ''} onChange={(e) => handleChange('crucible_game_id', e.target.value)} />
        <TextField label="Date" size="small" type="datetime-local" InputLabelProps={{ shrink: true }}
          value={fields.date || ''} onChange={(e) => handleChange('date', e.target.value)} />
        <TextField label="Winner Username" size="small" required
          value={fields.winner || ''} onChange={(e) => handleChange('winner', e.target.value)} />
        <TextField label="Winner Deck ID (or URL)" size="small"
          value={fields.winner_deck_id || ''} onChange={(e) => handleChange('winner_deck_id', e.target.value)} />
        <TextField label="Winner Deck Name" size="small"
          value={fields.winner_deck_name || ''} onChange={(e) => handleChange('winner_deck_name', e.target.value)} />
        <TextField label="Winner Keys" size="small" type="number"
          value={fields.winner_keys || ''} onChange={(e) => handleChange('winner_keys', e.target.value)} />
        <TextField label="Loser Username" size="small" required
          value={fields.loser || ''} onChange={(e) => handleChange('loser', e.target.value)} />
        <TextField label="Loser Deck ID (or URL)" size="small"
          value={fields.loser_deck_id || ''} onChange={(e) => handleChange('loser_deck_id', e.target.value)} />
        <TextField label="Loser Deck Name" size="small"
          value={fields.loser_deck_name || ''} onChange={(e) => handleChange('loser_deck_name', e.target.value)} />
        <TextField label="Loser Keys" size="small" type="number"
          value={fields.loser_keys || ''} onChange={(e) => handleChange('loser_keys', e.target.value)} />
        <FormControl size="small">
          <InputLabel>First Player</InputLabel>
          <Select value={fields.first_player || 'winner'} label="First Player"
            onChange={(e) => handleChange('first_player', e.target.value)}>
            <MenuItem value="winner">Winner</MenuItem>
            <MenuItem value="loser">Loser</MenuItem>
          </Select>
        </FormControl>
        <Button type="submit" variant="contained" disabled={loading}>
          {loading ? <CircularProgress size={24} /> : 'Upload Game'}
        </Button>
      </Box>
    </Container>
  );
}
