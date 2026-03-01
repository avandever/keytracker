import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Typography,
  Button,
  Box,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Checkbox,
  Alert,
  CircularProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Link,
} from '@mui/material';
import { useAuth } from '../contexts/AuthContext';
import { createStandaloneMatch, getPublicMatches } from '../api/standalone';
import { getSets } from '../api/leagues';
import type { StandaloneMatch, KeyforgeSetInfo } from '../types';

const FORMAT_LABELS: Record<string, string> = {
  archon_standard: 'Archon',
  triad: 'Triad',
  sealed_archon: 'Sealed Archon',
  sealed_alliance: 'Sealed Alliance',
  adaptive: 'Adaptive',
  alliance: 'Alliance',
};

export default function StandaloneMatchesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [publicMatches, setPublicMatches] = useState<StandaloneMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const [sets, setSets] = useState<KeyforgeSetInfo[]>([]);

  // Create form state
  const [formatType, setFormatType] = useState('archon_standard');
  const [bestOfN, setBestOfN] = useState(1);
  const [isPublic, setIsPublic] = useState(true);
  const [maxSas, setMaxSas] = useState('');
  const [combinedMaxSas, setCombinedMaxSas] = useState('');
  const [setDiversity, setSetDiversity] = useState(false);
  const [houseDiversity, setHouseDiversity] = useState(false);
  const [allowedSets, setAllowedSets] = useState<number[]>([]);
  const [decksPerPlayer, setDecksPerPlayer] = useState(3);

  const isSealed = formatType === 'sealed_archon' || formatType === 'sealed_alliance';
  const isSealedAlliance = formatType === 'sealed_alliance';
  const isTriad = formatType === 'triad';
  const isAdaptive = formatType === 'adaptive';

  useEffect(() => {
    Promise.all([
      getPublicMatches().then(setPublicMatches),
      getSets().then(setSets),
    ]).finally(() => setLoading(false));
  }, []);

  const handleFormatChange = (newFormat: string) => {
    setFormatType(newFormat);
    if (newFormat === 'sealed_alliance') {
      setAllowedSets([]);
    }
  };

  const handleCreate = async () => {
    if (isSealedAlliance && allowedSets.length === 0) {
      setCreateError('A set must be selected for Sealed Alliance');
      return;
    }
    setCreating(true);
    setCreateError('');
    try {
      const match = await createStandaloneMatch({
        format_type: formatType,
        best_of_n: isTriad || isAdaptive ? 3 : bestOfN,
        is_public: isPublic,
        max_sas: maxSas ? parseInt(maxSas) : null,
        combined_max_sas: combinedMaxSas ? parseInt(combinedMaxSas) : null,
        set_diversity: setDiversity,
        house_diversity: houseDiversity,
        allowed_sets: allowedSets.length > 0 ? allowedSets : null,
        decks_per_player: isSealed ? decksPerPlayer : 1,
      });
      navigate(`/matches/${match.id}?uuid=${match.uuid}`);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setCreateError(err.response?.data?.error || 'Failed to create match');
    } finally {
      setCreating(false);
    }
  };

  const handleJoin = (match: StandaloneMatch) => {
    navigate(`/matches/${match.id}?uuid=${match.uuid}`);
  };

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}><CircularProgress /></Box>;

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Standalone Matches</Typography>
        {user && (
          <Button variant="contained" onClick={() => setCreateOpen(true)}>
            Create Match
          </Button>
        )}
      </Box>

      <Typography variant="h6" gutterBottom>Public Open Matches</Typography>
      {publicMatches.length === 0 ? (
        <Typography color="text.secondary">No public matches available right now.</Typography>
      ) : (
        <List>
          {publicMatches.map((match) => (
            <ListItem key={match.id} divider>
              <ListItemText
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body1">{match.creator.name}</Typography>
                    <Chip label={FORMAT_LABELS[match.format_type] || match.format_type} size="small" />
                    <Chip label={`Bo${match.best_of_n}`} size="small" variant="outlined" />
                  </Box>
                }
                secondary={match.created_at ? new Date(match.created_at).toLocaleString() : ''}
              />
              <ListItemSecondaryAction>
                <Button variant="outlined" size="small" onClick={() => handleJoin(match)}>
                  Join
                </Button>
              </ListItemSecondaryAction>
            </ListItem>
          ))}
        </List>
      )}

      {/* Create match dialog */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create Standalone Match</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          {createError && (
            <Alert severity="error">
              {createError === 'Membership required' ? (
                <>Membership required. <Link href="/account">Visit your account page</Link> to become a member.</>
              ) : createError}
            </Alert>
          )}

          <FormControl fullWidth>
            <InputLabel>Format</InputLabel>
            <Select value={formatType} label="Format" onChange={(e) => handleFormatChange(e.target.value)}>
              <MenuItem value="archon_standard">Archon</MenuItem>
              <MenuItem value="triad">Triad</MenuItem>
              <MenuItem value="sealed_archon">Sealed Archon</MenuItem>
              <MenuItem value="sealed_alliance">Sealed Alliance</MenuItem>
              <MenuItem value="adaptive">Adaptive</MenuItem>
              <MenuItem value="alliance">Alliance</MenuItem>
            </Select>
          </FormControl>

          {!isTriad && !isAdaptive && (
            <TextField
              label="Best of N"
              type="number"
              value={bestOfN}
              onChange={(e) => setBestOfN(parseInt(e.target.value) || 1)}
              inputProps={{ min: 1, max: 9 }}
              size="small"
            />
          )}

          {isSealed && (
            <TextField
              label="Decks per player"
              type="number"
              value={decksPerPlayer}
              onChange={(e) => setDecksPerPlayer(parseInt(e.target.value) || 3)}
              inputProps={{ min: 1, max: 10 }}
              size="small"
            />
          )}

          <TextField
            label="Max SAS (optional)"
            type="number"
            value={maxSas}
            onChange={(e) => setMaxSas(e.target.value)}
            size="small"
          />

          {isTriad && (
            <TextField
              label="Combined Max SAS (optional)"
              type="number"
              value={combinedMaxSas}
              onChange={(e) => setCombinedMaxSas(e.target.value)}
              size="small"
            />
          )}

          {isTriad && (
            <>
              <FormControlLabel
                control={<Checkbox checked={setDiversity} onChange={(e) => setSetDiversity(e.target.checked)} />}
                label="Set Diversity (no two decks from same set)"
              />
              <FormControlLabel
                control={<Checkbox checked={houseDiversity} onChange={(e) => setHouseDiversity(e.target.checked)} />}
                label="House Diversity (no shared houses across decks)"
              />
            </>
          )}

          {isSealedAlliance ? (
            <FormControl fullWidth required>
              <InputLabel>Set (required)</InputLabel>
              <Select
                value={allowedSets[0] ?? ''}
                label="Set (required)"
                onChange={(e) => setAllowedSets([e.target.value as number])}
              >
                {sets.map((s) => (
                  <MenuItem key={s.number} value={s.number}>{s.name} ({s.shortname})</MenuItem>
                ))}
              </Select>
            </FormControl>
          ) : (
            <FormControl fullWidth>
              <InputLabel>Allowed Sets (optional)</InputLabel>
              <Select
                multiple
                value={allowedSets}
                label="Allowed Sets (optional)"
                onChange={(e) => setAllowedSets(e.target.value as number[])}
                renderValue={(selected) => (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {(selected as number[]).map((v) => (
                      <Chip key={v} label={sets.find((s) => s.number === v)?.shortname || v} size="small" />
                    ))}
                  </Box>
                )}
              >
                {sets.map((s) => (
                  <MenuItem key={s.number} value={s.number}>{s.name} ({s.shortname})</MenuItem>
                ))}
              </Select>
            </FormControl>
          )}

          <FormControlLabel
            control={<Checkbox checked={isPublic} onChange={(e) => setIsPublic(e.target.checked)} />}
            label="Public (appear in public match list)"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button onClick={handleCreate} variant="contained" disabled={creating}>
            {creating ? 'Creating...' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
