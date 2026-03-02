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
  submitTriadShortPick,
  submitOublietteBannedHouse,
  reportStandaloneGame,
  submitAdaptiveBid,
  submitAdaptiveShortChoice,
  submitAdaptiveShortBid,
  submitExchangeBorrow,
  submitNordicAction,
  submitMoiraiAssignments,
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
  MoiraiAssignmentInfo,
} from '../types';
import type { SealedPoolEntry } from '../api/leagues';
import { alpha } from '@mui/material/styles';

const FORMAT_LABELS: Record<string, string> = {
  archon_standard: 'Archon',
  triad: 'Triad',
  sealed_archon: 'Sealed Archon',
  sealed_alliance: 'Sealed Alliance',
  adaptive: 'Adaptive',
  alliance: 'Alliance',
  reversal: 'Reversal',
  triad_short: 'Triad Short',
  oubliette: 'Oubliette',
  adaptive_short: 'Adaptive Short',
  exchange: 'Exchange',
  nordic_hexad: 'Nordic Hexad',
  moirai: 'Moirai',
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

  // Triad Short pick state
  const [triadShortPickId, setTriadShortPickId] = useState<number | ''>('');

  // Oubliette banned house state
  const [oublietteBannedHouse, setOublietteBannedHouse] = useState('');

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

  // Adaptive Short state
  const [adaptiveShortChoiceId, setAdaptiveShortChoiceId] = useState<number | ''>('');
  const [adaptiveShortBidChains, setAdaptiveShortBidChains] = useState('');

  // Exchange state
  const [exchangeBorrowId, setExchangeBorrowId] = useState<number | ''>('');

  // Nordic Hexad state
  const [nordicActionTargetId, setNordicActionTargetId] = useState<number | ''>('');

  // Moirai state: track pending assignments (game_number → deck_selection_id)
  const [moiraiAssignments, setMoiraiAssignments] = useState<Record<number, number>>({});

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
    sas_ladder_maxes: null,
    sas_ladder_feature_rung: null,
  };

  const isSealed = match.format_type === 'sealed_archon' || match.format_type === 'sealed_alliance';
  const isTriad = match.format_type === 'triad';
  const isSealedAlliance = match.format_type === 'sealed_alliance';
  const isOpenAlliance = match.format_type === 'alliance';
  const isAlliance = isSealedAlliance || isOpenAlliance;
  const isAdaptive = match.format_type === 'adaptive';
  const isReversal = match.format_type === 'reversal';
  const isTriadShort = match.format_type === 'triad_short';
  const isOubliette = match.format_type === 'oubliette';
  const isAdaptiveShort = match.format_type === 'adaptive_short';
  const isExchange = match.format_type === 'exchange';
  const isNordicHexad = match.format_type === 'nordic_hexad';
  const isMoirai = match.format_type === 'moirai';

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

  const handleOublietteBan = async () => {
    if (!oublietteBannedHouse.trim()) return;
    setSubmitting(true);
    setError('');
    try {
      const updated = await submitOublietteBannedHouse(id, oublietteBannedHouse.trim());
      setMatch(updated);
      setSuccess('Banned house submitted!');
      setOublietteBannedHouse('');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Failed to submit banned house');
    } finally {
      setSubmitting(false);
    }
  };

  const handleTriadShortPick = async () => {
    if (!triadShortPickId) return;
    setSubmitting(true);
    setError('');
    try {
      const updated = await submitTriadShortPick(id, triadShortPickId as number);
      setMatch(updated);
      setSuccess('Pick submitted!');
      setTriadShortPickId('');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Failed to submit pick');
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

  const handleNordicAction = async (phase: number) => {
    if (!nordicActionTargetId) return;
    setSubmitting(true);
    setError('');
    try {
      const updated = await submitNordicAction(id, phase, nordicActionTargetId as number);
      setMatch(updated);
      setNordicActionTargetId('');
      setSuccess(phase === 2 ? 'Protection submitted!' : 'Ban submitted!');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Failed to submit action');
    } finally {
      setSubmitting(false);
    }
  };

  const handleMoiraiAssignments = async () => {
    if (Object.keys(moiraiAssignments).length !== 3) return;
    setSubmitting(true);
    setError('');
    try {
      const payload = Object.entries(moiraiAssignments).map(([gn, selId]) => ({
        game_number: parseInt(gn),
        deck_selection_id: selId,
      }));
      const updated = await submitMoiraiAssignments(id, payload);
      setMatch(updated);
      setMoiraiAssignments({});
      setSuccess('Assignments submitted!');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Failed to submit assignments');
    } finally {
      setSubmitting(false);
    }
  };

  const handleExchangeBorrow = async () => {
    if (!exchangeBorrowId) return;
    setSubmitting(true);
    setError('');
    try {
      const updated = await submitExchangeBorrow(id, exchangeBorrowId as number);
      setMatch(updated);
      setSuccess('Borrow submitted!');
      setExchangeBorrowId('');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Failed to submit borrow');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAdaptiveShortChoice = async () => {
    if (!adaptiveShortChoiceId) return;
    setSubmitting(true);
    setError('');
    try {
      const updated = await submitAdaptiveShortChoice(id, adaptiveShortChoiceId as number);
      setMatch(updated);
      setSuccess('Choice submitted!');
      setAdaptiveShortChoiceId('');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error || 'Failed to submit choice');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAdaptiveShortBid = async (concede: boolean) => {
    setSubmitting(true);
    setError('');
    try {
      const payload: { chains?: number; concede?: boolean } = {};
      if (concede) {
        payload.concede = true;
      } else {
        const chains = parseInt(adaptiveShortBidChains);
        if (isNaN(chains) || chains < 0) {
          setError('Chains must be a non-negative integer');
          return;
        }
        payload.chains = chains;
      }
      const updated = await submitAdaptiveShortBid(id, payload);
      setMatch(updated);
      setAdaptiveShortBidChains('');
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
      if ((isTriad || isExchange || isNordicHexad || isMoirai) && reportP1DeckId) payload.player1_deck_id = reportP1DeckId as number;
      if ((isTriad || isExchange || isNordicHexad || isMoirai) && reportP2DeckId) payload.player2_deck_id = reportP2DeckId as number;
      // Reversal: player 1 plays opponent's deck, player 2 plays creator's deck
      if (isReversal) {
        const creatorDeckId = match.creator_selections[0]?.deck?.db_id;
        const opponentDeckId = match.opponent_selections[0]?.deck?.db_id;
        if (opponentDeckId) payload.player1_deck_id = opponentDeckId;
        if (creatorDeckId) payload.player2_deck_id = creatorDeckId;
      }
      // Triad Short: use picked deck IDs from revealed picks
      if (isTriadShort && pm) {
        const picks = pm.triad_short_picks || [];
        const p1Pick = picks.find((p) => p.picking_user_id === pm.player1.id);
        const p2Pick = picks.find((p) => p.picking_user_id === pm.player2.id);
        const allSels = [...match.creator_selections, ...match.opponent_selections];
        const p1Sel = allSels.find((s) => s.id === p1Pick?.picked_deck_selection_id);
        const p2Sel = allSels.find((s) => s.id === p2Pick?.picked_deck_selection_id);
        if (p1Sel?.deck?.db_id) payload.player1_deck_id = p1Sel.deck.db_id;
        if (p2Sel?.deck?.db_id) payload.player2_deck_id = p2Sel.deck.db_id;
      }
      // Adaptive Short: auto-populate decks from choices when no bidding occurred
      if (isAdaptiveShort && pm && pm.adaptive_short_bid_chains === null) {
        const choices = pm.adaptive_short_choices || [];
        const p1Choice = choices.find((c) => c.choosing_user_id === pm.player1.id);
        const p2Choice = choices.find((c) => c.choosing_user_id === pm.player2.id);
        const allSels = [...match.creator_selections, ...match.opponent_selections];
        const p1ChosenSel = allSels.find((s) => s.id === p1Choice?.chosen_deck_selection_id);
        const p2ChosenSel = allSels.find((s) => s.id === p2Choice?.chosen_deck_selection_id);
        if (p1ChosenSel?.deck?.db_id) payload.player1_deck_id = p1ChosenSel.deck.db_id;
        if (p2ChosenSel?.deck?.db_id) payload.player2_deck_id = p2ChosenSel.deck.db_id;
      }
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
        <Chip label={FORMAT_LABELS[match.format_type] || match.format_type} variant="outlined" />
        <Chip label={`Bo${match.best_of_n}`} variant="outlined" />
        <Chip label={match.status} sx={match.status === 'completed' ? (theme) => ({ bgcolor: alpha(theme.palette.success.main, 0.12), color: theme.palette.success.dark }) : undefined} />
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
                {myPods.length < 3 && (
                  <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
                    <Button
                      variant="contained"
                      onClick={handleOpenAllianceSubmit}
                      disabled={submitting || openAlliancePods.length < 3}
                    >
                      Forge Alliance
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
                )}
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
            {!isSealed && !isOpenAlliance && (
              <Box>
                {Array.from({ length: isNordicHexad ? 6 : isTriad || isTriadShort || isMoirai ? 3 : isOubliette || isAdaptiveShort || isExchange ? 2 : 1 }, (_, i) => i + 1).map((slot) => {
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

            {myPods.length > 0 && !isOpenAlliance && (
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

          {/* Triad Short: pick phase (after both struck, before game) */}
          {isTriadShort && bothStarted && pm && (() => {
            const strikes = pm.strikes || [];
            const bothStruck = strikes.length >= 2;
            const picks = pm.triad_short_picks || [];
            const bothPicked = picks.length >= 2;
            const myPickCount = pm.triad_short_picks_count ?? picks.length;
            const iAlreadyPicked = isCreator
              ? myPickCount > 0 && picks.some((p) => p.picking_user_id === pm.player1.id)
              : myPickCount > 0 && picks.some((p) => p.picking_user_id === pm.player2.id);
            const strickenFromMe = new Set(
              strikes.filter((s) => s.striking_user_id !== user?.id).map((s) => s.struck_deck_selection_id)
            );
            const myNonStruckSelections = mySelections.filter((s) => !strickenFromMe.has(s.id));

            if (!bothStruck) return null;
            if (bothPicked) {
              // Show reveal
              const myPick = picks.find((p) =>
                p.picking_user_id === (isCreator ? pm.player1.id : pm.player2.id)
              );
              const oppPick = picks.find((p) =>
                p.picking_user_id === (isCreator ? pm.player2.id : pm.player1.id)
              );
              const myPickedSel = [...mySelections, ...oppSelections].find(
                (s) => s.id === myPick?.picked_deck_selection_id
              );
              const oppPickedSel = [...mySelections, ...oppSelections].find(
                (s) => s.id === oppPick?.picked_deck_selection_id
              );
              return (
                <Alert severity="success" sx={{ mb: 2 }}>
                  <strong>Picks revealed!</strong> You play <strong>{myPickedSel?.deck?.name ?? '?'}</strong>; opponent plays <strong>{oppPickedSel?.deck?.name ?? '?'}</strong>
                </Alert>
              );
            }
            if (iAlreadyPicked || !isParticipant) {
              return (
                <Alert severity="info" sx={{ mb: 2 }}>
                  {iAlreadyPicked ? 'Pick submitted — waiting for opponent to pick.' : 'Waiting for both players to pick.'}
                </Alert>
              );
            }
            return (
              <Card sx={{ mb: 2 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>Pick Phase</Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Secretly choose one of your non-struck decks to play. Picks are revealed simultaneously.
                  </Typography>
                  {myNonStruckSelections.map((s) => (
                    <Box key={s.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                      <Typography variant="body2">{s.deck?.name} (SAS: {s.deck?.sas_rating ?? 'N/A'})</Typography>
                      {s.deck?.houses && <HouseIcons houses={s.deck.houses} />}
                      <Chip
                        label={triadShortPickId === s.id ? 'Selected' : 'Pick'}
                        color={triadShortPickId === s.id ? 'primary' : 'default'}
                        size="small"
                        onClick={() => setTriadShortPickId(s.id)}
                        variant={triadShortPickId === s.id ? 'filled' : 'outlined'}
                      />
                    </Box>
                  ))}
                  <Button
                    variant="contained"
                    onClick={handleTriadShortPick}
                    disabled={submitting || !triadShortPickId}
                    sx={{ mt: 1 }}
                  >
                    Submit Pick
                  </Button>
                </CardContent>
              </Card>
            );
          })()}

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
                        {strickenIds.has(s.id) && <Chip label="Struck" size="small" sx={(theme) => ({ bgcolor: alpha(theme.palette.error.main, 0.12), color: theme.palette.error.dark })} />}
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
                          {strickenIds.has(s.id) && <Chip label="Struck" size="small" sx={(theme) => ({ bgcolor: alpha(theme.palette.error.main, 0.12), color: theme.palette.error.dark })} />}
                        </Box>
                      ))}
                    </Box>
                  )}
                </Box>
              </CardContent>
            </Card>
          )}

          {/* Oubliette: banned house submission and eligibility display */}
          {isOubliette && bothStarted && pm && (() => {
            const myBan = isCreator ? pm.oubliette_p1_banned_house : pm.oubliette_p2_banned_house;
            const oppBan = isCreator ? pm.oubliette_p2_banned_house : pm.oubliette_p1_banned_house;
            const myEligible = isCreator ? pm.oubliette_p1_eligible_deck_ids : pm.oubliette_p2_eligible_deck_ids;
            const oppEligible = isCreator ? pm.oubliette_p2_eligible_deck_ids : pm.oubliette_p1_eligible_deck_ids;
            const bothBanned = !!pm.oubliette_p1_banned_house && !!pm.oubliette_p2_banned_house;

            return (
              <Card sx={{ mb: 2 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>Oubliette — Banned Houses</Typography>
                  {!myBan && isParticipant && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Ban a house that does NOT appear in either of your own decks. Any deck (yours or your opponent&apos;s) containing a banned house is eliminated.
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <TextField
                          size="small"
                          label="House to ban (e.g. Shadows)"
                          value={oublietteBannedHouse}
                          onChange={(e) => setOublietteBannedHouse(e.target.value)}
                          sx={{ minWidth: 220 }}
                        />
                        <Button variant="contained" color="error" onClick={handleOublietteBan} disabled={submitting || !oublietteBannedHouse.trim()}>
                          Submit Ban
                        </Button>
                      </Box>
                    </Box>
                  )}
                  {myBan && !bothBanned && (
                    <Alert severity="info" sx={{ mb: 1 }}>You banned <strong>{myBan}</strong>. Waiting for opponent to ban.</Alert>
                  )}
                  {bothBanned && (
                    <>
                      <Typography variant="body2"><strong>Your ban:</strong> {myBan}</Typography>
                      <Typography variant="body2"><strong>Opponent&apos;s ban:</strong> {oppBan}</Typography>
                      <Box sx={{ display: 'flex', gap: 4, mt: 1, flexWrap: 'wrap' }}>
                        <Box>
                          <Typography variant="subtitle2">Your eligible decks</Typography>
                          {mySelections.map((s) => {
                            const eligible = myEligible?.includes(s.deck?.db_id ?? -1);
                            return (
                              <Box key={s.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                                <Typography variant="body2" sx={{ textDecoration: eligible ? 'none' : 'line-through', color: eligible ? 'inherit' : 'text.disabled' }}>
                                  {s.deck?.name}
                                </Typography>
                                <Chip label={eligible ? 'Eligible' : 'Eliminated'} size="small" color={eligible ? 'success' : 'error'} />
                              </Box>
                            );
                          })}
                          {myEligible?.length === 0 && <Alert severity="error" sx={{ mt: 0.5 }}>All your decks eliminated — you forfeit!</Alert>}
                        </Box>
                        <Box>
                          <Typography variant="subtitle2">Opponent&apos;s eligible decks</Typography>
                          {oppSelections.map((s) => {
                            const eligible = oppEligible?.includes(s.deck?.db_id ?? -1);
                            return (
                              <Box key={s.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                                <Typography variant="body2" sx={{ textDecoration: eligible ? 'none' : 'line-through', color: eligible ? 'inherit' : 'text.disabled' }}>
                                  {s.deck?.name}
                                </Typography>
                                <Chip label={eligible ? 'Eligible' : 'Eliminated'} size="small" color={eligible ? 'success' : 'error'} />
                              </Box>
                            );
                          })}
                          {oppEligible?.length === 0 && <Alert severity="success" sx={{ mt: 0.5 }}>Opponent forfeits — all their decks eliminated!</Alert>}
                        </Box>
                      </Box>
                    </>
                  )}
                </CardContent>
              </Card>
            );
          })()}

          {/* Reversal: deck swap note */}
          {isReversal && bothStarted && (
            <Alert severity="info" sx={{ mb: 2 }}>
              <strong>Reversal:</strong> {match.creator.name} plays with {match.opponent?.name}&apos;s deck, and {match.opponent?.name} plays with {match.creator.name}&apos;s deck.
            </Alert>
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

          {/* Adaptive Short: choice phase */}
          {isAdaptiveShort && bothStarted && pm && (() => {
            const choices = pm.adaptive_short_choices || [];
            const bothChosen = choices.length >= 2;
            const myId = user?.id;
            const iAlreadyChose = choices.some((c) => c.choosing_user_id === myId);
            const allSels = [...match.creator_selections, ...match.opponent_selections];

            if (!bothChosen) {
              if (!isParticipant || iAlreadyChose) {
                return (
                  <Alert severity="info" sx={{ mb: 2 }}>
                    {iAlreadyChose ? 'Choice submitted — waiting for opponent.' : 'Waiting for both players to choose.'}
                  </Alert>
                );
              }
              return (
                <Card sx={{ mb: 2 }}>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>Adaptive Short — Choose Your Deck</Typography>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Secretly choose one deck from the combined pool of all 4 decks to play. Choices are revealed simultaneously.
                    </Typography>
                    {allSels.map((s) => (
                      <Box key={s.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        <Typography variant="body2">
                          {match.creator_selections.some((cs) => cs.id === s.id) ? match.creator.name : match.opponent?.name}: {s.deck?.name} (SAS: {s.deck?.sas_rating ?? 'N/A'})
                        </Typography>
                        {s.deck?.houses && <HouseIcons houses={s.deck.houses} />}
                        <Chip
                          label={adaptiveShortChoiceId === s.id ? 'Selected' : 'Choose'}
                          color={adaptiveShortChoiceId === s.id ? 'primary' : 'default'}
                          size="small"
                          onClick={() => setAdaptiveShortChoiceId(s.id)}
                          variant={adaptiveShortChoiceId === s.id ? 'filled' : 'outlined'}
                        />
                      </Box>
                    ))}
                    <Button
                      variant="contained"
                      onClick={handleAdaptiveShortChoice}
                      disabled={submitting || !adaptiveShortChoiceId}
                      sx={{ mt: 1 }}
                    >
                      Submit Choice
                    </Button>
                  </CardContent>
                </Card>
              );
            }

            // Both chosen — check if same deck (bidding) or different
            const p1Choice = choices.find((c) => c.choosing_user_id === pm.player1.id);
            const p2Choice = choices.find((c) => c.choosing_user_id === pm.player2.id);
            const sameDeck = p1Choice && p2Choice && p1Choice.chosen_deck_selection_id === p2Choice.chosen_deck_selection_id;

            if (sameDeck) {
              // Bidding phase
              const bidComplete = pm.adaptive_short_bidding_complete;
              const contestedSel = allSels.find((s) => s.id === p1Choice?.chosen_deck_selection_id);
              if (!bidComplete) {
                const isMyTurn = pm.adaptive_short_bidder_id !== myId;
                const currentBidderName = pm.adaptive_short_bidder_id === pm.player1.id ? match.creator.name : match.opponent?.name;
                const opponentName = isCreator ? match.opponent?.name : match.creator.name;
                return (
                  <Card sx={{ mb: 2 }}>
                    <CardContent>
                      <Typography variant="h6" gutterBottom>Adaptive Short — Bidding</Typography>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Both players chose <strong>{contestedSel?.deck?.name ?? 'the same deck'}</strong>. Bid chains to play it.
                        The bid winner plays the contested deck with that many chains. The current bid holder must play the deck with the chains they hold.
                      </Typography>
                      <Typography variant="body2" sx={{ mb: 1 }}>
                        Current bid: <strong>{pm.adaptive_short_bid_chains} chains</strong> held by <strong>{currentBidderName}</strong>
                      </Typography>
                      {isParticipant && (isMyTurn ? (
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                          <Typography variant="body2">It&apos;s your turn. Raise the bid or accept.</Typography>
                          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                            <TextField
                              label={`Chains (> ${pm.adaptive_short_bid_chains})`}
                              type="number"
                              size="small"
                              value={adaptiveShortBidChains}
                              onChange={(e) => setAdaptiveShortBidChains(e.target.value)}
                              inputProps={{ min: (pm.adaptive_short_bid_chains ?? 0) + 1 }}
                              sx={{ width: 160 }}
                            />
                            <Button
                              variant="contained"
                              onClick={() => handleAdaptiveShortBid(false)}
                              disabled={submitting || !adaptiveShortBidChains}
                            >
                              Raise Bid
                            </Button>
                          </Box>
                          <Button
                            variant="outlined"
                            color="secondary"
                            onClick={() => handleAdaptiveShortBid(true)}
                            disabled={submitting}
                          >
                            Accept — let {currentBidderName} play the deck with {pm.adaptive_short_bid_chains} chains
                          </Button>
                        </Box>
                      ) : (
                        <Alert severity="info">
                          Waiting for {opponentName} to respond to your bid of {pm.adaptive_short_bid_chains} chains.
                        </Alert>
                      ))}
                    </CardContent>
                  </Card>
                );
              }
              // Bidding complete
              const bidderName = pm.adaptive_short_bidder_id === pm.player1.id ? match.creator.name : match.opponent?.name;
              return (
                <Alert severity="success" sx={{ mb: 2 }}>
                  Bidding complete — <strong>{bidderName}</strong> plays <strong>{contestedSel?.deck?.name ?? 'the contested deck'}</strong> with <strong>{pm.adaptive_short_bid_chains} chains</strong>.
                </Alert>
              );
            }

            // Different decks chosen — reveal
            const myChoice = isCreator ? p1Choice : p2Choice;
            const oppChoice = isCreator ? p2Choice : p1Choice;
            const myChosenSel = allSels.find((s) => s.id === myChoice?.chosen_deck_selection_id);
            const oppChosenSel = allSels.find((s) => s.id === oppChoice?.chosen_deck_selection_id);
            return (
              <Alert severity="success" sx={{ mb: 2 }}>
                <strong>Choices revealed!</strong> You play <strong>{myChosenSel?.deck?.name ?? '?'}</strong>; opponent plays <strong>{oppChosenSel?.deck?.name ?? '?'}</strong>
              </Alert>
            );
          })()}

          {/* Exchange: borrow submission and exchange deck display */}
          {isExchange && bothStarted && pm && (() => {
            const borrows = pm.exchange_borrows || [];
            const bothBorrowed = borrows.length >= 2;
            const myBorrow = borrows.find((b) => b.borrowing_user_id === user?.id);
            const allSels = [...match.creator_selections, ...match.opponent_selections];

            return (
              <Card sx={{ mb: 2 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>Exchange — Borrow a Deck</Typography>
                  {!myBorrow && isParticipant && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Secretly choose one of your opponent&apos;s decks to borrow. You will play your remaining deck and the borrowed deck. Borrows are revealed simultaneously.
                      </Typography>
                      {oppSelections.map((s) => (
                        <Box key={s.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                          <Typography variant="body2">{s.deck?.name} (SAS: {s.deck?.sas_rating ?? 'N/A'})</Typography>
                          {s.deck?.houses && <HouseIcons houses={s.deck.houses} />}
                          <Chip
                            label={exchangeBorrowId === s.id ? 'Selected' : 'Borrow'}
                            color={exchangeBorrowId === s.id ? 'primary' : 'default'}
                            size="small"
                            onClick={() => setExchangeBorrowId(s.id)}
                            variant={exchangeBorrowId === s.id ? 'filled' : 'outlined'}
                          />
                        </Box>
                      ))}
                      <Button
                        variant="contained"
                        onClick={handleExchangeBorrow}
                        disabled={submitting || !exchangeBorrowId}
                        sx={{ mt: 1 }}
                      >
                        Submit Borrow
                      </Button>
                    </Box>
                  )}
                  {myBorrow && !bothBorrowed && (
                    <Alert severity="info" sx={{ mb: 1 }}>Borrow submitted — waiting for opponent.</Alert>
                  )}
                  {bothBorrowed && (() => {
                    const getExchangePool = (playerId: number, selectionSet: typeof match.creator_selections) => {
                      const oppBorrow = borrows.find((b) => b.borrowing_user_id !== playerId);
                      const myBorrowEntry = borrows.find((b) => b.borrowing_user_id === playerId);
                      const myNonBorrowed = selectionSet.filter((s) => s.id !== oppBorrow?.borrowed_deck_selection_id);
                      const borrowedSel = allSels.find((s) => s.id === myBorrowEntry?.borrowed_deck_selection_id);
                      return { nonBorrowed: myNonBorrowed, borrowed: borrowedSel };
                    };
                    const p1Pool = getExchangePool(pm.player1.id, match.creator_selections);
                    const p2Pool = getExchangePool(pm.player2.id, match.opponent_selections);
                    return (
                      <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        <Box>
                          <Typography variant="subtitle2">{match.creator.name}&apos;s exchange decks</Typography>
                          {[...p1Pool.nonBorrowed, ...(p1Pool.borrowed ? [p1Pool.borrowed] : [])].map((s) => (
                            <Box key={s.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                              <Typography variant="body2">{s.deck?.name}</Typography>
                              {s.deck?.houses && <HouseIcons houses={s.deck.houses} />}
                              {p1Pool.borrowed && s.id === p1Pool.borrowed.id && <Chip label="Borrowed" size="small" sx={(theme) => ({ bgcolor: alpha(theme.palette.info.main, 0.12), color: theme.palette.info.dark })} />}
                            </Box>
                          ))}
                        </Box>
                        <Box>
                          <Typography variant="subtitle2">{match.opponent?.name}&apos;s exchange decks</Typography>
                          {[...p2Pool.nonBorrowed, ...(p2Pool.borrowed ? [p2Pool.borrowed] : [])].map((s) => (
                            <Box key={s.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                              <Typography variant="body2">{s.deck?.name}</Typography>
                              {s.deck?.houses && <HouseIcons houses={s.deck.houses} />}
                              {p2Pool.borrowed && s.id === p2Pool.borrowed.id && <Chip label="Borrowed" size="small" sx={(theme) => ({ bgcolor: alpha(theme.palette.info.main, 0.12), color: theme.palette.info.dark })} />}
                            </Box>
                          ))}
                        </Box>
                      </Box>
                    );
                  })()}
                  {!bothBorrowed && !isParticipant && (
                    <Alert severity="info">Waiting for both players to submit borrows.</Alert>
                  )}
                </CardContent>
              </Card>
            );
          })()}

          {/* Nordic Hexad: phase-gated ban/protect UI */}
          {isNordicHexad && bothStarted && pm && (() => {
            const phase = pm.nordic_hexad_phase ?? 0;
            if (phase === 0 || phase > 3) return null;

            const pendingCount = pm.nordic_hexad_pending_phase_count ?? 0;
            const revealedActions = pm.nordic_hexad_actions || [];
            const allSels = [...match.creator_selections, ...match.opponent_selections];

            // Collect revealed bans and protects from completed phases
            const p1BannedPhase1Id = revealedActions.find((a) => a.phase === 1 && a.player_id === pm.player1.id)?.target_deck_selection_id;
            const p2BannedPhase1Id = revealedActions.find((a) => a.phase === 1 && a.player_id === pm.player2.id)?.target_deck_selection_id;
            const p1ProtectedId = revealedActions.find((a) => a.phase === 2 && a.player_id === pm.player1.id)?.target_deck_selection_id;
            const p2ProtectedId = revealedActions.find((a) => a.phase === 2 && a.player_id === pm.player2.id)?.target_deck_selection_id;

            // For phase 3, opponent's banned decks from phase 1 and their protected deck from phase 2
            const oppProtectedId = isCreator ? p2ProtectedId : p1ProtectedId;
            const oppBannedPhase1Id = isCreator ? p2BannedPhase1Id : p1BannedPhase1Id;

            const phaseLabel = phase === 1 ? 'Ban Phase 1' : phase === 2 ? 'Protect Phase' : 'Ban Phase 2';
            const phaseDesc = phase === 1
              ? "Secretly choose one of your opponent's decks to ban."
              : phase === 2
              ? 'Secretly choose one of your own decks to protect from the second ban.'
              : "Secretly choose one of your opponent's remaining (non-protected) decks to ban.";

            // Options the current player can target this phase
            const targetOptions = isParticipant
              ? (() => {
                if (phase === 1) return oppSelections;
                if (phase === 2) return mySelections;
                // Phase 3: opponent's selections minus their phase-1 ban (already removed) and excluding their protected deck
                return oppSelections.filter((s) => s.id !== oppBannedPhase1Id && s.id !== oppProtectedId);
              })()
              : [];

            return (
              <Card sx={{ mb: 2 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>Nordic Hexad — {phaseLabel}</Typography>

                  {/* Show completed phase results */}
                  {phase >= 2 && p1BannedPhase1Id != null && p2BannedPhase1Id != null && (
                    <Box sx={{ mb: 1 }}>
                      <Typography variant="subtitle2">Ban Phase 1 (revealed):</Typography>
                      <Typography variant="body2">
                        {match.creator.name} banned: <strong>{allSels.find((s) => s.id === p1BannedPhase1Id)?.deck?.name ?? '?'}</strong>
                        {' '}from {match.opponent?.name}&apos;s pool
                      </Typography>
                      <Typography variant="body2">
                        {match.opponent?.name} banned: <strong>{allSels.find((s) => s.id === p2BannedPhase1Id)?.deck?.name ?? '?'}</strong>
                        {' '}from {match.creator.name}&apos;s pool
                      </Typography>
                    </Box>
                  )}
                  {phase >= 3 && p1ProtectedId != null && p2ProtectedId != null && (
                    <Box sx={{ mb: 1 }}>
                      <Typography variant="subtitle2">Protect Phase (revealed):</Typography>
                      <Typography variant="body2">
                        {match.creator.name} protected: <strong>{allSels.find((s) => s.id === p1ProtectedId)?.deck?.name ?? '?'}</strong>
                      </Typography>
                      <Typography variant="body2">
                        {match.opponent?.name} protected: <strong>{allSels.find((s) => s.id === p2ProtectedId)?.deck?.name ?? '?'}</strong>
                      </Typography>
                    </Box>
                  )}

                  {/* Current phase action */}
                  {isParticipant && pendingCount < 2 && (
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        {phaseDesc} Actions are revealed simultaneously when both players submit.
                      </Typography>
                      {pendingCount === 1 && (
                        <Alert severity="info" sx={{ mb: 1 }}>One player has already submitted — waiting for the other.</Alert>
                      )}
                      {targetOptions.map((s) => (
                        <Box key={s.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                          <Typography variant="body2">{s.deck?.name} (SAS: {s.deck?.sas_rating ?? 'N/A'})</Typography>
                          {s.deck?.houses && <HouseIcons houses={s.deck.houses} />}
                          {phase === 3 && s.id === (isCreator ? p2ProtectedId : p1ProtectedId) ? (
                            <Chip label="Protected" size="small" color="warning" variant="outlined" />
                          ) : (
                            <Chip
                              label={nordicActionTargetId === s.id ? 'Selected' : phase === 2 ? 'Protect' : 'Ban'}
                              color={nordicActionTargetId === s.id ? 'primary' : 'default'}
                              size="small"
                              onClick={() => setNordicActionTargetId(s.id)}
                              variant={nordicActionTargetId === s.id ? 'filled' : 'outlined'}
                            />
                          )}
                        </Box>
                      ))}
                      <Button
                        variant="contained"
                        onClick={() => handleNordicAction(phase)}
                        disabled={submitting || !nordicActionTargetId}
                        sx={{ mt: 1 }}
                      >
                        Submit {phase === 2 ? 'Protection' : 'Ban'}
                      </Button>
                    </Box>
                  )}
                  {!isParticipant && (
                    <Alert severity="info">Waiting for both players to complete {phaseLabel.toLowerCase()}.</Alert>
                  )}
                </CardContent>
              </Card>
            );
          })()}

          {/* Nordic Hexad: remaining deck pool display (phase 4) */}
          {isNordicHexad && bothStarted && pm && pm.nordic_hexad_phase === 4 && (() => {
            const allSels = [...match.creator_selections, ...match.opponent_selections];
            const p1RemainingIds = new Set(pm.nordic_p1_remaining_deck_ids || []);
            const p2RemainingIds = new Set(pm.nordic_p2_remaining_deck_ids || []);
            const p1Remaining = match.creator_selections.filter((s) => s.deck?.db_id != null && p1RemainingIds.has(s.deck.db_id));
            const p2Remaining = match.opponent_selections.filter((s) => s.deck?.db_id != null && p2RemainingIds.has(s.deck.db_id));

            // Show all revealed actions as a summary
            const revealedActions = pm.nordic_hexad_actions || [];
            const getSelName = (id: number) => allSels.find((s) => s.id === id)?.deck?.name ?? '?';
            return (
              <Card sx={{ mb: 2 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>Nordic Hexad — Remaining Decks</Typography>
                  <Box sx={{ mb: 1 }}>
                    <Typography variant="subtitle2">Ban/Protect summary:</Typography>
                    {[1, 2, 3].map((ph) => {
                      const p1a = revealedActions.find((a) => a.phase === ph && a.player_id === pm.player1.id);
                      const p2a = revealedActions.find((a) => a.phase === ph && a.player_id === pm.player2.id);
                      const label = ph === 1 ? 'Ban 1' : ph === 2 ? 'Protect' : 'Ban 2';
                      return (
                        <Typography key={ph} variant="body2">
                          <strong>{label}:</strong>{' '}
                          {match.creator.name}: {p1a ? getSelName(p1a.target_deck_selection_id) : '?'},{' '}
                          {match.opponent?.name}: {p2a ? getSelName(p2a.target_deck_selection_id) : '?'}
                        </Typography>
                      );
                    })}
                  </Box>
                  <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap', mt: 1 }}>
                    <Box>
                      <Typography variant="subtitle2">{match.creator.name}&apos;s remaining decks</Typography>
                      {p1Remaining.map((s) => (
                        <Box key={s.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                          <Typography variant="body2">{s.deck?.name}</Typography>
                          {s.deck?.houses && <HouseIcons houses={s.deck.houses} />}
                        </Box>
                      ))}
                    </Box>
                    <Box>
                      <Typography variant="subtitle2">{match.opponent?.name}&apos;s remaining decks</Typography>
                      {p2Remaining.map((s) => (
                        <Box key={s.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                          <Typography variant="body2">{s.deck?.name}</Typography>
                          {s.deck?.houses && <HouseIcons houses={s.deck.houses} />}
                        </Box>
                      ))}
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            );
          })()}

          {/* Moirai: assignment phase and game deck display */}
          {isMoirai && bothStarted && pm && (() => {
            const assignments = pm.moirai_assignments || null;
            const assignmentsRevealed = assignments !== null && assignments.length === 6;
            const myCount = assignmentsRevealed
              ? 0
              : (pm.moirai_assignments_count ?? 0);
            // Helpers
            const allSels = [...match.creator_selections, ...match.opponent_selections];
            const getSelById = (id: number) => allSels.find((s) => s.id === id);

            // Compute per-game deck assignments after reveal
            const getGameDecks = (gameNumber: number) => {
              if (!assignments) return null;
              const p1Id = pm.player1.id;
              const p1Assigns: Record<number, number> = {};
              const p2Assigns: Record<number, number> = {};
              assignments.forEach((a: MoiraiAssignmentInfo) => {
                if (a.assigning_user_id === p1Id) p1Assigns[a.game_number] = a.assigned_deck_selection_id;
                else p2Assigns[a.game_number] = a.assigned_deck_selection_id;
              });
              if (gameNumber === 1) {
                // P1 plays what P2 assigned for G1 (from P1's pool); P2 plays what P1 assigned for G1 (from P2's pool)
                return { p1Sel: getSelById(p2Assigns[1]), p2Sel: getSelById(p1Assigns[1]) };
              } else if (gameNumber === 2) {
                // Reversal: P1 plays what P1 assigned for G2 (from P2's pool); P2 plays what P2 assigned for G2 (from P1's pool)
                return { p1Sel: getSelById(p1Assigns[2]), p2Sel: getSelById(p2Assigns[2]) };
              }
              return null;
            };

            // G3 pool: P1's G3 deck = what P2 assigned for G3 from P1's pool; P2's G3 deck = what P1 assigned for G3 from P2's pool
            const getG3Pool = () => {
              if (!assignments) return null;
              const p1Id = pm.player1.id;
              const p1Assigns: Record<number, number> = {};
              const p2Assigns: Record<number, number> = {};
              assignments.forEach((a: MoiraiAssignmentInfo) => {
                if (a.assigning_user_id === p1Id) p1Assigns[a.game_number] = a.assigned_deck_selection_id;
                else p2Assigns[a.game_number] = a.assigned_deck_selection_id;
              });
              return { p1Sel: getSelById(p2Assigns[3]), p2Sel: getSelById(p1Assigns[3]) };
            };

            return (
              <Card sx={{ mb: 2 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>Moirai — Game Assignments</Typography>

                  {!assignmentsRevealed && isParticipant && (
                    <Box>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Secretly assign each of your opponent&apos;s 3 decks to a game slot (G1=Archon, G2=Reversal, G3=Adaptive Short).
                        Assignments are revealed simultaneously when both players submit.
                      </Typography>
                      {myCount === 3 && (
                        <Alert severity="info" sx={{ mb: 1 }}>Your assignments submitted — waiting for opponent.</Alert>
                      )}
                      {myCount < 3 && (
                        <Box sx={{ mb: 2 }}>
                          {[1, 2, 3].map((gameNum) => (
                            <Box key={gameNum} sx={{ mb: 1 }}>
                              <Typography variant="subtitle2">Game {gameNum} ({gameNum === 1 ? 'Archon' : gameNum === 2 ? 'Reversal' : 'Adaptive Short'}):</Typography>
                              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                {oppSelections.map((s) => {
                                  const alreadyAssignedToOtherSlot = Object.entries(moiraiAssignments).some(
                                    ([gn, selId]) => selId === s.id && parseInt(gn) !== gameNum
                                  );
                                  const selected = moiraiAssignments[gameNum] === s.id;
                                  return (
                                    <Box key={s.id} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                      <Typography variant="body2" sx={{ mr: 0.5 }}>{s.deck?.name}</Typography>
                                      {s.deck?.houses && <HouseIcons houses={s.deck.houses} />}
                                      <Chip
                                        label={selected ? 'Assigned' : alreadyAssignedToOtherSlot ? 'Used' : 'Assign'}
                                        color={selected ? 'primary' : 'default'}
                                        size="small"
                                        disabled={alreadyAssignedToOtherSlot}
                                        onClick={() => !alreadyAssignedToOtherSlot && setMoiraiAssignments((prev) => ({ ...prev, [gameNum]: s.id }))}
                                        variant={selected ? 'filled' : 'outlined'}
                                      />
                                    </Box>
                                  );
                                })}
                              </Box>
                            </Box>
                          ))}
                          <Button
                            variant="contained"
                            onClick={handleMoiraiAssignments}
                            disabled={submitting || Object.keys(moiraiAssignments).length !== 3}
                            sx={{ mt: 1 }}
                          >
                            Submit Assignments
                          </Button>
                        </Box>
                      )}
                    </Box>
                  )}
                  {!assignmentsRevealed && !isParticipant && (
                    <Alert severity="info">Waiting for both players to submit assignments.</Alert>
                  )}

                  {assignmentsRevealed && (
                    <Box>
                      {[1, 2, 3].map((gameNum) => {
                        const gameLabel = gameNum === 1 ? 'G1 (Archon)' : gameNum === 2 ? 'G2 (Reversal)' : 'G3 (Adaptive Short)';
                        if (gameNum === 3) {
                          const g3 = getG3Pool();
                          return (
                            <Box key={gameNum} sx={{ mb: 0.5 }}>
                              <Typography variant="body2">
                                <strong>{gameLabel}:</strong>{' '}
                                {match.creator.name}: {g3?.p1Sel?.deck?.name ?? '?'},{' '}
                                {match.opponent?.name}: {g3?.p2Sel?.deck?.name ?? '?'}
                                {' '}(pool — Adaptive Short choice required)
                              </Typography>
                            </Box>
                          );
                        }
                        const decks = getGameDecks(gameNum);
                        return (
                          <Box key={gameNum} sx={{ mb: 0.5 }}>
                            <Typography variant="body2">
                              <strong>{gameLabel}:</strong>{' '}
                              {match.creator.name}: {decks?.p1Sel?.deck?.name ?? '?'},{' '}
                              {match.opponent?.name}: {decks?.p2Sel?.deck?.name ?? '?'}
                            </Typography>
                          </Box>
                        );
                      })}
                    </Box>
                  )}
                </CardContent>
              </Card>
            );
          })()}

          {/* Moirai G3: Adaptive Short choice phase (after 2 games are played and assignments revealed) */}
          {isMoirai && bothStarted && pm && pm.moirai_assignments && pm.moirai_assignments.length === 6 && games.length >= 2 && (() => {
            const choices = pm.adaptive_short_choices || [];
            const bothChose = choices.length >= 2;
            const myChoice = choices.find((c) => c.choosing_user_id === user?.id);
            const allSels = [...match.creator_selections, ...match.opponent_selections];

            // Compute G3 pool
            const p1Id = pm.player1.id;
            const p1Assigns: Record<number, number> = {};
            const p2Assigns: Record<number, number> = {};
            pm.moirai_assignments.forEach((a: MoiraiAssignmentInfo) => {
              if (a.assigning_user_id === p1Id) p1Assigns[a.game_number] = a.assigned_deck_selection_id;
              else p2Assigns[a.game_number] = a.assigned_deck_selection_id;
            });
            const p1G3SelId = p2Assigns[3];
            const p2G3SelId = p1Assigns[3];
            const g3Pool = [p1G3SelId, p2G3SelId].filter(Boolean).map((selId) => allSels.find((s) => s.id === selId)).filter(Boolean) as typeof allSels;

            if (matchDecided) return null;

            return (
              <Card sx={{ mb: 2 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>Moirai G3 — Adaptive Short Choice</Typography>
                  {!bothChose && (
                    <>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Secretly choose one deck from the G3 pool to play. If both choose the same deck, a chain-bid auction determines who plays it.
                      </Typography>
                      {isParticipant && !myChoice && (
                        <Box sx={{ mb: 1 }}>
                          {g3Pool.map((s) => (
                            <Box key={s.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                              <Typography variant="body2">{s.deck?.name} (SAS: {s.deck?.sas_rating ?? 'N/A'})</Typography>
                              {s.deck?.houses && <HouseIcons houses={s.deck.houses} />}
                              <Chip
                                label={adaptiveShortChoiceId === s.id ? 'Selected' : 'Choose'}
                                color={adaptiveShortChoiceId === s.id ? 'primary' : 'default'}
                                size="small"
                                onClick={() => setAdaptiveShortChoiceId(s.id)}
                                variant={adaptiveShortChoiceId === s.id ? 'filled' : 'outlined'}
                              />
                            </Box>
                          ))}
                          <Button
                            variant="contained"
                            onClick={async () => {
                              if (!adaptiveShortChoiceId) return;
                              setSubmitting(true); setError('');
                              try {
                                const updated = await submitAdaptiveShortChoice(id, adaptiveShortChoiceId as number);
                                setMatch(updated); setAdaptiveShortChoiceId('');
                                setSuccess('G3 choice submitted!');
                              } catch (e: unknown) {
                                const err = e as { response?: { data?: { error?: string } } };
                                setError(err.response?.data?.error || 'Failed');
                              } finally { setSubmitting(false); }
                            }}
                            disabled={submitting || !adaptiveShortChoiceId}
                            sx={{ mt: 1 }}
                          >
                            Submit G3 Choice
                          </Button>
                        </Box>
                      )}
                      {isParticipant && myChoice && (
                        <Alert severity="info">G3 choice submitted — waiting for opponent.</Alert>
                      )}
                      {!isParticipant && (
                        <Alert severity="info">Waiting for both players to choose G3 deck.</Alert>
                      )}
                    </>
                  )}
                  {bothChose && (() => {
                    const p1Choice = choices.find((c) => c.choosing_user_id === pm.player1.id);
                    const p2Choice = choices.find((c) => c.choosing_user_id === pm.player2.id);
                    const myChoiceEntry = isCreator ? p1Choice : p2Choice;
                    const oppChoiceEntry = isCreator ? p2Choice : p1Choice;
                    if (!p1Choice || !p2Choice) return null;

                    const contestedSelId = p1Choice.chosen_deck_selection_id;
                    const sameDeck = p1Choice.chosen_deck_selection_id === p2Choice.chosen_deck_selection_id;
                    if (!sameDeck) {
                      const myChosenSel = allSels.find((s) => s.id === myChoiceEntry?.chosen_deck_selection_id);
                      const oppChosenSel = allSels.find((s) => s.id === oppChoiceEntry?.chosen_deck_selection_id);
                      return (
                        <Alert severity="success">
                          <strong>Choices revealed!</strong> You play <strong>{myChosenSel?.deck?.name ?? '?'}</strong>; opponent plays <strong>{oppChosenSel?.deck?.name ?? '?'}</strong>
                        </Alert>
                      );
                    }

                    // Same deck — bidding phase
                    const contestedSel = allSels.find((s) => s.id === contestedSelId);
                    const bidComplete = pm.adaptive_short_bidding_complete;
                    const bidChains = pm.adaptive_short_bid_chains;
                    const bidderId = pm.adaptive_short_bidder_id;
                    const bidderName = bidderId === pm.player1.id ? match.creator.name : match.opponent?.name;
                    const iAmBidder = bidderId === user?.id;

                    if (bidComplete) {
                      return (
                        <Alert severity="success">
                          Bidding complete — <strong>{bidderName}</strong> plays <strong>{contestedSel?.deck?.name ?? '?'}</strong> with <strong>{bidChains} chains</strong>.
                        </Alert>
                      );
                    }

                    return (
                      <Box>
                        <Alert severity="warning" sx={{ mb: 1 }}>
                          Both chose <strong>{contestedSel?.deck?.name}</strong>. Chain bid: current bid = <strong>{bidChains ?? 0}</strong>. {iAmBidder ? 'Your opponent must raise or concede.' : 'Your turn — raise the bid or concede.'}
                        </Alert>
                        {isParticipant && !iAmBidder && (
                          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                            <TextField
                              size="small"
                              type="number"
                              label="Chains"
                              value={adaptiveShortBidChains}
                              onChange={(e) => setAdaptiveShortBidChains(e.target.value)}
                              sx={{ width: 100 }}
                            />
                            <Button
                              variant="contained"
                              onClick={async () => {
                                setSubmitting(true); setError('');
                                try {
                                  const updated = await submitAdaptiveShortBid(id, { chains: parseInt(adaptiveShortBidChains) });
                                  setMatch(updated); setAdaptiveShortBidChains('');
                                } catch (e: unknown) {
                                  const err = e as { response?: { data?: { error?: string } } };
                                  setError(err.response?.data?.error || 'Failed');
                                } finally { setSubmitting(false); }
                              }}
                              disabled={submitting || !adaptiveShortBidChains}
                            >
                              Raise Bid
                            </Button>
                            <Button
                              variant="outlined"
                              color="error"
                              onClick={async () => {
                                setSubmitting(true); setError('');
                                try {
                                  const updated = await submitAdaptiveShortBid(id, { concede: true });
                                  setMatch(updated);
                                } catch (e: unknown) {
                                  const err = e as { response?: { data?: { error?: string } } };
                                  setError(err.response?.data?.error || 'Failed');
                                } finally { setSubmitting(false); }
                              }}
                              disabled={submitting}
                            >
                              Concede
                            </Button>
                          </Box>
                        )}
                      </Box>
                    );
                  })()}
                </CardContent>
              </Card>
            );
          })()}

          {/* Moirai G1/G2/G3 deck selectors in game form */}

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
          {isParticipant && bothStarted && !matchDecided && pm && (!isAdaptive || games.length < 2 || pm.adaptive_bidding_complete) && (!isTriadShort || (pm.triad_short_picks || []).length >= 2) && (!isOubliette || (!!pm.oubliette_p1_banned_house && !!pm.oubliette_p2_banned_house)) && (!isAdaptiveShort || ((pm.adaptive_short_choices || []).length >= 2 && (pm.adaptive_short_bid_chains === null || !!pm.adaptive_short_bidding_complete))) && (!isExchange || (pm.exchange_borrows || []).length >= 2) && (!isNordicHexad || pm.nordic_hexad_phase === 4) && (!isMoirai || ((pm.moirai_assignments || []).length >= 6 && (games.length < 2 || ((pm.adaptive_short_choices || []).length >= 2 && (pm.adaptive_short_bid_chains === null || !!pm.adaptive_short_bidding_complete))))) && (
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

                  {isNordicHexad && pm && pm.nordic_hexad_phase === 4 && (() => {
                    const p1RemainingIds = new Set(pm.nordic_p1_remaining_deck_ids || []);
                    const p2RemainingIds = new Set(pm.nordic_p2_remaining_deck_ids || []);
                    return (
                      <Box sx={{ display: 'flex', gap: 2 }}>
                        <FormControl size="small" sx={{ minWidth: 200 }}>
                          <InputLabel>{match.creator.name}&apos;s Deck</InputLabel>
                          <Select
                            value={reportP1DeckId}
                            label={`${match.creator.name}'s Deck`}
                            onChange={(e) => setReportP1DeckId(e.target.value as number)}
                          >
                            {match.creator_selections
                              .filter((s) => s.deck?.db_id != null && p1RemainingIds.has(s.deck.db_id))
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
                              .filter((s) => s.deck?.db_id != null && p2RemainingIds.has(s.deck.db_id))
                              .map((s) => (
                                <MenuItem key={s.deck?.db_id} value={s.deck?.db_id}>
                                  {s.deck?.name}
                                </MenuItem>
                              ))}
                          </Select>
                        </FormControl>
                      </Box>
                    );
                  })()}

                  {isMoirai && pm && pm.moirai_assignments && pm.moirai_assignments.length === 6 && (() => {
                    // Compute the expected deck for each player based on game number
                    const allSels = [...match.creator_selections, ...match.opponent_selections];
                    const p1Id = pm.player1.id;
                    const p1Assigns: Record<number, number> = {};
                    const p2Assigns: Record<number, number> = {};
                    pm.moirai_assignments.forEach((a: MoiraiAssignmentInfo) => {
                      if (a.assigning_user_id === p1Id) p1Assigns[a.game_number] = a.assigned_deck_selection_id;
                      else p2Assigns[a.game_number] = a.assigned_deck_selection_id;
                    });
                    const gn = games.length + 1;
                    let p1Sel: typeof allSels[0] | undefined;
                    let p2Sel: typeof allSels[0] | undefined;
                    if (gn === 1) {
                      p1Sel = allSels.find((s) => s.id === p2Assigns[1]);
                      p2Sel = allSels.find((s) => s.id === p1Assigns[1]);
                    } else if (gn === 2) {
                      p1Sel = allSels.find((s) => s.id === p1Assigns[2]);
                      p2Sel = allSels.find((s) => s.id === p2Assigns[2]);
                    } else {
                      // G3: from adaptive short choices
                      const choices = pm.adaptive_short_choices || [];
                      const p1Choice = choices.find((c) => c.choosing_user_id === pm.player1.id);
                      const p2Choice = choices.find((c) => c.choosing_user_id === pm.player2.id);
                      if (p1Choice && p2Choice) {
                        const bidderId = pm.adaptive_short_bidder_id;
                        if (p1Choice.chosen_deck_selection_id === p2Choice.chosen_deck_selection_id) {
                          // Same deck chosen — bidder plays contested; other plays remaining
                          const contestedSel = allSels.find((s) => s.id === p1Choice.chosen_deck_selection_id);
                          const p1G3SelId = p2Assigns[3];
                          const p2G3SelId = p1Assigns[3];
                          const otherSelId = p1Choice.chosen_deck_selection_id === p1G3SelId ? p2G3SelId : p1G3SelId;
                          const otherSel = allSels.find((s) => s.id === otherSelId);
                          if (bidderId === pm.player1.id) { p1Sel = contestedSel; p2Sel = otherSel; }
                          else { p1Sel = otherSel; p2Sel = contestedSel; }
                        } else {
                          p1Sel = allSels.find((s) => s.id === p1Choice.chosen_deck_selection_id);
                          p2Sel = allSels.find((s) => s.id === p2Choice.chosen_deck_selection_id);
                        }
                      }
                    }
                    // Auto-populate when deck is determined
                    if (p1Sel?.deck?.db_id && !reportP1DeckId) setReportP1DeckId(p1Sel.deck.db_id);
                    if (p2Sel?.deck?.db_id && !reportP2DeckId) setReportP2DeckId(p2Sel.deck.db_id);
                    return (
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          G{gn} decks: <strong>{match.creator.name}</strong>: {p1Sel?.deck?.name ?? '?'} | <strong>{match.opponent?.name}</strong>: {p2Sel?.deck?.name ?? '?'}
                        </Typography>
                      </Box>
                    );
                  })()}

                  {isExchange && pm && (() => {
                    const borrows = pm.exchange_borrows || [];
                    const allSels = [...match.creator_selections, ...match.opponent_selections];
                    // Compute exchange deck pools: own non-borrowed + borrowed from opponent
                    const getExchangePool = (playerId: number, selectionSet: typeof match.creator_selections) => {
                      const oppBorrow = borrows.find((b) => b.borrowing_user_id !== playerId);
                      const myBorrow = borrows.find((b) => b.borrowing_user_id === playerId);
                      const myNonBorrowed = selectionSet.filter((s) => s.id !== oppBorrow?.borrowed_deck_selection_id);
                      const borrowedSel = allSels.find((s) => s.id === myBorrow?.borrowed_deck_selection_id);
                      return [...myNonBorrowed, ...(borrowedSel ? [borrowedSel] : [])];
                    };
                    const p1Pool = getExchangePool(pm.player1.id, match.creator_selections);
                    const p2Pool = getExchangePool(pm.player2.id, match.opponent_selections);
                    return (
                      <Box sx={{ display: 'flex', gap: 2 }}>
                        <FormControl size="small" sx={{ minWidth: 200 }}>
                          <InputLabel>{match.creator.name}&apos;s Deck</InputLabel>
                          <Select
                            value={reportP1DeckId}
                            label={`${match.creator.name}'s Deck`}
                            onChange={(e) => setReportP1DeckId(e.target.value as number)}
                          >
                            {p1Pool.map((s) => (
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
                            {p2Pool.map((s) => (
                              <MenuItem key={s.deck?.db_id} value={s.deck?.db_id}>
                                {s.deck?.name}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      </Box>
                    );
                  })()}

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

            {/* Deck details for both players */}
            <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap', mt: 2 }}>
              {([
                { player: match.creator, selections: match.creator_selections, pods: match.creator_pods },
                ...(match.opponent ? [{ player: match.opponent, selections: match.opponent_selections, pods: match.opponent_pods }] : []),
              ]).map(({ player, selections, pods }) => (
                <Box key={player.id}>
                  <Typography variant="subtitle2" gutterBottom>{player.name}</Typography>
                  {isAlliance ? (
                    pods.filter((p) => p.slot_type === 'pod').sort((a, b) => a.slot_number - b.slot_number).map((p) => (
                      <Box key={p.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                        <Chip label={`Pod ${p.slot_number}`} size="small" variant="outlined" />
                        <HouseIcons houses={[p.house_name || '']} />
                        <Typography variant="body2">{p.deck_name}</Typography>
                        {p.deck?.mv_url && <Link href={p.deck.mv_url} target="_blank" rel="noopener" variant="body2">MV</Link>}
                        {p.deck?.dok_url && <Link href={p.deck.dok_url} target="_blank" rel="noopener" variant="body2">DoK</Link>}
                      </Box>
                    ))
                  ) : (
                    selections.map((s) => (
                      <Box key={s.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                        <Typography variant="body2">{s.deck?.name}</Typography>
                        {s.deck?.houses && <HouseIcons houses={s.deck.houses} />}
                        {s.deck?.sas_rating != null && <Chip label={`SAS ${s.deck.sas_rating}`} size="small" variant="outlined" />}
                        {s.deck?.mv_url && <Link href={s.deck.mv_url} target="_blank" rel="noopener" variant="body2">MV</Link>}
                        {s.deck?.dok_url && <Link href={s.deck.dok_url} target="_blank" rel="noopener" variant="body2">DoK</Link>}
                      </Box>
                    ))
                  )}
                </Box>
              ))}
            </Box>
          </CardContent>
        </Card>
      )}
    </Container>
  );
}
