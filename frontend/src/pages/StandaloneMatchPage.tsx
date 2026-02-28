import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import {
  Container,
  Typography,
  CircularProgress,
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  FormControlLabel,
  Link,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import {
  getStandaloneMatch,
  joinStandaloneMatch,
  getStandaloneSealedPool,
  submitStandaloneDeckSelection,
  removeStandaloneDeckSelection,
  submitStandaloneAllianceSelection,
  clearStandaloneAllianceSelection,
  startStandaloneMatch,
  submitStandaloneStrike,
  reportStandaloneGame,
  submitAdaptiveBid,
} from '../api/standalone';
import { getSets } from '../api/leagues';
import WeekConstraints from '../components/WeekConstraints';
import HouseIcons from '../components/HouseIcons';
import AlliancePodBuilder, { type PodEntry } from '../components/AlliancePodBuilder';
import { useAuth } from '../contexts/AuthContext';
import type {
  StandaloneMatch,
  DeckSelectionInfo,
  AlliancePodSelectionInfo,
  KeyforgeSetInfo,
} from '../types';
import type { SealedPoolEntry } from '../api/leagues';

const FORMAT_LABELS: Record<string, string> = {
  archon_standard: 'Archon',
  triad: 'Triad',
  sealed_archon: 'Sealed Archon',
  sealed_alliance: 'Sealed Alliance',
  adaptive: 'Adaptive',
  alliance: 'Alliance',
};

const TOKEN_SETS = new Set([855, 600]);
const PROPHECY_EXPANSION_ID = 886;

export default function StandaloneMatchPage() {
  const { matchId } = useParams<{ matchId: string }>();
  const [searchParams] = useSearchParams();
  const urlUuid = searchParams.get('uuid') || '';
  const { user } = useAuth();

  const [match, setMatch] = useState<StandaloneMatch | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [sets, setSets] = useState<KeyforgeSetInfo[]>([]);
  const [sealedPool, setSealedPool] = useState<SealedPoolEntry[]>([]);
  const [joining, setJoining] = useState(false);

  // Deck selection state
  const [deckUrl, setDeckUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [sealedDeckId, setSealedDeckId] = useState<number | ''>('');

  // Sealed Alliance selection state
  const [alliancePods, setAlliancePods] = useState<string[]>(['', '', '']);
  const [allianceTokenDeckId, setAllianceTokenDeckId] = useState(0);
  const [allianceProphecyDeckId, setAllianceProphecyDeckId] = useState(0);

  // Open Alliance selection state (AlliancePodBuilder)
  const [openAlliancePods, setOpenAlliancePods] = useState<PodEntry[]>([]);
  const [openAllianceTokenId, setOpenAllianceTokenId] = useState<number | null>(null);
  const [openAllianceProphecyId, setOpenAllianceProphecyId] = useState<number | null>(null);

  // Strike state
  const [strikeSelectionId, setStrikeSelectionId] = useState<number | ''>('');

  // Game report state
  const [reportWinnerId, setReportWinnerId] = useState<number | ''>('');
  const [reportWinnerKeys, setReportWinnerKeys] = useState('3');
  const [reportLoserKeys, setReportLoserKeys] = useState('0');
  const [reportWentToTime, setReportWentToTime] = useState(false);
  const [reportLoserConceded, setReportLoserConceded] = useState(false);
  const [reportP1DeckId, setReportP1DeckId] = useState<number | ''>('');
  const [reportP2DeckId, setReportP2DeckId] = useState<number | ''>('');

  // Adaptive bid state
  const [adaptiveBidChains, setAdaptiveBidChains] = useState('');

  const [copiedUrl, setCopiedUrl] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const id = parseInt(matchId || '0');

  const refresh = useCallback(async () => {
    try {
      const m = await getStandaloneMatch(id, urlUuid || undefined);
      setMatch(m);
      setError('');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Failed to load match');
    }
  }, [id, urlUuid]);

  // Initial load
  useEffect(() => {
    Promise.all([
      getSets().then(setSets),
    ]).then(async () => {
      // If UUID is present and match is in setup, try joining
      if (urlUuid) {
        try {
          const m = await getStandaloneMatch(id, urlUuid);
          setMatch(m);
          if (m.status === 'setup' && (!user || m.creator.id !== user.id)) {
            setJoining(true);
            try {
              const joined = await joinStandaloneMatch(id, urlUuid);
              setMatch(joined);
              setSuccess('You joined the match!');
            } catch (e: unknown) {
              const err = e as { response?: { data?: { error?: string } } };
              // If already joined or other error, just continue
              if (err.response?.data?.error !== 'Match already has an opponent') {
                setError(err.response?.data?.error || 'Failed to join match');
              }
            } finally {
              setJoining(false);
            }
          }
        } catch (e: unknown) {
          const err = e as { response?: { data?: { error?: string } } };
          setError(err.response?.data?.error || 'Failed to load match');
        }
      } else {
        await refresh();
      }
    }).finally(() => setLoading(false));
  }, [id, urlUuid, user, refresh]);

  // Load sealed pool when match changes to deck_selection
  useEffect(() => {
    if (match?.status === 'deck_selection' && match.sealed_pools_generated && user) {
      getStandaloneSealedPool(id).then(setSealedPool).catch(() => {});
    }
  }, [match?.status, match?.sealed_pools_generated, id, user]);

  // Poll while not completed
  useEffect(() => {
    if (!match || match.status === 'completed') {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    pollRef.current = setInterval(refresh, 10000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [match?.status, refresh]);

  if (loading || joining) return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}><CircularProgress /></Box>;
  if (!match) return <Container sx={{ py: 4 }}><Alert severity="error">{error || 'Match not found'}</Alert></Container>;

  const isCreator = user?.id === match.creator.id;
  const isOpponent = user?.id === match.opponent?.id;
  const isParticipant = isCreator || isOpponent;

  const mySelections: DeckSelectionInfo[] = isCreator ? match.creator_selections : match.opponent_selections;
  const oppSelections: DeckSelectionInfo[] = isCreator ? match.opponent_selections : match.creator_selections;
  const myPods: AlliancePodSelectionInfo[] = isCreator ? match.creator_pods : match.opponent_pods;

  const pm = match.matchup;
  const myStarted = pm
    ? (isCreator ? pm.player1_started : pm.player2_started)
    : false;
  const bothStarted = pm ? (pm.player1_started && pm.player2_started) : false;

  const winsNeeded = Math.ceil(match.best_of_n / 2);
  const games = pm ? [...pm.games].sort((a, b) => a.game_number - b.game_number) : [];
  const p1Wins = games.filter((g) => g.winner_id === pm?.player1.id).length;
  const p2Wins = games.filter((g) => g.winner_id === pm?.player2.id).length;
  const matchDecided = p1Wins >= winsNeeded || p2Wins >= winsNeeded;

  const myWins = isCreator ? p1Wins : p2Wins;
  const oppWins = isCreator ? p2Wins : p1Wins;

  const myStrikes = pm?.strikes.filter((s) => s.striking_user_id === user?.id) || [];
  const strickenIds = new Set(pm?.strikes.map((s) => s.struck_deck_selection_id) || []);

  const shareUrl = `${window.location.origin}/matches/${match.id}?uuid=${match.uuid}`;

  // Week-like object for WeekConstraints
  const weekLike = {
    id: 0,
    league_id: 0,
    week_number: 1,
    name: null,
    format_type: match.format_type,
    status: 'deck_selection' as const,
    best_of_n: match.best_of_n,
    allowed_sets: match.allowed_sets,
    max_sas: match.max_sas,
    combined_max_sas: match.combined_max_sas,
    set_diversity: match.set_diversity,
    house_diversity: match.house_diversity,
    decks_per_player: match.decks_per_player,
    sealed_pools_generated: match.sealed_pools_generated,
    no_keycheat: match.no_keycheat,
    matchups: [],
    deck_selections: [],
    feature_designations: [],
  };

  const isSealed = match.format_type === 'sealed_archon' || match.format_type === 'sealed_alliance';
  const isTriad = match.format_type === 'triad';
  const isSealedAlliance = match.format_type === 'sealed_alliance';
  const isOpenAlliance = match.format_type === 'alliance';
  const isAlliance = isSealedAlliance || isOpenAlliance;
  const isAdaptive = match.format_type === 'adaptive';

  const allowedSetsSet = new Set(match.allowed_sets || []);
  const needsToken = TOKEN_SETS.size > 0 && [...TOKEN_SETS].some((s) => allowedSetsSet.has(s));
  const needsProphecy = allowedSetsSet.has(PROPHECY_EXPANSION_ID);

  const handleDeckSubmit = async (slot: number) => {
    setSubmitting(true);
    setError('');
    try {
      if (match.format_type === 'sealed_archon') {
        if (!sealedDeckId) return;
        await submitStandaloneDeckSelection(id, { deck_id: sealedDeckId as number, slot_number: slot });
      } else {
        if (!deckUrl.trim()) return;
        await submitStandaloneDeckSelection(id, { deck_url: deckUrl.trim(), slot_number: slot });
        setDeckUrl('');
      }
      await refresh();
      setSuccess('Deck submitted!');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Failed to submit deck');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemoveDeck = async (slot: number) => {
    setSubmitting(true);
    setError('');
    try {
      await removeStandaloneDeckSelection(id, slot);
      await refresh();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Failed to remove deck');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAllianceSubmit = async () => {
    setSubmitting(true);
    setError('');
    try {
      const pods = alliancePods
        .filter((p) => p)
        .map((p) => {
          const [deckId, house] = p.split(':');
          return { deck_id: parseInt(deckId), house };
        });
      const payload: Parameters<typeof submitStandaloneAllianceSelection>[1] = { pods };
      if (needsToken && allianceTokenDeckId) payload.token_deck_id = allianceTokenDeckId;
      if (needsProphecy && allianceProphecyDeckId) payload.prophecy_deck_id = allianceProphecyDeckId;
      await submitStandaloneAllianceSelection(id, payload);
      await refresh();
      setSuccess('Alliance submitted!');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Failed to submit alliance');
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenAllianceSubmit = async () => {
    setSubmitting(true);
    setError('');
    try {
      const payload: Parameters<typeof submitStandaloneAllianceSelection>[1] = {
        pods: openAlliancePods,
      };
      if (openAllianceTokenId) payload.token_deck_id = openAllianceTokenId;
      if (openAllianceProphecyId) payload.prophecy_deck_id = openAllianceProphecyId;
      await submitStandaloneAllianceSelection(id, payload);
      await refresh();
      setSuccess('Alliance submitted!');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Failed to submit alliance');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStart = async () => {
    setSubmitting(true);
    setError('');
    try {
      const updated = await startStandaloneMatch(id);
      setMatch(updated);
      setSuccess('Selection confirmed!');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Failed to start');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStrike = async () => {
    if (!strikeSelectionId) return;
    setSubmitting(true);
    setError('');
    try {
      const updated = await submitStandaloneStrike(id, strikeSelectionId as number);
      setMatch(updated);
      setSuccess('Strike submitted!');
      setStrikeSelectionId('');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Failed to submit strike');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAdaptiveBid = async (concede: boolean) => {
    setSubmitting(true);
    setError('');
    try {
      const payload: { chains?: number; concede?: boolean } = {};
      if (concede) {
        payload.concede = true;
      } else {
        const chains = parseInt(adaptiveBidChains);
        if (isNaN(chains) || chains < 0) {
          setError('Chains must be a non-negative integer');
          return;
        }
        payload.chains = chains;
      }
      const updated = await submitAdaptiveBid(id, payload);
      setMatch(updated);
      setAdaptiveBidChains('');
      setSuccess(concede ? 'You accepted the bid!' : 'Bid submitted!');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Failed to submit bid');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReportGame = async () => {
    if (!reportWinnerId || !pm) return;
    setSubmitting(true);
    setError('');
    try {
      const nextGame = games.length + 1;
      const winnerIsP1 = reportWinnerId === pm.player1.id;
      const payload: Parameters<typeof reportStandaloneGame>[1] = {
        game_number: nextGame,
        winner_id: reportWinnerId as number,
        player1_keys: winnerIsP1 ? parseInt(reportWinnerKeys) : parseInt(reportLoserKeys),
        player2_keys: winnerIsP1 ? parseInt(reportLoserKeys) : parseInt(reportWinnerKeys),
        went_to_time: reportWentToTime,
        loser_conceded: reportLoserConceded,
      };
      if (isTriad && reportP1DeckId) payload.player1_deck_id = reportP1DeckId as number;
      if (isTriad && reportP2DeckId) payload.player2_deck_id = reportP2DeckId as number;
      await reportStandaloneGame(id, payload);
      await refresh();
      setSuccess('Game reported!');
      setReportWinnerId('');
      setReportWinnerKeys('3');
      setReportLoserKeys('0');
      setReportWentToTime(false);
      setReportLoserConceded(false);
      setReportP1DeckId('');
      setReportP2DeckId('');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Failed to report game');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCopyUrl = () => {
    navigator.clipboard.writeText(shareUrl);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
  };

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>{success}</Alert>}

      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <Typography variant="h4">Standalone Match</Typography>
        <Chip label={FORMAT_LABELS[match.format_type] || match.format_type} />
        <Chip label={`Bo${match.best_of_n}`} variant="outlined" />
        <Chip label={match.status} color={match.status === 'completed' ? 'success' : 'default'} />
      </Box>

      {/* Constraints */}
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
        <WeekConstraints week={weekLike} sets={sets} />
      </Box>

      {/* Players */}
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>Players</Typography>
          <Box sx={{ display: 'flex', gap: 4 }}>
            <Box>
              <Typography variant="body2" fontWeight="bold">{match.creator.name}</Typography>
              <Typography variant="caption" color="text.secondary">Creator (P1)</Typography>
            </Box>
            {match.opponent ? (
              <Box>
                <Typography variant="body2" fontWeight="bold">{match.opponent.name}</Typography>
                <Typography variant="caption" color="text.secondary">Opponent (P2)</Typography>
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary">Waiting for opponent…</Typography>
            )}
          </Box>
        </CardContent>
      </Card>

      {/* Share link (SETUP phase) */}
      {match.status === 'setup' && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="subtitle2" gutterBottom>Share this link with your opponent:</Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Link href={shareUrl} variant="body2" sx={{ wordBreak: 'break-all' }}>{shareUrl}</Link>
              <Button
                size="small"
                startIcon={<ContentCopyIcon />}
                onClick={handleCopyUrl}
                variant="outlined"
              >
                {copiedUrl ? 'Copied!' : 'Copy'}
              </Button>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* DECK SELECTION phase */}
      {match.status === 'deck_selection' && isParticipant && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>Deck Selection</Typography>

            {/* Open Alliance: free pod selection */}
            {isOpenAlliance && (
              <Box>
                <Typography variant="subtitle2" gutterBottom>Forge Your Alliance</Typography>
                {match.alliance_restricted_list_version && (
                  <Chip
                    label={`Restricted List v${match.alliance_restricted_list_version.version}`}
                    size="small"
                    variant="outlined"
                    sx={{ mb: 1 }}
                  />
                )}
                <AlliancePodBuilder
                  allowedSets={match.allowed_sets}
                  existingPods={isParticipant && user?.id === match.creator.id ? match.creator_pods : match.opponent_pods}
                  onPodsChange={(pods, tok, proph) => {
                    setOpenAlliancePods(pods);
                    setOpenAllianceTokenId(tok);
                    setOpenAllianceProphecyId(proph);
                  }}
                  disabled={submitting}
                />
                <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
                  <Button
                    variant="contained"
                    onClick={handleOpenAllianceSubmit}
                    disabled={submitting || openAlliancePods.length < 3}
                  >
                    Submit Alliance
                  </Button>
                  <Button
                    variant="outlined"
                    onClick={async () => {
                      await clearStandaloneAllianceSelection(id);
                      await refresh();
                    }}
                  >
                    Clear
                  </Button>
                </Box>
              </Box>
            )}

            {/* Sealed Alliance: pod selection */}
            {isSealedAlliance && (
              <Box>
                <Typography variant="subtitle2" gutterBottom>Sealed Pool</Typography>
                {sealedPool.map((entry) => (
                  <Box key={entry.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5, flexWrap: 'wrap' }}>
                    {entry.deck?.houses && <HouseIcons houses={entry.deck.houses} />}
                    <Typography variant="body2">{entry.deck?.name} ({entry.deck?.expansion_name})</Typography>
                    {entry.deck?.sas_rating != null && <Chip label={`SAS: ${entry.deck.sas_rating}`} size="small" variant="outlined" />}
                    {entry.deck && (
                      <Box sx={{ display: 'flex', gap: 0.5 }}>
                        <Link href={entry.deck.mv_url} target="_blank" rel="noopener" variant="body2">MV</Link>
                        <Link href={entry.deck.dok_url} target="_blank" rel="noopener" variant="body2">DoK</Link>
                      </Box>
                    )}
                  </Box>
                ))}
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" gutterBottom>Select 3 Pods</Typography>
                {(() => {
                  const allPairs = sealedPool.flatMap((entry) =>
                    (entry.deck?.houses || []).map((house) => ({
                      value: `${entry.deck!.db_id}:${house}`,
                      label: `${entry.deck!.name} — ${house}`,
                      house,
                    }))
                  );
                  const selectedHouses = alliancePods.filter(Boolean).map((p) => p.split(':').slice(1).join(':'));
                  const getPodOptions = (podIndex: number) => {
                    const othersSelected = selectedHouses.filter((_, i) => i !== podIndex);
                    return allPairs.filter((p) => !othersSelected.includes(p.house));
                  };
                  return (
                    <>
                      {[0, 1, 2].map((i) => (
                        <FormControl key={i} size="small" fullWidth sx={{ mb: 1 }}>
                          <InputLabel>Pod {i + 1}</InputLabel>
                          <Select
                            value={alliancePods[i]}
                            label={`Pod ${i + 1}`}
                            onChange={(e) => {
                              const newPods = [...alliancePods];
                              newPods[i] = e.target.value;
                              setAlliancePods(newPods);
                            }}
                          >
                            <MenuItem value=""><em>None</em></MenuItem>
                            {getPodOptions(i).map((opt) => (
                              <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      ))}
                    </>
                  );
                })()}
                {needsToken && (
                  <FormControl size="small" sx={{ minWidth: 200, mt: 1 }}>
                    <InputLabel>Token Deck</InputLabel>
                    <Select
                      value={allianceTokenDeckId || ''}
                      label="Token Deck"
                      onChange={(e) => setAllianceTokenDeckId(e.target.value as number)}
                    >
                      {sealedPool.map((entry) => entry.deck && (
                        <MenuItem key={entry.deck.db_id} value={entry.deck.db_id}>{entry.deck.name}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                )}
                {needsProphecy && (
                  <FormControl size="small" sx={{ minWidth: 200, mt: 1 }}>
                    <InputLabel>Prophecy Deck</InputLabel>
                    <Select
                      value={allianceProphecyDeckId || ''}
                      label="Prophecy Deck"
                      onChange={(e) => setAllianceProphecyDeckId(e.target.value as number)}
                    >
                      {sealedPool.map((entry) => entry.deck && (
                        <MenuItem key={entry.deck.db_id} value={entry.deck.db_id}>{entry.deck.name}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                )}
                <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
                  <Button variant="contained" onClick={handleAllianceSubmit} disabled={submitting || alliancePods.filter(Boolean).length < 3}>
                    Submit Alliance
                  </Button>
                  <Button variant="outlined" onClick={async () => { await clearStandaloneAllianceSelection(id); await refresh(); }}>
                    Clear
                  </Button>
                </Box>
              </Box>
            )}

            {/* Sealed Archon: pick from pool */}
            {match.format_type === 'sealed_archon' && (
              <Box>
                <Typography variant="subtitle2" gutterBottom>Your Sealed Pool</Typography>
                {sealedPool.map((entry) => (
                  <Box key={entry.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Typography variant="body2">{entry.deck?.name} ({entry.deck?.expansion_name})</Typography>
                    {entry.deck?.houses && <HouseIcons houses={entry.deck.houses} />}
                  </Box>
                ))}
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" gutterBottom>Select Your Deck</Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <FormControl size="small" sx={{ minWidth: 200 }}>
                    <InputLabel>Select Deck</InputLabel>
                    <Select
                      value={sealedDeckId}
                      label="Select Deck"
                      onChange={(e) => setSealedDeckId(e.target.value as number)}
                    >
                      {sealedPool.map((entry) => entry.deck && (
                        <MenuItem key={entry.deck.db_id} value={entry.deck.db_id}>
                          {entry.deck.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <Button variant="contained" onClick={() => handleDeckSubmit(1)} disabled={submitting || !sealedDeckId}>
                    Submit
                  </Button>
                </Box>
              </Box>
            )}

            {/* Archon / Triad: submit by URL */}
            {!isSealed && (
              <Box>
                {Array.from({ length: isTriad ? 3 : 1 }, (_, i) => i + 1).map((slot) => {
                  const sel = mySelections.find((s) => s.slot_number === slot);
                  return (
                    <Box key={slot} sx={{ mb: 2 }}>
                      <Typography variant="subtitle2">Deck {slot}</Typography>
                      {sel ? (
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="body2">{sel.deck?.name}</Typography>
                          <Chip label={`SAS: ${sel.deck?.sas_rating ?? 'N/A'}`} size="small" />
                          {sel.deck?.houses && <HouseIcons houses={sel.deck.houses} />}
                          <Button size="small" color="error" onClick={() => handleRemoveDeck(slot)}>Remove</Button>
                        </Box>
                      ) : (
                        <Box sx={{ display: 'flex', gap: 1 }}>
                          <TextField
                            size="small"
                            label="Deck URL or ID"
                            value={deckUrl}
                            onChange={(e) => setDeckUrl(e.target.value)}
                            sx={{ minWidth: 300 }}
                          />
                          <Button variant="contained" onClick={() => handleDeckSubmit(slot)} disabled={submitting}>
                            Submit
                          </Button>
                        </Box>
                      )}
                    </Box>
                  );
                })}
              </Box>
            )}

            {/* Current selections */}
            {mySelections.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2">Your selections:</Typography>
                {mySelections.map((s) => (
                  <Box key={s.id} sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    <Typography variant="body2">Slot {s.slot_number}: {s.deck?.name}</Typography>
                    <Chip label={`SAS: ${s.deck?.sas_rating ?? 'N/A'}`} size="small" />
                  </Box>
                ))}
              </Box>
            )}

            {myPods.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2">Your alliance:</Typography>
                {myPods.filter((p) => p.slot_type === 'pod').sort((a, b) => a.slot_number - b.slot_number).map((p) => (
                  <Box key={p.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                    <Chip label={`Pod ${p.slot_number}`} size="small" variant="outlined" />
                    <HouseIcons houses={[p.house_name || '']} />
                    <Typography variant="body2">{p.deck_name}</Typography>
                    {p.deck?.mv_url && <Link href={p.deck.mv_url} target="_blank" rel="noopener" variant="body2">MV</Link>}
                    {p.deck?.dok_url && <Link href={p.deck.dok_url} target="_blank" rel="noopener" variant="body2">DoK</Link>}
                  </Box>
                ))}
              </Box>
            )}

            {/* Confirm start */}
            {!myStarted && (
              <Button
                variant="contained"
                color="success"
                onClick={handleStart}
                disabled={submitting}
                sx={{ mt: 2 }}
              >
                Confirm Selection
              </Button>
            )}
            {myStarted && !bothStarted && (
              <Alert severity="info" sx={{ mt: 2 }}>Waiting for opponent to confirm their selection…</Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* PUBLISHED phase */}
      {match.status === 'published' && (
        <Box>
          {/* Strike phase (Triad, before both struck) */}
          {isTriad && bothStarted && myStrikes.length === 0 && isParticipant && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>Strike Phase</Typography>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Strike one of your opponent&apos;s decks to remove it from play.
                </Typography>
                <Typography variant="subtitle2" sx={{ mt: 1 }}>Opponent&apos;s Decks:</Typography>
                {oppSelections.map((s) => (
                  <Box key={s.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                    <Typography variant="body2">{s.deck?.name} (SAS: {s.deck?.sas_rating ?? 'N/A'})</Typography>
                    {s.deck?.houses && <HouseIcons houses={s.deck.houses} />}
                    <Chip
                      label={strickenIds.has(s.id) ? 'Struck' : 'Strike'}
                      color={strickenIds.has(s.id) ? 'error' : 'default'}
                      size="small"
                      onClick={strickenIds.has(s.id) ? undefined : () => setStrikeSelectionId(s.id)}
                      variant={strikeSelectionId === s.id ? 'filled' : 'outlined'}
                    />
                  </Box>
                ))}
                <Button
                  variant="contained"
                  color="error"
                  onClick={handleStrike}
                  disabled={submitting || !strikeSelectionId}
                  sx={{ mt: 1 }}
                >
                  Submit Strike
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Alliance pods (once both started, sealed_alliance only) */}
          {isAlliance && bothStarted && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>Alliance Pods</Typography>
                <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {([
                    { player: match.creator, pods: match.creator_pods },
                    ...(match.opponent ? [{ player: match.opponent, pods: match.opponent_pods }] : []),
                  ]).map(({ player, pods }) => (
                    <Box key={player.id}>
                      <Typography variant="subtitle2" gutterBottom>{player.name}</Typography>
                      {pods.filter((p) => p.slot_type === 'pod').sort((a, b) => a.slot_number - b.slot_number).map((p) => (
                        <Box key={p.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                          <Chip label={`Pod ${p.slot_number}`} size="small" variant="outlined" />
                          <HouseIcons houses={[p.house_name || '']} />
                          <Typography variant="body2">{p.deck_name}</Typography>
                          {p.deck?.mv_url && <Link href={p.deck.mv_url} target="_blank" rel="noopener" variant="body2">MV</Link>}
                          {p.deck?.dok_url && <Link href={p.deck.dok_url} target="_blank" rel="noopener" variant="body2">DoK</Link>}
                        </Box>
                      ))}
                    </Box>
                  ))}
                </Box>
              </CardContent>
            </Card>
          )}

          {/* Decks (once both started, non-alliance formats) */}
          {!isAlliance && bothStarted && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>Decks</Typography>
                <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <Box>
                    <Typography variant="subtitle2">{match.creator.name}</Typography>
                    {match.creator_selections.map((s) => (
                      <Box key={s.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                        <Typography variant="body2" sx={{ textDecoration: strickenIds.has(s.id) ? 'line-through' : 'none' }}>
                          {s.deck?.name}
                        </Typography>
                        {s.deck?.houses && <HouseIcons houses={s.deck.houses} />}
                        {strickenIds.has(s.id) && <Chip label="Struck" size="small" color="error" />}
                      </Box>
                    ))}
                  </Box>
                  {match.opponent && (
                    <Box>
                      <Typography variant="subtitle2">{match.opponent.name}</Typography>
                      {match.opponent_selections.map((s) => (
                        <Box key={s.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                          <Typography variant="body2" sx={{ textDecoration: strickenIds.has(s.id) ? 'line-through' : 'none' }}>
                            {s.deck?.name}
                          </Typography>
                          {s.deck?.houses && <HouseIcons houses={s.deck.houses} />}
                          {strickenIds.has(s.id) && <Chip label="Struck" size="small" color="error" />}
                        </Box>
                      ))}
                    </Box>
                  )}
                </Box>
              </CardContent>
            </Card>
          )}

          {/* Adaptive: game assignment guidance */}
          {isAdaptive && bothStarted && pm && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>Game Assignments</Typography>
                <Typography variant="body2">
                  <strong>Game 1:</strong> {match.creator.name} plays their own deck / {match.opponent?.name} plays their own deck
                </Typography>
                <Typography variant="body2">
                  <strong>Game 2:</strong> {match.creator.name} plays {match.opponent?.name}&apos;s deck / {match.opponent?.name} plays {match.creator.name}&apos;s deck
                </Typography>
                {pm.adaptive_bidding_complete && pm.adaptive_bidder_id !== null && (() => {
                  const bidderIsP1 = pm.adaptive_bidder_id === pm.player1.id;
                  const winDeckOwnerIsP1 = pm.adaptive_winning_deck_player_id === pm.player1.id;
                  // The bid winner (bidder) plays the winning deck with N chains
                  const winningDeckPlayer = bidderIsP1 ? match.creator : match.opponent;
                  const losingDeckPlayer = bidderIsP1 ? match.opponent : match.creator;
                  const winningDeckName = winDeckOwnerIsP1 ? match.creator_selections[0]?.deck?.name : match.opponent_selections[0]?.deck?.name;
                  const losingDeckName = winDeckOwnerIsP1 ? match.opponent_selections[0]?.deck?.name : match.creator_selections[0]?.deck?.name;
                  return (
                    <Typography variant="body2">
                      <strong>Game 3:</strong> {winningDeckPlayer?.name} plays {winningDeckName ?? 'the winning deck'} with {pm.adaptive_bid_chains} chains / {losingDeckPlayer?.name} plays {losingDeckName ?? 'the losing deck'}
                    </Typography>
                  );
                })()}
                {!pm.adaptive_bidding_complete && games.length < 2 && (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    Game 3 assignments will be determined by bidding after a 1-1 tie.
                  </Typography>
                )}
              </CardContent>
            </Card>
          )}

          {/* Adaptive: bidding UI (shown after 1-1 tie, before bidding complete) */}
          {isAdaptive && bothStarted && pm && pm.adaptive_bid_chains !== null && !pm.adaptive_bidding_complete && isParticipant && (() => {
            const myId = user!.id;
            const isMyTurn = pm.adaptive_bidder_id !== myId;
            const currentBidderName = pm.adaptive_bidder_id === pm.player1.id ? match.creator.name : match.opponent?.name;
            const winningDeckOwnerName = pm.adaptive_winning_deck_player_id === pm.player1.id ? match.creator.name : match.opponent?.name;
            const opponentName = isCreator ? match.opponent?.name : match.creator.name;
            return (
              <Card sx={{ mb: 2 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>Adaptive Bidding</Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    The match is tied 1-1. {winningDeckOwnerName}&apos;s deck won both games.
                    Players bid chains to play the opponent&apos;s (winning) deck in game 3.
                    The current bid holder must play the <em>winning</em> deck with that many chains.
                  </Typography>
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    Current bid: <strong>{pm.adaptive_bid_chains} chains</strong> held by <strong>{currentBidderName}</strong>
                  </Typography>
                  {isMyTurn ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      <Typography variant="body2">
                        It&apos;s your turn. You can raise the bid or accept {currentBidderName}&apos;s offer.
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                        <TextField
                          label={`Chains (> ${pm.adaptive_bid_chains})`}
                          type="number"
                          size="small"
                          value={adaptiveBidChains}
                          onChange={(e) => setAdaptiveBidChains(e.target.value)}
                          inputProps={{ min: pm.adaptive_bid_chains + 1 }}
                          sx={{ width: 160 }}
                        />
                        <Button
                          variant="contained"
                          onClick={() => handleAdaptiveBid(false)}
                          disabled={submitting || !adaptiveBidChains}
                        >
                          Raise Bid
                        </Button>
                      </Box>
                      <Button
                        variant="outlined"
                        color="secondary"
                        onClick={() => handleAdaptiveBid(true)}
                        disabled={submitting}
                      >
                        Accept — let {currentBidderName} play the winning deck with {pm.adaptive_bid_chains} chains
                      </Button>
                    </Box>
                  ) : (
                    <Alert severity="info">
                      Waiting for {opponentName} to respond to your bid of {pm.adaptive_bid_chains} chains.
                    </Alert>
                  )}
                </CardContent>
              </Card>
            );
          })()}

          {/* Adaptive: post-bidding summary */}
          {isAdaptive && pm && pm.adaptive_bidding_complete && (
            <Alert severity="success" sx={{ mb: 2 }}>
              {(() => {
                const bidderName = pm.adaptive_bidder_id === pm.player1.id ? match.creator.name : match.opponent?.name;
                return `Bidding complete — ${bidderName} plays the winning deck with ${pm.adaptive_bid_chains} chains in Game 3.`;
              })()}
            </Alert>
          )}

          {/* Score */}
          {bothStarted && pm && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>Score</Typography>
                <Typography>
                  {match.creator.name}: {p1Wins} — {match.opponent?.name}: {p2Wins}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  First to {winsNeeded} wins
                </Typography>
              </CardContent>
            </Card>
          )}

          {/* Game history */}
          {games.length > 0 && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>Games</Typography>
                {games.map((g) => {
                  const winnerName = g.winner_id === pm?.player1.id ? match.creator.name : match.opponent?.name;
                  return (
                    <Typography key={g.id} variant="body2">
                      Game {g.game_number}: {winnerName} wins ({g.player1_keys}-{g.player2_keys} keys)
                    </Typography>
                  );
                })}
              </CardContent>
            </Card>
          )}

          {/* Game report form */}
          {isParticipant && bothStarted && !matchDecided && pm && (!isAdaptive || games.length < 2 || pm.adaptive_bidding_complete) && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>Report Game {games.length + 1}</Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <FormControl size="small" sx={{ minWidth: 200 }}>
                    <InputLabel>Winner</InputLabel>
                    <Select value={reportWinnerId} label="Winner" onChange={(e) => setReportWinnerId(e.target.value as number)}>
                      <MenuItem value={pm.player1.id}>{match.creator.name}</MenuItem>
                      <MenuItem value={pm.player2.id}>{match.opponent?.name}</MenuItem>
                    </Select>
                  </FormControl>

                  <Box sx={{ display: 'flex', gap: 2 }}>
                    <TextField
                      label="Winner Keys"
                      type="number"
                      size="small"
                      value={reportWinnerKeys}
                      onChange={(e) => setReportWinnerKeys(e.target.value)}
                      inputProps={{ min: 0, max: 3 }}
                      sx={{ width: 150 }}
                    />
                    <TextField
                      label="Loser Keys"
                      type="number"
                      size="small"
                      value={reportLoserKeys}
                      onChange={(e) => setReportLoserKeys(e.target.value)}
                      inputProps={{ min: 0, max: 3 }}
                      sx={{ width: 150 }}
                    />
                  </Box>

                  {isTriad && (
                    <Box sx={{ display: 'flex', gap: 2 }}>
                      <FormControl size="small" sx={{ minWidth: 200 }}>
                        <InputLabel>{match.creator.name}&apos;s Deck</InputLabel>
                        <Select
                          value={reportP1DeckId}
                          label={`${match.creator.name}'s Deck`}
                          onChange={(e) => setReportP1DeckId(e.target.value as number)}
                        >
                          {match.creator_selections
                            .filter((s) => !strickenIds.has(s.id))
                            .map((s) => (
                              <MenuItem key={s.deck?.db_id} value={s.deck?.db_id}>
                                {s.deck?.name}
                              </MenuItem>
                            ))}
                        </Select>
                      </FormControl>
                      <FormControl size="small" sx={{ minWidth: 200 }}>
                        <InputLabel>{match.opponent?.name}&apos;s Deck</InputLabel>
                        <Select
                          value={reportP2DeckId}
                          label={`${match.opponent?.name || 'Opponent'}'s Deck`}
                          onChange={(e) => setReportP2DeckId(e.target.value as number)}
                        >
                          {match.opponent_selections
                            .filter((s) => !strickenIds.has(s.id))
                            .map((s) => (
                              <MenuItem key={s.deck?.db_id} value={s.deck?.db_id}>
                                {s.deck?.name}
                              </MenuItem>
                            ))}
                        </Select>
                      </FormControl>
                    </Box>
                  )}

                  <Box>
                    <FormControlLabel
                      control={<Checkbox checked={reportWentToTime} onChange={(e) => setReportWentToTime(e.target.checked)} />}
                      label="Went to time"
                    />
                    <FormControlLabel
                      control={<Checkbox checked={reportLoserConceded} onChange={(e) => setReportLoserConceded(e.target.checked)} />}
                      label="Loser conceded"
                    />
                  </Box>

                  <Button
                    variant="contained"
                    onClick={handleReportGame}
                    disabled={submitting || !reportWinnerId}
                  >
                    Report Game
                  </Button>
                </Box>
              </CardContent>
            </Card>
          )}
        </Box>
      )}

      {/* COMPLETED */}
      {match.status === 'completed' && pm && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Match Complete</Typography>
            <Typography>
              {p1Wins >= winsNeeded ? match.creator.name : match.opponent?.name} wins the match {Math.max(myWins, oppWins)}-{Math.min(myWins, oppWins)}!
            </Typography>
            {games.map((g) => {
              const winnerName = g.winner_id === pm.player1.id ? match.creator.name : match.opponent?.name;
              return (
                <Typography key={g.id} variant="body2" color="text.secondary">
                  Game {g.game_number}: {winnerName} ({g.player1_keys}-{g.player2_keys})
                </Typography>
              );
            })}
          </CardContent>
        </Card>
      )}
    </Container>
  );
}
