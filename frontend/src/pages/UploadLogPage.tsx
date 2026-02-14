import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Container, Typography, TextField, Button, Box, Alert, CircularProgress } from '@mui/material';
import { uploadLog } from '../api/upload';

export default function UploadLogPage() {
  const [log, setLog] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!log.trim()) {
      setError('Please paste a game log');
      return;
    }
    setLoading(true);
    setError('');
    uploadLog(log)
      .then((res) => navigate(`/game/${res.crucible_game_id}`))
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  };

  return (
    <Container maxWidth="md" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>Upload a Game</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Paste a Crucible game log below.
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Box component="form" onSubmit={handleSubmit}>
        <TextField
          label="Game Log"
          multiline
          minRows={10}
          maxRows={30}
          fullWidth
          value={log}
          onChange={(e) => setLog(e.target.value)}
          sx={{ mb: 2 }}
        />
        <Button type="submit" variant="contained" disabled={loading}>
          {loading ? <CircularProgress size={24} /> : 'Upload'}
        </Button>
      </Box>
    </Container>
  );
}
