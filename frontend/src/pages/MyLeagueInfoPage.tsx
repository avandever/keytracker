import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import {
  Container,
  Typography,
  CircularProgress,
  Alert,
  Box,
  Button,
  TextField,
  Card,
  CardContent,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Tab,
  Tabs,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  FormControlLabel,
  Link,
} from '@mui/material';
import {
  getLeague,
  submitDeckSelection,
  removeDeckSelection,
  startMatch,
  reportGame,
  submitStrike,
  getSealedPool,
  getSets,
  submitAllianceSelection,
  clearAllianceSelection,
  submitSteals,
} from '../api/leagues';
import HouseIcons from '../components/HouseIcons';
import WeekConstraints, { CombinedSas } from '../components/WeekConstraints';
import type { SealedPoolEntry } from '../api/leagues';
import { useAuth } from '../contexts/AuthContext';
import { useTestUser } from '../contexts/TestUserContext';
import type {
  KeyforgeSetInfo,
  LeagueDetail,
  LeagueWeek,
  PlayerMatchupInfo,
  DeckSelectionInfo,
} from '../types';

const TOKEN_SETS = new Set([855, 600]);
const PROPHECY_EXPANSION_ID = 886;

export default function MyLeagueInfoPage() {
  const { leagueId } = useParams<{ leagueId: string }>();
  const { user } = useAuth();
  const { testUserId } = useTestUser();
  const effectiveUserId = testUserId ?? user?.id;
  const [league, setLeague] = useState<LeagueDetail | null>(null);
  const [sets, setSets] = useState<KeyforgeSetInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [activeTab, setActiveTab] = useState(0);

  // Deck selection
  const [deckUrl, setDeckUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Game reporting
  const [reportWinnerId, setReportWinnerId] = useState<number | ''>('');
  const [reportP1Keys, setReportP1Keys] = useState('3');
  const [reportP2Keys, setReportP2Keys] = useState('0');
  const [reportWentToTime, setReportWentToTime] = useState(false);
  const [reportLoserConceded, setReportLoserConceded] = useState(false);

  // Triad: strike selection and deck pickers
  const [strikeSelectionId, setStrikeSelectionId] = useState<number | ''>('');
  const [reportP1DeckId, setReportP1DeckId] = useState<number | ''>('');
  const [reportP2DeckId, setReportP2DeckId] = useState<number | ''>('');

  // Sealed: pool and selection
  const [sealedPools, setSealedPools] = useState<Record<number, SealedPoolEntry[]>>({});
  const [sealedDeckId, setSealedDeckId] = useState<number | ''>('');

  // Sealed Alliance: pod selection state (per week, single user view)
  const [alliancePods, setAlliancePods] = useState<string[]>(['', '', '']); // "deckId:house" each
  const [allianceTokenDeckId, setAllianceTokenDeckId] = useState(0);
  const [allianceProphecyDeckId, setAllianceProphecyDeckId] = useState(0);

  // Thief: steal selection (curation deck IDs) and pool deck selection
  const [thiefSteals, setThiefSteals] = useState<number[]>([]);
  const [thiefDeckId, setThiefDeckId] = useState<number | ''>('');

  const refreshCountRef = useRef(0);
  const refresh = useCallback(() => {
    if (!leagueId) return;
    setSealedPools({});
    const count = ++refreshCountRef.current;
    getLeague(parseInt(leagueId, 10))
      .then((l) => {
        if (count === refreshCountRef.current) {
          setLeague(l);
        }
      })
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  const loadSealedPool = useCallback(async (weekId: number) => {
    if (!league) return;
    if (sealedPools[weekId]) return;
    try {
      const pool = await getSealedPool(league.id, weekId);
      setSealedPools((prev) => ({ ...prev, [weekId]: pool }));
    } catch {
      // Silently fail — pool may not be generated yet
    }
  }, [league, sealedPools]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { getSets().then(setSets).catch(() => {}); }, []);

  // Pre-populate thief steal selections from server data on first load
  useEffect(() => {
    if (!league || thiefSteals.length > 0) return;
    const myTeamId = league.my_team_id;
    if (!myTeamId) return;
    const thiefWeek = (league.weeks || []).find(
      (w) => w.format_type === 'thief' && w.status === 'thief',
    );
    if (!thiefWeek) return;
    const existingIds = (thiefWeek.thief_steals || [])
      .filter((s) => s.stealing_team_id === myTeamId)
      .map((s) => s.curation_deck_id);
    if (existingIds.length > 0) setThiefSteals(existingIds);
  }, [league]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep a ref to the latest league so the polling interval can check it
  // without needing to be in the dependency array (which would reset the interval
  // on every data update, causing unstable timing).
  const leagueRef = useRef<LeagueDetail | null>(null);
  leagueRef.current = league;

  // Poll while any published week has an active (started but undecided) match
  useEffect(() => {
    const interval = setInterval(() => {
      const l = leagueRef.current;
      if (!l) return;
      const hasActiveMatch = (l.weeks || []).some((week) => {
        if (week.status !== 'published') return false;
        for (const wm of week.matchups) {
          for (const pm of wm.player_matchups) {
            if (!pm.player1_started || !pm.player2_started) continue;
            const winsNeeded = Math.ceil(week.best_of_n / 2);
            const p1Wins = pm.games.filter((g) => g.winner_id === pm.player1.id).length;
            const p2Wins = pm.games.filter((g) => g.winner_id === pm.player2.id).length;
            if (p1Wins < winsNeeded && p2Wins < winsNeeded) return true;
          }
        }
        return false;
      });
      if (hasActiveMatch) refresh();
    }, 10000);
    return () => clearInterval(interval);
  }, [refresh]);

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error && !league) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;
  if (!league || !user) return null;

  const myTeam = league.teams.find((t) => t.id === league.my_team_id);
  if (!myTeam) {
    return (
      <Container sx={{ mt: 3 }}>
        <Alert severity="info">You are not on a team in this league yet.</Alert>
      </Container>
    );
  }

  const captain = myTeam.members.find((m) => m.is_captain);
  const myMember = myTeam.members.find((m) => m.user.id === effectiveUserId);
  const weeks = league.weeks || [];

  const handleSubmitSealedDeck = async (weekId: number) => {
    if (!sealedDeckId) return;
    setError('');
    setSuccess('');
    setSubmitting(true);
    try {
      await submitDeckSelection(league.id, weekId, {
        deck_url: '', // not used for sealed
        deck_id: sealedDeckId as number,
        slot_number: 1,
      } as any);
      setSealedDeckId('');
      setSuccess('Deck selected!');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitDeck = async (weekId: number, slotNumber: number = 1) => {
    if (!deckUrl.trim()) return;
    setError('');
    setSuccess('');
    setSubmitting(true);
    try {
      await submitDeckSelection(league.id, weekId, {
        deck_url: deckUrl.trim(),
        slot_number: slotNumber,
      });
      setDeckUrl('');
      setSuccess('Deck submitted!');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemoveDeck = async (weekId: number, slot: number) => {
    setError('');
    try {
      await removeDeckSelection(league.id, weekId, slot);
      setSuccess('Deck removed');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleSubmitStrike = async (matchupId: number) => {
    if (!strikeSelectionId) return;
    setError('');
    setSuccess('');
    try {
      await submitStrike(league.id, matchupId, strikeSelectionId as number);
      setSuccess('Strike submitted!');
      setStrikeSelectionId('');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleStartMatch = async (matchupId: number) => {
    setError('');
    try {
      await startMatch(league.id, matchupId);
      setSuccess('Match started!');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleReportGame = async (matchupId: number, pm: PlayerMatchupInfo) => {
    if (!reportWinnerId) return;
    setError('');
    setSuccess('');
    try {
      const nextGameNumber = pm.games.length + 1;
      await reportGame(league.id, matchupId, {
        game_number: nextGameNumber,
        winner_id: reportWinnerId as number,
        player1_keys: parseInt(reportP1Keys, 10) || 0,
        player2_keys: parseInt(reportP2Keys, 10) || 0,
        went_to_time: reportWentToTime,
        loser_conceded: reportLoserConceded,
        player1_deck_id: reportP1DeckId || undefined,
        player2_deck_id: reportP2DeckId || undefined,
      });
      setSuccess('Game reported!');
      setReportWinnerId('');
      setReportP1Keys('3');
      setReportP2Keys('0');
      setReportWentToTime(false);
      setReportLoserConceded(false);
      setReportP1DeckId('');
      setReportP2DeckId('');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleSubmitAlliance = async (weekId: number) => {
    const pods = alliancePods
      .filter(Boolean)
      .map((s) => {
        const colonIdx = s.indexOf(':');
        return { deck_id: parseInt(s.slice(0, colonIdx), 10), house: s.slice(colonIdx + 1) };
      });
    setError('');
    setSuccess('');
    setSubmitting(true);
    try {
      const payload: Parameters<typeof submitAllianceSelection>[2] = { pods };
      if (allianceTokenDeckId) payload.token_deck_id = allianceTokenDeckId;
      if (allianceProphecyDeckId) payload.prophecy_deck_id = allianceProphecyDeckId;
      await submitAllianceSelection(league.id, weekId, payload);
      setAlliancePods(['', '', '']);
      setAllianceTokenDeckId(0);
      setAllianceProphecyDeckId(0);
      setSuccess('Alliance selection submitted!');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleClearAlliance = async (weekId: number) => {
    setError('');
    try {
      await clearAllianceSelection(league.id, weekId);
      setSuccess('Alliance selection cleared');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleSubmitThiefSteals = async (weekId: number) => {
    setError('');
    setSuccess('');
    try {
      await submitSteals(league.id, weekId, thiefSteals);
      setSuccess('Steals submitted!');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleSubmitThiefDeck = async (weekId: number) => {
    if (!thiefDeckId) return;
    setError('');
    setSuccess('');
    setSubmitting(true);
    try {
      await submitDeckSelection(league.id, weekId, {
        deck_id: thiefDeckId as number,
        slot_number: 1,
      } as any);
      setThiefDeckId('');
      setSuccess('Deck selected!');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const getMyMatchup = (week: LeagueWeek): PlayerMatchupInfo | null => {
    for (const wm of week.matchups) {
      for (const pm of wm.player_matchups) {
        if (pm.player1.id === effectiveUserId || pm.player2.id === effectiveUserId) {
          return pm;
        }
      }
    }
    return null;
  };

  const getMySelections = (week: LeagueWeek): DeckSelectionInfo[] => {
    return week.deck_selections.filter((ds) => ds.user_id === effectiveUserId);
  };

  const isMatchDecided = (pm: PlayerMatchupInfo, bestOfN: number): boolean => {
    const winsNeeded = Math.ceil(bestOfN / 2);
    const p1Wins = pm.games.filter((g) => g.winner_id === pm.player1.id).length;
    const p2Wins = pm.games.filter((g) => g.winner_id === pm.player2.id).length;
    return p1Wins >= winsNeeded || p2Wins >= winsNeeded;
  };

  const renderWeekContent = (week: LeagueWeek) => {
    const mySelections = getMySelections(week);
    const myMatchup = getMyMatchup(week);
    const canSelectDeck = week.status === 'deck_selection' || week.status === 'team_paired' || week.status === 'pairing';
    const maxSlots = week.format_type === 'triad' ? 3 : 1;

    return (
      <Box>
        {/* Deck Selection */}
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Deck Selection
              {week.status === 'published' && (
                <Chip label="Locked" size="small" color="default" sx={{ ml: 1 }} />
              )}
            </Typography>

            {/* Week constraints */}
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 1 }}>
              <WeekConstraints week={week} sets={sets} />
            </Box>

            {/* Current selections */}
            {mySelections.length > 0 && (
              <Box sx={{ mb: 2 }}>
                {mySelections.map((sel) => {
                  const bothStruck = !!myMatchup && myMatchup.strikes.length >= 2;
                  const strickenIds = myMatchup ? new Set(myMatchup.strikes.map((s) => s.struck_deck_selection_id)) : new Set<number>();
                  const isStruck = bothStruck && strickenIds.has(sel.id);
                  return (
                    <Box key={sel.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, opacity: isStruck ? 0.5 : 1, textDecoration: isStruck ? 'line-through' : 'none' }}>
                      {maxSlots > 1 && (
                        <Chip label={`Slot ${sel.slot_number}`} size="small" variant="outlined" />
                      )}
                      {sel.deck?.houses && <HouseIcons houses={sel.deck.houses} />}
                      <Typography variant="body2">
                        {sel.deck?.name || 'Unknown deck'}
                      </Typography>
                      {sel.deck?.sas_rating != null && (
                        <Chip label={`SAS: ${sel.deck.sas_rating}`} size="small" variant="outlined" />
                      )}
                      {sel.deck?.expansion_name && (
                        <Chip label={sel.deck.expansion_name} size="small" variant="outlined" />
                      )}
                      {sel.deck && (
                        <Box sx={{ display: 'flex', gap: 0.5 }}>
                          <Link href={sel.deck.mv_url} target="_blank" rel="noopener" variant="body2">MV</Link>
                          <Link href={sel.deck.dok_url} target="_blank" rel="noopener" variant="body2">DoK</Link>
                        </Box>
                      )}
                      {isStruck && <Chip label="Struck" size="small" color="error" />}
                      {canSelectDeck && (
                        <Button size="small" color="error" onClick={() => handleRemoveDeck(week.id, sel.slot_number)}>
                          Remove
                        </Button>
                      )}
                    </Box>
                  );
                })}
                {maxSlots > 1 && mySelections.length > 1 && (
                  <CombinedSas selections={mySelections} />
                )}
              </Box>
            )}

            {/* Submit new deck */}
            {canSelectDeck && mySelections.length < maxSlots &&
              week.format_type !== 'sealed_archon' &&
              week.format_type !== 'sealed_alliance' &&
              week.format_type !== 'thief' && (
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                <TextField
                  label="Deck URL or ID"
                  value={deckUrl}
                  onChange={(e) => setDeckUrl(e.target.value)}
                  size="small"
                  fullWidth
                  placeholder="https://decksofkeyforge.com/decks/..."
                />
                <Button
                  variant="contained"
                  onClick={() => handleSubmitDeck(week.id, mySelections.length + 1)}
                  disabled={submitting || !deckUrl.trim()}
                >
                  Submit
                </Button>
              </Box>
            )}

            {/* Sealed Archon: always show pool, show dropdown only when selecting */}
            {week.format_type === 'sealed_archon' && (() => {
              if (!sealedPools[week.id]) {
                loadSealedPool(week.id);
              }
              const pool = sealedPools[week.id] || [];
              return (
                <Box>
                  {pool.length > 0 ? (
                    <>
                      <Typography variant="subtitle2" gutterBottom>Your Sealed Pool</Typography>
                      <Box sx={{ mb: 2 }}>
                        {pool.map((entry) => (
                          <Box key={entry.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                            {entry.deck?.houses && <HouseIcons houses={entry.deck.houses} />}
                            <Typography variant="body2">{entry.deck?.name || 'Unknown'}</Typography>
                            {entry.deck?.sas_rating != null && (
                              <Chip label={`SAS: ${entry.deck.sas_rating}`} size="small" variant="outlined" />
                            )}
                            {entry.deck?.expansion_name && (
                              <Chip label={entry.deck.expansion_name} size="small" variant="outlined" />
                            )}
                            {entry.deck && (
                              <Box sx={{ display: 'flex', gap: 0.5 }}>
                                <Link href={entry.deck.mv_url} target="_blank" rel="noopener" variant="body2">MV</Link>
                                <Link href={entry.deck.dok_url} target="_blank" rel="noopener" variant="body2">DoK</Link>
                              </Box>
                            )}
                          </Box>
                        ))}
                      </Box>
                      {canSelectDeck && mySelections.length < 1 && (
                        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                          <FormControl size="small" sx={{ minWidth: 300 }}>
                            <InputLabel>Select deck from pool</InputLabel>
                            <Select
                              value={sealedDeckId}
                              label="Select deck from pool"
                              onChange={(e) => setSealedDeckId(e.target.value as number)}
                            >
                              {pool.map((entry) => (
                                <MenuItem key={entry.id} value={entry.deck?.db_id || 0}>
                                  {entry.deck?.name || 'Unknown'}
                                  {entry.deck?.sas_rating != null ? ` (SAS: ${entry.deck.sas_rating})` : ''}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                          <Button
                            variant="contained"
                            onClick={() => handleSubmitSealedDeck(week.id)}
                            disabled={submitting || !sealedDeckId}
                          >
                            Select
                          </Button>
                        </Box>
                      )}
                    </>
                  ) : week.status !== 'setup' ? (
                    <Typography color="text.secondary">
                      Sealed pools have not been generated yet.
                    </Typography>
                  ) : null}
                </Box>
              );
            })()}

            {/* Sealed Alliance: pod selection */}
            {week.format_type === 'sealed_alliance' && (() => {
              if (!sealedPools[week.id]) {
                loadSealedPool(week.id);
              }
              const pool = sealedPools[week.id] || [];
              const alreadySubmitted = (week.alliance_selections || []).filter((s) => s.slot_type === 'pod').length === 3;
              const needsToken = (week.allowed_sets || []).some((s) => TOKEN_SETS.has(s));
              const needsProphecy = (week.allowed_sets || []).includes(PROPHECY_EXPANSION_ID);

              // Build all (deck, house) pairs from pool
              const allPairs = pool.flatMap((entry) =>
                (entry.deck?.houses || []).map((house) => ({
                  value: `${entry.deck!.db_id}:${house}`,
                  label: `${entry.deck!.name} — ${house}${entry.deck!.token_name ? ` (token: ${entry.deck!.token_name})` : ''}`,
                  house,
                  deckId: entry.deck!.db_id!,
                }))
              );

              const selectedHouses = alliancePods.filter(Boolean).map((p) => p.split(':').slice(1).join(':'));
              const getPodOptions = (podIndex: number) => {
                const othersSelected = selectedHouses.filter((_, i) => i !== podIndex);
                return allPairs.filter((p) => !othersSelected.includes(p.house));
              };

              // Selected pod deck IDs for token/prophecy dropdowns
              const selectedPodDeckIds = alliancePods
                .filter(Boolean)
                .map((p) => parseInt(p.split(':')[0], 10))
                .filter(Boolean);
              const podPoolEntries = pool.filter((e) => e.deck?.db_id && selectedPodDeckIds.includes(e.deck.db_id));

              return (
                <Box>
                  {pool.length > 0 ? (
                    <>
                      <Typography variant="subtitle2" gutterBottom>Your Sealed Pool</Typography>
                      <Box sx={{ mb: 2 }}>
                        {pool.map((entry) => (
                          <Box key={entry.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                            {entry.deck?.houses && <HouseIcons houses={entry.deck.houses} />}
                            <Typography variant="body2">{entry.deck?.name || 'Unknown'}</Typography>
                            {entry.deck?.sas_rating != null && (
                              <Chip label={`SAS: ${entry.deck.sas_rating}`} size="small" variant="outlined" />
                            )}
                            {entry.deck?.expansion_name && (
                              <Chip label={entry.deck.expansion_name} size="small" variant="outlined" />
                            )}
                            {entry.deck?.token_name && (
                              <Chip label={`Token: ${entry.deck.token_name}`} size="small" color="secondary" variant="outlined" />
                            )}
                            {entry.deck && (
                              <Box sx={{ display: 'flex', gap: 0.5 }}>
                                <Link href={entry.deck.mv_url} target="_blank" rel="noopener" variant="body2">MV</Link>
                                <Link href={entry.deck.dok_url} target="_blank" rel="noopener" variant="body2">DoK</Link>
                              </Box>
                            )}
                          </Box>
                        ))}
                      </Box>

                      {alreadySubmitted ? (
                        <Box>
                          <Typography variant="subtitle2" gutterBottom>Current Alliance Selection</Typography>
                          {(week.alliance_selections || [])
                            .filter((s) => s.slot_type === 'pod')
                            .sort((a, b) => a.slot_number - b.slot_number)
                            .map((s) => {
                              const poolEntry = pool.find((e) => e.deck?.db_id === s.deck_id);
                              return (
                                <Box key={s.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                                  <Chip label={`Pod ${s.slot_number}`} size="small" variant="outlined" />
                                  {poolEntry?.deck?.houses && <HouseIcons houses={[s.house_name || '']} />}
                                  <Typography variant="body2">
                                    {poolEntry?.deck?.name || `Deck ${s.deck_id}`} — {s.house_name}
                                  </Typography>
                                </Box>
                              );
                            })}
                          {(week.alliance_selections || []).find((s) => s.slot_type === 'token') && (
                            <Typography variant="body2" color="text.secondary">
                              Token: {pool.find((e) => e.deck?.db_id === (week.alliance_selections || []).find((s) => s.slot_type === 'token')?.deck_id)?.deck?.name}
                            </Typography>
                          )}
                          {(week.alliance_selections || []).find((s) => s.slot_type === 'prophecy') && (
                            <Typography variant="body2" color="text.secondary">
                              Prophecy: {pool.find((e) => e.deck?.db_id === (week.alliance_selections || []).find((s) => s.slot_type === 'prophecy')?.deck_id)?.deck?.name}
                            </Typography>
                          )}
                          {canSelectDeck && (
                            <Button size="small" color="error" sx={{ mt: 1 }} onClick={() => handleClearAlliance(week.id)}>
                              Clear Selection
                            </Button>
                          )}
                        </Box>
                      ) : canSelectDeck ? (
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                          <Typography variant="subtitle2">Select 3 Pods</Typography>
                          {[0, 1, 2].map((podIndex) => (
                            <FormControl key={podIndex} size="small" fullWidth>
                              <InputLabel>Pod {podIndex + 1}</InputLabel>
                              <Select
                                value={alliancePods[podIndex]}
                                label={`Pod ${podIndex + 1}`}
                                onChange={(e) => {
                                  const updated = [...alliancePods];
                                  updated[podIndex] = e.target.value;
                                  setAlliancePods(updated);
                                }}
                              >
                                <MenuItem value=""><em>None</em></MenuItem>
                                {getPodOptions(podIndex).map((opt) => (
                                  <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                                ))}
                              </Select>
                            </FormControl>
                          ))}
                          {needsToken && podPoolEntries.length > 0 && (
                            <FormControl size="small" fullWidth>
                              <InputLabel>Token Deck</InputLabel>
                              <Select
                                value={allianceTokenDeckId || ''}
                                label="Token Deck"
                                onChange={(e) => setAllianceTokenDeckId(e.target.value as number)}
                              >
                                <MenuItem value=""><em>None</em></MenuItem>
                                {podPoolEntries.map((e) => (
                                  <MenuItem key={e.deck!.db_id} value={e.deck!.db_id!}>
                                    {e.deck!.name}{e.deck!.token_name ? ` (${e.deck!.token_name})` : ''}
                                  </MenuItem>
                                ))}
                              </Select>
                            </FormControl>
                          )}
                          {needsProphecy && podPoolEntries.length > 0 && (
                            <FormControl size="small" fullWidth>
                              <InputLabel>Prophecy Deck</InputLabel>
                              <Select
                                value={allianceProphecyDeckId || ''}
                                label="Prophecy Deck"
                                onChange={(e) => setAllianceProphecyDeckId(e.target.value as number)}
                              >
                                <MenuItem value=""><em>None</em></MenuItem>
                                {podPoolEntries.map((e) => (
                                  <MenuItem key={e.deck!.db_id} value={e.deck!.db_id!}>
                                    {e.deck!.name}
                                  </MenuItem>
                                ))}
                              </Select>
                            </FormControl>
                          )}
                          <Button
                            variant="contained"
                            onClick={() => handleSubmitAlliance(week.id)}
                            disabled={submitting || alliancePods.filter(Boolean).length < 3}
                          >
                            Submit Alliance
                          </Button>
                        </Box>
                      ) : null}
                    </>
                  ) : week.status !== 'setup' ? (
                    <Typography color="text.secondary">
                      Sealed pools have not been generated yet.
                    </Typography>
                  ) : null}
                </Box>
              );
            })()}

            {/* Thief: curation phase */}
            {week.format_type === 'thief' && (week.status === 'curation' || week.status === 'team_paired') && (
              <Typography color="text.secondary">
                Curation phase: your captain is submitting decks for the week.
              </Typography>
            )}

            {/* Thief: steal phase */}
            {week.format_type === 'thief' && week.status === 'thief' && (() => {
              // Use matchup data to find the actual paired opponent (matches backend validation)
              const myMatchup = week.matchups.find(
                (wm) => wm.team1.id === myTeam.id || wm.team2.id === myTeam.id,
              );
              const opponentTeam = myMatchup
                ? (myMatchup.team1.id === myTeam.id ? myMatchup.team2 : myMatchup.team1)
                : league.teams.find((t) => t.id !== myTeam.id);
              if (!opponentTeam) return null;
              const opponentDecks = (week.thief_curation_decks || [])
                .filter((cd) => cd.team_id === opponentTeam.id)
                .sort((a, b) => a.slot_number - b.slot_number);
              const favorThieving = myMatchup?.thief_stolen_team_id === myTeam.id;
              const stealCount = favorThieving ? Math.ceil(league.team_size / 2) : Math.floor(league.team_size / 2);
              const currentSteals = (week.thief_steals || []).filter((s) => s.stealing_team_id === myTeam.id);
              return (
                <Box>
                  <Typography variant="subtitle2" gutterBottom>
                    Steal Phase — Select {stealCount} deck{stealCount !== 1 ? 's' : ''} from {opponentTeam.name}
                  </Typography>
                  {opponentDecks.map((cd) => (
                    <Box key={cd.id} sx={{ display: 'flex', gap: 1, mb: 0.5, alignItems: 'center' }}>
                      <Checkbox
                        size="small"
                        checked={thiefSteals.includes(cd.id)}
                        onChange={(e) => {
                          setThiefSteals((prev) =>
                            e.target.checked ? [...prev, cd.id] : prev.filter((id) => id !== cd.id)
                          );
                        }}
                      />
                      <Chip label={`Slot ${cd.slot_number}`} size="small" variant="outlined" />
                      {cd.deck?.houses && <HouseIcons houses={cd.deck.houses} />}
                      <Typography variant="body2">{cd.deck?.name || 'Unknown'}</Typography>
                      {cd.deck?.sas_rating != null && (
                        <Chip label={`SAS: ${cd.deck.sas_rating}`} size="small" variant="outlined" />
                      )}
                    </Box>
                  ))}
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mt: 1 }}>
                    <Typography variant="body2">Selected: {thiefSteals.length} / {stealCount}</Typography>
                    <Button
                      size="small"
                      variant="contained"
                      onClick={() => handleSubmitThiefSteals(week.id)}
                      disabled={thiefSteals.length !== stealCount}
                    >
                      Submit Steals
                    </Button>
                  </Box>
                  {currentSteals.length > 0 && (
                    <Typography variant="body2" color="success.main" sx={{ mt: 1 }}>
                      Steals submitted ({currentSteals.length} deck{currentSteals.length !== 1 ? 's' : ''})
                    </Typography>
                  )}
                </Box>
              );
            })()}

            {/* Thief: deck selection from pool */}
            {week.format_type === 'thief' && canSelectDeck && (() => {
              const stolenByMyTeam = new Set(
                (week.thief_steals || [])
                  .filter((s) => s.stealing_team_id === myTeam.id)
                  .map((s) => s.curation_deck_id)
              );
              const stolenFromMyTeamIds = new Set(
                (week.thief_steals || [])
                  .filter((s) => {
                    const cd = (week.thief_curation_decks || []).find((c) => c.id === s.curation_deck_id);
                    return cd?.team_id === myTeam.id;
                  })
                  .map((s) => s.curation_deck_id)
              );
              const myTeamCurationDecks = (week.thief_curation_decks || []).filter(
                (cd) => cd.team_id === myTeam.id
              );
              const stolenDecks = (week.thief_curation_decks || []).filter((cd) =>
                stolenByMyTeam.has(cd.id)
              );
              const leftDecks = myTeamCurationDecks.filter((cd) => !stolenFromMyTeamIds.has(cd.id));
              const assignedDeckIds = new Set(
                mySelections.map((s) => s.deck?.db_id).filter(Boolean)
              );
              const allPoolDecks = [...stolenDecks, ...leftDecks];
              const availableDecks = allPoolDecks.filter((cd) => cd.deck && !assignedDeckIds.has(cd.deck.db_id));

              return (
                <Box>
                  {mySelections.length > 0 ? null : (
                    <>
                      {stolenDecks.length > 0 && (
                        <Box sx={{ mb: 1 }}>
                          <Typography variant="caption" color="text.secondary">Stolen from opponent:</Typography>
                          {stolenDecks.map((cd) => (
                            <Box key={cd.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5, ml: 1 }}>
                              {cd.deck?.houses && <HouseIcons houses={cd.deck.houses} />}
                              <Typography variant="body2">{cd.deck?.name || 'Unknown'}</Typography>
                              {cd.deck?.sas_rating != null && (
                                <Chip label={`SAS: ${cd.deck.sas_rating}`} size="small" variant="outlined" />
                              )}
                            </Box>
                          ))}
                        </Box>
                      )}
                      {leftDecks.length > 0 && (
                        <Box sx={{ mb: 1 }}>
                          <Typography variant="caption" color="text.secondary">Your remaining decks:</Typography>
                          {leftDecks.map((cd) => (
                            <Box key={cd.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5, ml: 1 }}>
                              {cd.deck?.houses && <HouseIcons houses={cd.deck.houses} />}
                              <Typography variant="body2">{cd.deck?.name || 'Unknown'}</Typography>
                              {cd.deck?.sas_rating != null && (
                                <Chip label={`SAS: ${cd.deck.sas_rating}`} size="small" variant="outlined" />
                              )}
                            </Box>
                          ))}
                        </Box>
                      )}
                      {availableDecks.length > 0 && (
                        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                          <FormControl size="small" sx={{ minWidth: 300 }}>
                            <InputLabel>Select deck from pool</InputLabel>
                            <Select
                              value={thiefDeckId}
                              label="Select deck from pool"
                              onChange={(e) => setThiefDeckId(e.target.value as number)}
                            >
                              {availableDecks.map((cd) => (
                                <MenuItem key={cd.id} value={cd.deck?.db_id || 0}>
                                  {cd.deck?.name || 'Unknown'}
                                  {cd.deck?.sas_rating != null ? ` (SAS: ${cd.deck.sas_rating})` : ''}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                          <Button
                            variant="contained"
                            onClick={() => handleSubmitThiefDeck(week.id)}
                            disabled={submitting || !thiefDeckId}
                          >
                            Select
                          </Button>
                        </Box>
                      )}
                    </>
                  )}
                </Box>
              );
            })()}

            {!canSelectDeck && mySelections.length === 0 && week.status !== 'setup' &&
              week.format_type !== 'thief' && week.format_type !== 'sealed_alliance' && (
              <Typography color="text.secondary">No deck selected</Typography>
            )}
            {week.status === 'setup' && (
              <Typography color="text.secondary">Deck selection has not opened yet</Typography>
            )}
          </CardContent>
        </Card>

        {/* Opponent's decks (triad, after match starts) */}
        {week.format_type === 'triad' && myMatchup && myMatchup.player1_started && myMatchup.player2_started && (() => {
          const opponentId = myMatchup.player1.id === effectiveUserId ? myMatchup.player2.id : myMatchup.player1.id;
          const opponentName = myMatchup.player1.id === effectiveUserId ? myMatchup.player2.name : myMatchup.player1.name;
          const opponentSelections = week.deck_selections.filter((ds) => ds.user_id === opponentId);
          const strickenIds = new Set(myMatchup.strikes.map((s) => s.struck_deck_selection_id));
          const bothStruck = myMatchup.strikes.length >= 2;
          if (opponentSelections.length === 0) return null;
          return (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  {opponentName}'s Decks
                </Typography>
                {opponentSelections.map((ds) => {
                  const isStruck = bothStruck && strickenIds.has(ds.id);
                  return (
                    <Box
                      key={ds.id}
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        mb: 1,
                        opacity: isStruck ? 0.5 : 1,
                        textDecoration: isStruck ? 'line-through' : 'none',
                      }}
                    >
                      {maxSlots > 1 && (
                        <Chip label={`Slot ${ds.slot_number}`} size="small" variant="outlined" />
                      )}
                      {ds.deck?.houses && <HouseIcons houses={ds.deck.houses} />}
                      <Typography variant="body2">{ds.deck?.name || 'Unknown deck'}</Typography>
                      {ds.deck?.sas_rating != null && (
                        <Chip label={`SAS: ${ds.deck.sas_rating}`} size="small" variant="outlined" />
                      )}
                      {ds.deck?.expansion_name && (
                        <Chip label={ds.deck.expansion_name} size="small" variant="outlined" />
                      )}
                      {ds.deck && (
                        <Box sx={{ display: 'flex', gap: 0.5 }}>
                          <Link href={ds.deck.mv_url} target="_blank" rel="noopener" variant="body2">MV</Link>
                          <Link href={ds.deck.dok_url} target="_blank" rel="noopener" variant="body2">DoK</Link>
                        </Box>
                      )}
                      {isStruck && <Chip label="Struck" size="small" color="error" />}
                    </Box>
                  );
                })}
              </CardContent>
            </Card>
          );
        })()}

        {/* Match section */}
        {myMatchup && week.status === 'published' && (
          <Card sx={{ mb: 2 }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Typography variant="h6">My Match</Typography>
                {myMatchup.is_feature && (
                  <Chip label="Feature Match" color="warning" size="small" />
                )}
              </Box>
              <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Avatar src={myMatchup.player1.avatar_url || undefined} sx={{ width: 32, height: 32 }}>
                    {myMatchup.player1.name?.[0]}
                  </Avatar>
                  <Typography fontWeight={myMatchup.player1.id === effectiveUserId ? 'bold' : 'normal'}>
                    {myMatchup.player1.name}
                  </Typography>
                </Box>
                <Typography color="text.secondary">vs</Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Avatar src={myMatchup.player2.avatar_url || undefined} sx={{ width: 32, height: 32 }}>
                    {myMatchup.player2.name?.[0]}
                  </Avatar>
                  <Typography fontWeight={myMatchup.player2.id === effectiveUserId ? 'bold' : 'normal'}>
                    {myMatchup.player2.name}
                  </Typography>
                </Box>
              </Box>

              {/* Start status */}
              <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                <Chip
                  label={`${myMatchup.player1.name}: ${myMatchup.player1_started ? 'Ready' : 'Not started'}`}
                  size="small"
                  color={myMatchup.player1_started ? 'success' : 'default'}
                />
                <Chip
                  label={`${myMatchup.player2.name}: ${myMatchup.player2_started ? 'Ready' : 'Not started'}`}
                  size="small"
                  color={myMatchup.player2_started ? 'success' : 'default'}
                />
              </Box>

              {/* Start button */}
              {((myMatchup.player1.id === effectiveUserId && !myMatchup.player1_started) ||
                (myMatchup.player2.id === effectiveUserId && !myMatchup.player2_started)) && (
                <Button variant="contained" onClick={() => handleStartMatch(myMatchup.id)} sx={{ mb: 2 }}>
                  Start Match
                </Button>
              )}

              {/* Triad Strike Phase */}
              {week.format_type === 'triad' && myMatchup.player1_started && myMatchup.player2_started && (() => {
                const myStrike = myMatchup.strikes.find((s) => s.striking_user_id === effectiveUserId);
                const opponentId = myMatchup.player1.id === effectiveUserId ? myMatchup.player2.id : myMatchup.player1.id;
                const opponentSelections = week.deck_selections.filter((ds) => ds.user_id === opponentId);
                const opponentStrike = myMatchup.strikes.find((s) => s.striking_user_id === opponentId);
                const bothStruck = myMatchup.strikes.length >= 2;

                return (
                  <Box sx={{ mb: 2, p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                    <Typography variant="subtitle2" gutterBottom>Strike Phase</Typography>
                    {!myStrike ? (
                      <Box>
                        <Typography variant="body2" sx={{ mb: 1 }}>Select one of your opponent's decks to strike:</Typography>
                        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                          <FormControl size="small" sx={{ minWidth: 250 }}>
                            <InputLabel>Deck to strike</InputLabel>
                            <Select
                              value={strikeSelectionId}
                              label="Deck to strike"
                              onChange={(e) => setStrikeSelectionId(e.target.value as number)}
                            >
                              {opponentSelections.map((ds) => (
                                <MenuItem key={ds.id} value={ds.id}>
                                  Slot {ds.slot_number}: {ds.deck?.name || 'Unknown'}
                                  {ds.deck?.sas_rating != null ? ` (SAS: ${ds.deck.sas_rating})` : ''}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                          <Button
                            variant="contained"
                            color="warning"
                            onClick={() => handleSubmitStrike(myMatchup.id)}
                            disabled={!strikeSelectionId}
                          >
                            Strike
                          </Button>
                        </Box>
                      </Box>
                    ) : (
                      <Box>
                        <Typography variant="body2" color="success.main">
                          You have submitted your strike.
                        </Typography>
                        {bothStruck && opponentStrike && (
                          <Box sx={{ mt: 1 }}>
                            <Typography variant="body2">
                              Opponent struck your deck: {
                                week.deck_selections.find((ds) => ds.id === opponentStrike.struck_deck_selection_id)?.deck?.name || 'Unknown'
                              }
                            </Typography>
                            <Typography variant="body2">
                              You struck: {
                                week.deck_selections.find((ds) => ds.id === myStrike.struck_deck_selection_id)?.deck?.name || 'Unknown'
                              }
                            </Typography>
                          </Box>
                        )}
                        {!bothStruck && (
                          <Typography variant="body2" color="text.secondary">
                            Waiting for opponent to submit their strike...
                          </Typography>
                        )}
                      </Box>
                    )}
                  </Box>
                );
              })()}

              {/* Games played */}
              {myMatchup.games.length > 0 && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>Games</Typography>
                  {myMatchup.games.map((g) => {
                    const winner = g.winner_id === myMatchup.player1.id
                      ? myMatchup.player1 : myMatchup.player2;
                    return (
                      <Box key={g.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                        <Chip label={`Game ${g.game_number}`} size="small" variant="outlined" />
                        <Typography variant="body2">
                          Winner: {winner.name} | Keys: {g.player1_keys}-{g.player2_keys}
                        </Typography>
                        {g.went_to_time && <Chip label="Time" size="small" color="warning" />}
                        {g.loser_conceded && <Chip label="Conceded" size="small" color="info" />}
                      </Box>
                    );
                  })}
                  {(() => {
                    const p1Wins = myMatchup.games.filter((g) => g.winner_id === myMatchup.player1.id).length;
                    const p2Wins = myMatchup.games.filter((g) => g.winner_id === myMatchup.player2.id).length;
                    return (
                      <Typography variant="body2" fontWeight="bold" sx={{ mt: 1 }}>
                        Score: {myMatchup.player1.name} {p1Wins} - {p2Wins} {myMatchup.player2.name}
                      </Typography>
                    );
                  })()}
                </Box>
              )}

              {/* Game reporting */}
              {myMatchup.player1_started && myMatchup.player2_started &&
                !isMatchDecided(myMatchup, week.best_of_n) &&
                (week.format_type !== 'triad' || myMatchup.strikes.length >= 2) && (
                <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>Report Game {myMatchup.games.length + 1}</Typography>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <FormControl fullWidth size="small">
                      <InputLabel>Winner</InputLabel>
                      <Select
                        value={reportWinnerId}
                        label="Winner"
                        onChange={(e) => setReportWinnerId(e.target.value as number)}
                      >
                        <MenuItem value={myMatchup.player1.id}>{myMatchup.player1.name}</MenuItem>
                        <MenuItem value={myMatchup.player2.id}>{myMatchup.player2.name}</MenuItem>
                      </Select>
                    </FormControl>
                    {week.format_type === 'triad' && (() => {
                      const strickenSelIds = new Set(myMatchup.strikes.map((s) => s.struck_deck_selection_id));
                      const p1Sels = week.deck_selections.filter(
                        (ds) => ds.user_id === myMatchup.player1.id && !strickenSelIds.has(ds.id)
                      );
                      const p2Sels = week.deck_selections.filter(
                        (ds) => ds.user_id === myMatchup.player2.id && !strickenSelIds.has(ds.id)
                      );
                      // Filter out decks that already won
                      const p1WonDeckIds = new Set(
                        myMatchup.games.filter((g) => g.winner_id === myMatchup.player1.id).map((g) => g.player1_deck_id)
                      );
                      const p2WonDeckIds = new Set(
                        myMatchup.games.filter((g) => g.winner_id === myMatchup.player2.id).map((g) => g.player2_deck_id)
                      );
                      const p1Available = p1Sels.filter((ds) => ds.deck?.db_id && !p1WonDeckIds.has(ds.deck.db_id));
                      const p2Available = p2Sels.filter((ds) => ds.deck?.db_id && !p2WonDeckIds.has(ds.deck.db_id));

                      return (
                        <Box sx={{ display: 'flex', gap: 2 }}>
                          <FormControl size="small" sx={{ flex: 1 }}>
                            <InputLabel>{myMatchup.player1.name}'s Deck</InputLabel>
                            <Select
                              value={reportP1DeckId}
                              label={`${myMatchup.player1.name}'s Deck`}
                              onChange={(e) => setReportP1DeckId(e.target.value as number)}
                            >
                              {p1Available.map((ds) => (
                                <MenuItem key={ds.id} value={ds.deck!.db_id!}>
                                  {ds.deck?.name || 'Unknown'}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                          <FormControl size="small" sx={{ flex: 1 }}>
                            <InputLabel>{myMatchup.player2.name}'s Deck</InputLabel>
                            <Select
                              value={reportP2DeckId}
                              label={`${myMatchup.player2.name}'s Deck`}
                              onChange={(e) => setReportP2DeckId(e.target.value as number)}
                            >
                              {p2Available.map((ds) => (
                                <MenuItem key={ds.id} value={ds.deck!.db_id!}>
                                  {ds.deck?.name || 'Unknown'}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        </Box>
                      );
                    })()}
                    <Box sx={{ display: 'flex', gap: 2 }}>
                      <FormControl size="small" sx={{ flex: 1 }}>
                        <InputLabel>{myMatchup.player1.name} Keys</InputLabel>
                        <Select value={reportP1Keys} label={`${myMatchup.player1.name} Keys`} onChange={(e) => setReportP1Keys(e.target.value)}>
                          {[0, 1, 2, 3].map((k) => <MenuItem key={k} value={String(k)}>{k}</MenuItem>)}
                        </Select>
                      </FormControl>
                      <FormControl size="small" sx={{ flex: 1 }}>
                        <InputLabel>{myMatchup.player2.name} Keys</InputLabel>
                        <Select value={reportP2Keys} label={`${myMatchup.player2.name} Keys`} onChange={(e) => setReportP2Keys(e.target.value)}>
                          {[0, 1, 2, 3].map((k) => <MenuItem key={k} value={String(k)}>{k}</MenuItem>)}
                        </Select>
                      </FormControl>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2 }}>
                      <FormControlLabel
                        control={<Checkbox checked={reportWentToTime} onChange={(e) => setReportWentToTime(e.target.checked)} size="small" />}
                        label="Went to time"
                      />
                      <FormControlLabel
                        control={<Checkbox checked={reportLoserConceded} onChange={(e) => setReportLoserConceded(e.target.checked)} size="small" />}
                        label="Loser conceded"
                      />
                    </Box>
                    <Button
                      variant="contained"
                      onClick={() => handleReportGame(myMatchup.id, myMatchup)}
                      disabled={!reportWinnerId}
                    >
                      Report Game
                    </Button>
                  </Box>
                </Box>
              )}

              {isMatchDecided(myMatchup, week.best_of_n) && (
                <Alert severity="success" sx={{ mt: 1 }}>Match complete!</Alert>
              )}
            </CardContent>
          </Card>
        )}

        {!myMatchup && week.status === 'published' && (
          <Alert severity="info">No matchup assigned for this week.</Alert>
        )}
      </Box>
    );
  };

  const topTabs = ['Team', ...(league.fee_amount != null ? ['Fee Status'] : []), ...weeks.map((w) => w.name || `Week ${w.week_number}`)];
  const feeOffset = league.fee_amount != null ? 1 : 0;
  const weekStartIdx = 1 + feeOffset;

  return (
    <Container maxWidth="sm" sx={{ mt: 3 }}>
      <Typography variant="h4" gutterBottom>{league.name}</Typography>
      <Typography variant="h5" gutterBottom>My Info</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      <Tabs
        value={activeTab}
        onChange={(_, v) => setActiveTab(v)}
        sx={{ mb: 2 }}
        variant="scrollable"
        scrollButtons="auto"
      >
        {topTabs.map((label, i) => (
          <Tab key={i} label={label} />
        ))}
      </Tabs>

      {activeTab === 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6">{myTeam.name}</Typography>
            {captain && (
              <Typography color="text.secondary" sx={{ mb: 1 }}>
                Captain: {captain.user.name}
              </Typography>
            )}
            <List dense>
              {myTeam.members.map((m) => (
                <ListItem key={m.id}>
                  <ListItemAvatar>
                    <Avatar src={m.user.avatar_url || undefined} sx={{ width: 28, height: 28 }}>
                      {m.user.name?.[0]}
                    </Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                        {m.user.name}
                        {m.is_captain && <Chip label="Captain" size="small" color="primary" />}
                        {m.user.id === effectiveUserId && <Chip label="You" size="small" variant="outlined" />}
                      </Box>
                    }
                  />
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      )}

      {league.fee_amount != null && activeTab === 1 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Fee Status</Typography>
            <Typography>
              Fee: ${league.fee_amount}
            </Typography>
            <Chip
              label={myMember?.has_paid ? 'Paid' : 'Unpaid'}
              color={myMember?.has_paid ? 'success' : 'warning'}
              sx={{ mt: 1 }}
            />
          </CardContent>
        </Card>
      )}

      {activeTab >= weekStartIdx && weeks[activeTab - weekStartIdx] && renderWeekContent(weeks[activeTab - weekStartIdx])}
    </Container>
  );
}
