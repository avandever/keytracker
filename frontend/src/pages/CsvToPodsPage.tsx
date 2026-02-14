import { useState } from 'react';
import {
  Container,
  Typography,
  Button,
  Box,
  Alert,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import { uploadCsvPods } from '../api/upload';
import type { CsvPod } from '../types';

export default function CsvToPodsPage() {
  const [file, setFile] = useState<File | null>(null);
  const [pods, setPods] = useState<CsvPod[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a CSV file');
      return;
    }
    setLoading(true);
    setError('');
    uploadCsvPods(file)
      .then((data) => setPods(data as CsvPod[]))
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>Pod Stats From CSV</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Upload a Decks of Keyforge CSV export to view pod statistics.
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', gap: 2, mb: 3, alignItems: 'center' }}>
        <Button variant="outlined" component="label">
          Choose File
          <input type="file" accept=".csv" hidden onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </Button>
        {file && <Typography variant="body2">{file.name}</Typography>}
        <Button type="submit" variant="contained" disabled={loading}>
          {loading ? <CircularProgress size={24} /> : 'Analyze'}
        </Button>
      </Box>

      {pods && pods.length > 0 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Deck</TableCell>
                <TableCell>Set</TableCell>
                <TableCell>House</TableCell>
                <TableCell align="right">SAS</TableCell>
                <TableCell>Cards</TableCell>
                <TableCell>Market</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {pods.map((pod, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Typography component="a" href={pod.link} target="_blank" rel="noopener" variant="body2">
                      {pod.name}
                    </Typography>
                  </TableCell>
                  <TableCell>{pod.expansion}</TableCell>
                  <TableCell>{pod.house}</TableCell>
                  <TableCell align="right">{pod.sas}</TableCell>
                  <TableCell sx={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {pod.cards}
                  </TableCell>
                  <TableCell>{pod.on_market ? 'Yes' : 'No'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Container>
  );
}
