import { useEffect, useState, useCallback } from 'react';
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
} from '../api/leagues';
import HouseIcons from '../components/HouseIcons';
import type { SealedPoolEntry } from '../api/leagues';
import { useAuth } from '../contexts/AuthContext';
import type {
  LeagueDetail,
  LeagueWeek,
  PlayerMatchupInfo,
  DeckSelectionInfo,
} from '../types';

const FORMAT_LABELS: Record<string, string> = {
  archon_standard: 'Archon Standard',
  triad: 'Triad',
  sealed_archon: 'Sealed Archon',
};

export default function MyLeagueInfoPage() {
  const { leagueId } = useParams<{ leagueId: string }>();
  const { user } = useAuth();
  const [league, setLeague] = useState<LeagueDetail | null>(null);
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

  const refresh = useCallback(() => {
    if (!leagueId) return;
    getLeague(parseInt(leagueId, 10))
      .then((l) => {
        setLeague(l);
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
  const myMember = myTeam.members.find((m) => m.user.id === user.id);
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

  const getMyMatchup = (week: LeagueWeek): PlayerMatchupInfo | null => {
    for (const wm of week.matchups) {
      for (const pm of wm.player_matchups) {
        if (pm.player1.id === user.id || pm.player2.id === user.id) {
          return pm;
        }
      }
    }
    return null;
  };

  const getMySelections = (week: LeagueWeek): DeckSelectionInfo[] => {
    return week.deck_selections.filter((ds) => ds.user_id === user.id);
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
    const canSelectDeck = week.status === 'deck_selection' || week.status === 'pairing';
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

            {/* Current selections */}
            {mySelections.length > 0 && (
              <Box sx={{ mb: 2 }}>
                {mySelections.map((sel) => (
                  <Box key={sel.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
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
                    {canSelectDeck && (
                      <Button size="small" color="error" onClick={() => handleRemoveDeck(week.id, sel.slot_number)}>
                        Remove
                      </Button>
                    )}
                  </Box>
                ))}
              </Box>
            )}

            {/* Submit new deck */}
            {canSelectDeck && mySelections.length < maxSlots && week.format_type !== 'sealed_archon' && (
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

            {/* Sealed Archon: show pool and dropdown */}
            {week.format_type === 'sealed_archon' && canSelectDeck && mySelections.length < 1 && (() => {
              // Load pool on first render
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
                    </>
                  ) : (
                    <Typography color="text.secondary">
                      Sealed pools have not been generated yet.
                    </Typography>
                  )}
                </Box>
              );
            })()}

            {!canSelectDeck && mySelections.length === 0 && week.status !== 'setup' && (
              <Typography color="text.secondary">No deck selected</Typography>
            )}
            {week.status === 'setup' && (
              <Typography color="text.secondary">Deck selection has not opened yet</Typography>
            )}
          </CardContent>
        </Card>

        {/* Match section */}
        {myMatchup && week.status === 'published' && (
          <Card sx={{ mb: 2 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>My Match</Typography>
              <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Avatar src={myMatchup.player1.avatar_url || undefined} sx={{ width: 32, height: 32 }}>
                    {myMatchup.player1.name?.[0]}
                  </Avatar>
                  <Typography fontWeight={myMatchup.player1.id === user.id ? 'bold' : 'normal'}>
                    {myMatchup.player1.name}
                  </Typography>
                </Box>
                <Typography color="text.secondary">vs</Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Avatar src={myMatchup.player2.avatar_url || undefined} sx={{ width: 32, height: 32 }}>
                    {myMatchup.player2.name?.[0]}
                  </Avatar>
                  <Typography fontWeight={myMatchup.player2.id === user.id ? 'bold' : 'normal'}>
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
              {((myMatchup.player1.id === user.id && !myMatchup.player1_started) ||
                (myMatchup.player2.id === user.id && !myMatchup.player2_started)) && (
                <Button variant="contained" onClick={() => handleStartMatch(myMatchup.id)} sx={{ mb: 2 }}>
                  Start Match
                </Button>
              )}

              {/* Triad Strike Phase */}
              {week.format_type === 'triad' && myMatchup.player1_started && myMatchup.player2_started && (() => {
                const myStrike = myMatchup.strikes.find((s) => s.striking_user_id === user.id);
                const opponentId = myMatchup.player1.id === user.id ? myMatchup.player2.id : myMatchup.player1.id;
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
                !isMatchDecided(myMatchup, week.best_of_n) && (
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

  return (
    <Container maxWidth="sm" sx={{ mt: 3 }}>
      <Typography variant="h4" gutterBottom>{league.name}</Typography>
      <Typography variant="h5" gutterBottom>My Info</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      <Card sx={{ mb: 3 }}>
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
                      {m.user.id === user.id && <Chip label="You" size="small" variant="outlined" />}
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>

      {league.fee_amount != null && (
        <Card sx={{ mb: 3 }}>
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

      {/* Weekly tabs */}
      {weeks.length > 0 && (
        <>
          <Tabs
            value={activeTab}
            onChange={(_, v) => setActiveTab(v)}
            sx={{ mb: 2 }}
            variant="scrollable"
            scrollButtons="auto"
          >
            {weeks.map((w) => (
              <Tab
                key={w.id}
                label={
                  <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                    {w.name || `Week ${w.week_number}`}
                    <Chip
                      label={FORMAT_LABELS[w.format_type] || w.format_type}
                      size="small"
                      sx={{ height: 18, fontSize: '0.65rem' }}
                    />
                  </Box>
                }
              />
            ))}
          </Tabs>
          {weeks[activeTab] && renderWeekContent(weeks[activeTab])}
        </>
      )}
    </Container>
  );
}
