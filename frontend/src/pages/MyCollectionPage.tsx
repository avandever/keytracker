import { useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Container,
  Link,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { getCollection } from '../api/collection';
import type { AllianceDeckEntry, CollectionDeck } from '../types';

export default function MyCollectionPage() {
  const [tab, setTab] = useState(0);
  const [standard, setStandard] = useState<CollectionDeck[]>([]);
  const [alliance, setAlliance] = useState<AllianceDeckEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getCollection()
      .then((res) => {
        setStandard(res.data.standard || []);
        setAlliance(res.data.alliance || []);
      })
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;

  const isEmpty = standard.length === 0 && alliance.length === 0;

  return (
    <Container maxWidth="lg" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>My Collection</Typography>

      {isEmpty ? (
        <Alert severity="info">
          Your collection is empty. Go to{' '}
          <RouterLink to="/account">Account Settings</RouterLink> and click{' '}
          <strong>Sync Collection</strong> to import decks from Decks of Keyforge.
        </Alert>
      ) : (
        <>
          <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
            <Tab label={`Standard Decks (${standard.length})`} />
            <Tab label={`Alliance Decks (${alliance.length})`} />
          </Tabs>

          {tab === 0 && (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Set</TableCell>
                  <TableCell>Houses</TableCell>
                  <TableCell align="right">SAS</TableCell>
                  <TableCell align="right">AERC</TableCell>
                  <TableCell>Tags</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {standard.map((deck) => (
                  <TableRow key={deck.kf_id} hover>
                    <TableCell>
                      <Link component={RouterLink} to={`/deck/${deck.kf_id}`}>
                        {deck.name}
                      </Link>
                    </TableCell>
                    <TableCell>{deck.expansion_name}</TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                        {(deck.houses || []).map((h) => (
                          <Chip key={h} label={h} size="small" variant="outlined" />
                        ))}
                      </Box>
                    </TableCell>
                    <TableCell align="right">{deck.sas_rating ?? '—'}</TableCell>
                    <TableCell align="right">{deck.aerc_score ?? '—'}</TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', gap: 0.5 }}>
                        {deck.dok_owned && <Chip label="Owned" size="small" color="success" />}
                        {deck.dok_wishlist && <Chip label="Wishlist" size="small" color="info" />}
                        {deck.dok_funny && <Chip label="Funny" size="small" color="warning" />}
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {tab === 1 && (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Pods</TableCell>
                  <TableCell align="right">SAS</TableCell>
                  <TableCell align="right">AERC</TableCell>
                  <TableCell>Tags</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {alliance.map((deck) => (
                  <TableRow key={deck.kf_id} hover>
                    <TableCell>
                      <Link href={deck.dok_url} target="_blank" rel="noopener noreferrer">
                        {deck.name}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                        {(deck.pods || []).map((p) => (
                          <Chip
                            key={p.house}
                            label={`${p.house}: ${p.source_name}`}
                            size="small"
                            variant="outlined"
                          />
                        ))}
                      </Box>
                    </TableCell>
                    <TableCell align="right">{deck.sas_rating ?? '—'}</TableCell>
                    <TableCell align="right">{deck.aerc_score ?? '—'}</TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', gap: 0.5 }}>
                        {deck.dok_owned && <Chip label="Owned" size="small" color="success" />}
                        {deck.dok_wishlist && <Chip label="Wishlist" size="small" color="info" />}
                        {deck.dok_funny && <Chip label="Funny" size="small" color="warning" />}
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </>
      )}
    </Container>
  );
}
