import { useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Container,
  LinearProgress,
  Link,
  Paper,
  Tab,
  TablePagination,
  TableSortLabel,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { getCollection } from '../api/collection';
import type { AllianceDeckEntry, CollectionDeck } from '../types';

export default function MyCollectionPage() {
  const [tab, setTab] = useState(0);
  const [standard, setStandard] = useState<CollectionDeck[]>([]);
  const [alliance, setAlliance] = useState<AllianceDeckEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [initialLoading, setInitialLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState('');

  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(50);
  const [sort, setSort] = useState('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      setPage(0);
    }, 400);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Fetch standard decks when params change
  useEffect(() => {
    if (tab !== 0) return;
    setFetching(true);
    getCollection({
      type: 'standard',
      page,
      per_page: rowsPerPage,
      sort,
      sort_dir: sortDir,
      search: search || undefined,
    })
      .then((res) => {
        setStandard(res.data.standard || []);
        setTotal(res.data.standard_total ?? 0);
      })
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => {
        setFetching(false);
        setInitialLoading(false);
      });
  }, [tab, page, rowsPerPage, sort, sortDir, search]);

  // Fetch alliance decks when switching to that tab
  useEffect(() => {
    if (tab !== 1) return;
    setInitialLoading(false);
    getCollection({ type: 'alliance' })
      .then((res) => setAlliance(res.data.alliance || []))
      .catch((e) => setError(e.response?.data?.error || e.message));
  }, [tab]);

  const handleSort = (field: string) => {
    if (sort === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSort(field);
      setSortDir('asc');
    }
    setPage(0);
  };

  if (initialLoading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;

  const isEmpty = total === 0 && alliance.length === 0 && !fetching;

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
            <Tab label={`Standard Decks (${total})`} />
            <Tab label={`Alliance Decks (${alliance.length})`} />
          </Tabs>

          {tab === 0 && (
            <>
              <TextField
                size="small"
                placeholder="Search by name…"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                sx={{ mb: 2, width: 300 }}
              />
              {fetching && <LinearProgress sx={{ mb: 1 }} />}
              <TableContainer component={Paper}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sortDirection={sort === 'name' ? sortDir : false}>
                        <TableSortLabel
                          active={sort === 'name'}
                          direction={sort === 'name' ? sortDir : 'asc'}
                          onClick={() => handleSort('name')}
                        >
                          Name
                        </TableSortLabel>
                      </TableCell>
                      <TableCell sortDirection={sort === 'expansion' ? sortDir : false}>
                        <TableSortLabel
                          active={sort === 'expansion'}
                          direction={sort === 'expansion' ? sortDir : 'asc'}
                          onClick={() => handleSort('expansion')}
                        >
                          Set
                        </TableSortLabel>
                      </TableCell>
                      <TableCell>Houses</TableCell>
                      <TableCell align="right" sortDirection={sort === 'sas_rating' ? sortDir : false}>
                        <TableSortLabel
                          active={sort === 'sas_rating'}
                          direction={sort === 'sas_rating' ? sortDir : 'asc'}
                          onClick={() => handleSort('sas_rating')}
                        >
                          SAS
                        </TableSortLabel>
                      </TableCell>
                      <TableCell align="right" sortDirection={sort === 'aerc_score' ? sortDir : false}>
                        <TableSortLabel
                          active={sort === 'aerc_score'}
                          direction={sort === 'aerc_score' ? sortDir : 'asc'}
                          onClick={() => handleSort('aerc_score')}
                        >
                          AERC
                        </TableSortLabel>
                      </TableCell>
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
              </TableContainer>
              <TablePagination
                component="div"
                count={total}
                page={page}
                onPageChange={(_, newPage) => setPage(newPage)}
                rowsPerPage={rowsPerPage}
                rowsPerPageOptions={[25, 50, 100]}
                onRowsPerPageChange={(e) => {
                  setRowsPerPage(parseInt(e.target.value, 10));
                  setPage(0);
                }}
              />
            </>
          )}

          {tab === 1 && (
            <TableContainer component={Paper}>
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
            </TableContainer>
          )}
        </>
      )}
    </Container>
  );
}
