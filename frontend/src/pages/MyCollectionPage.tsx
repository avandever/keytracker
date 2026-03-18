import { useEffect, useState } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Container,
  FormControl,
  InputLabel,
  LinearProgress,
  Link,
  MenuItem,
  Paper,
  Select,
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
import { getCollection, getCollectionPods, type CollectionPod } from '../api/collection';
import type { AllianceDeckEntry, CollectionDeck } from '../types';

export default function MyCollectionPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState(() => {
    const t = parseInt(searchParams.get('tab') ?? '0', 10);
    return isNaN(t) ? 0 : t;
  });
  const [standard, setStandard] = useState<CollectionDeck[]>([]);
  const [alliance, setAlliance] = useState<AllianceDeckEntry[]>([]);
  const [pods, setPods] = useState<CollectionPod[]>([]);
  const [podHouseFilter, setPodHouseFilter] = useState('');
  const [podExpansionFilter, setPodExpansionFilter] = useState<number | ''>('');
  const [podSortDir, setPodSortDir] = useState<'asc' | 'desc'>('desc');
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

  // Fetch all pods once when switching to pods tab
  useEffect(() => {
    if (tab !== 2) return;
    setInitialLoading(false);
    getCollectionPods()
      .then((res) => setPods(res.data.pods || []))
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
          <Tabs value={tab} onChange={(_, v) => { setTab(v); setSearchParams((prev) => { prev.set('tab', String(v)); return prev; }, { replace: true }); }} variant="scrollable" scrollButtons="auto" allowScrollButtonsMobile sx={{ mb: 2 }}>
            <Tab label={`Standard Decks (${total})`} />
            <Tab label={`Alliance Decks (${alliance.length})`} />
            <Tab label="Pods" />
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

          {tab === 2 && (() => {
            const allHouses = Array.from(new Set(pods.map((p) => p.house))).sort();
            const allExpansions = Array.from(
              new Map(pods.map((p) => [p.expansion, p.expansion_name])).entries()
            ).sort((a, b) => a[1].localeCompare(b[1]));
            const visiblePods = pods
              .filter((p) => (!podHouseFilter || p.house === podHouseFilter) &&
                (podExpansionFilter === '' || p.expansion === podExpansionFilter))
              .sort((a, b) => podSortDir === 'desc'
                ? b.sas_rating - a.sas_rating
                : a.sas_rating - b.sas_rating);
            return (
              <Box>
                <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
                  <FormControl size="small" sx={{ minWidth: 150 }}>
                    <InputLabel>House</InputLabel>
                    <Select
                      value={podHouseFilter}
                      label="House"
                      onChange={(e) => setPodHouseFilter(e.target.value)}
                    >
                      <MenuItem value="">All Houses</MenuItem>
                      {allHouses.map((h) => (
                        <MenuItem key={h} value={h}>{h}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <FormControl size="small" sx={{ minWidth: 150 }}>
                    <InputLabel>Set</InputLabel>
                    <Select
                      value={podExpansionFilter}
                      label="Set"
                      onChange={(e) => setPodExpansionFilter(e.target.value as number | '')}
                    >
                      <MenuItem value="">All Sets</MenuItem>
                      {allExpansions.map(([id, name]) => (
                        <MenuItem key={id} value={id}>{name}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <FormControl size="small" sx={{ minWidth: 130 }}>
                    <InputLabel>Sort</InputLabel>
                    <Select
                      value={podSortDir}
                      label="Sort"
                      onChange={(e) => setPodSortDir(e.target.value as 'asc' | 'desc')}
                    >
                      <MenuItem value="desc">SAS High→Low</MenuItem>
                      <MenuItem value="asc">SAS Low→High</MenuItem>
                    </Select>
                  </FormControl>
                  <Typography variant="body2" color="text.secondary">{visiblePods.length} pods</Typography>
                </Box>
                <TableContainer component={Paper}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>House</TableCell>
                        <TableCell>Deck</TableCell>
                        <TableCell>Set</TableCell>
                        <TableCell align="right">Pod SAS</TableCell>
                        <TableCell>Links</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {visiblePods.map((pod, idx) => (
                        <TableRow key={`${pod.deck_kf_id}-${pod.house}-${idx}`} hover>
                          <TableCell>{pod.house}</TableCell>
                          <TableCell>
                            <Link component={RouterLink} to={`/deck/${pod.deck_kf_id}`}>
                              {pod.deck_name}
                            </Link>
                          </TableCell>
                          <TableCell>{pod.expansion_name}</TableCell>
                          <TableCell align="right">
                            {pod.sas_rating > 0 ? pod.sas_rating : '—'}
                          </TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', gap: 1 }}>
                              {pod.deck_mv_url && (
                                <Link href={pod.deck_mv_url} target="_blank" rel="noopener" variant="body2">MV</Link>
                              )}
                              {pod.deck_dok_url && (
                                <Link href={pod.deck_dok_url} target="_blank" rel="noopener" variant="body2">DoK</Link>
                              )}
                            </Box>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Box>
            );
          })()}
        </>
      )}
    </Container>
  );
}
