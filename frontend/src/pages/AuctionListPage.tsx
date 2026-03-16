import { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { createAuction, listAuctions } from '../api/auction';

const STATUS_COLORS: Record<string, 'default' | 'primary' | 'success' | 'secondary'> = {
  setup: 'default',
  deck_submission: 'primary',
  auction: 'secondary',
  completed: 'success',
};

export default function AuctionListPage() {
  const [auctions, setAuctions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    listAuctions()
      .then(setAuctions)
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async () => {
    setCreating(true);
    try {
      const a = await createAuction();
      navigate(`/auctions/${a.id}`);
    } catch (e) {
      alert('Failed to create auction');
      setCreating(false);
    }
  };

  return (
    <Box sx={{ maxWidth: 800, mx: 'auto', p: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" sx={{ flexGrow: 1 }}>
          Deck Auctions
        </Typography>
        <Button variant="contained" onClick={handleCreate} disabled={creating}>
          {creating ? <CircularProgress size={20} /> : 'Create Auction'}
        </Button>
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        In a deck auction, each player brings one deck to the pool. Players take turns picking a
        deck to bid on, and the highest bidder wins it at the cost of that many chains. To join an
        existing auction, visit its URL and enter the passphrase.
      </Typography>
      {loading ? (
        <CircularProgress />
      ) : auctions.length === 0 ? (
        <Typography color="text.secondary">You are not in any auctions yet.</Typography>
      ) : (
        <Paper>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Players</TableCell>
                <TableCell>Created</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {auctions.map((a) => (
                <TableRow
                  key={a.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/auctions/${a.id}`)}
                >
                  <TableCell>#{a.id}</TableCell>
                  <TableCell>
                    <Chip
                      label={a.status.replace('_', ' ')}
                      size="small"
                      color={STATUS_COLORS[a.status] || 'default'}
                    />
                  </TableCell>
                  <TableCell>{a.player_count}</TableCell>
                  <TableCell>
                    {a.created_at ? new Date(a.created_at).toLocaleDateString() : '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}
    </Box>
  );
}
