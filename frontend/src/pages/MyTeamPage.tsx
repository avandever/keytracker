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
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Switch,
  Chip,
  Tab,
  Tabs,
  Link,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Checkbox,
} from '@mui/material';
import {
  getLeague,
  updateTeam,
  toggleFeePaid,
  submitDeckSelection,
  removeDeckSelection,
  getSealedPool,
  getSets,
  setFeatureDesignation,
  clearFeatureDesignation,
  submitAllianceSelection,
  clearAllianceSelection,
  submitCurationDeck,
  removeCurationDeck,
  submitSteals,
} from '../api/leagues';
import HouseIcons from '../components/HouseIcons';
import WeekConstraints, { CombinedSas } from '../components/WeekConstraints';
import { useAuth } from '../contexts/AuthContext';
import type { KeyforgeSetInfo, LeagueDetail, LeagueWeek, DeckSelectionInfo } from '../types';
import type { SealedPoolEntry } from '../api/leagues';

const FORMAT_LABELS: Record<string, string> = {
  archon_standard: 'Archon Standard',
  triad: 'Triad',
  sealed_archon: 'Sealed Archon',
  sealed_alliance: 'Sealed Alliance',
  thief: 'Thief',
};

const TOKEN_SETS = new Set([855, 600]);
const PROPHECY_EXPANSION_ID = 886;

export default function MyTeamPage() {
  const { leagueId } = useParams<{ leagueId: string }>();
  const { user } = useAuth();
  const [league, setLeague] = useState<LeagueDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [editName, setEditName] = useState('');
  const [weekTab, setWeekTab] = useState(0);

  // Available sets for constraint display
  const [sets, setSets] = useState<KeyforgeSetInfo[]>([]);

  // Captain override confirmation for PAIRING status
  type PendingDeckAction =
    | { type: 'submit'; weekId: number; userId: number; slotNumber: number; playerName: string }
    | { type: 'remove'; weekId: number; slot: number; userId: number; playerName: string };
  const [pendingDeckAction, setPendingDeckAction] = useState<PendingDeckAction | null>(null);

  // Feature designation state: keyed by weekId
  const [featureSelectUserId, setFeatureSelectUserId] = useState<Record<number, number>>({});

  // Deck submission state
  const [teammateDeckUrls, setTeammateDeckUrls] = useState<Record<string, string>>({});

  // Sealed pool state: keyed by `${weekId}-${userId}`
  const [sealedPools, setSealedPools] = useState<Record<string, SealedPoolEntry[]>>({});
  // Sealed selection state: keyed by `${weekId}-${userId}-${slotNumber}`
  const [sealedSelections, setSealedSelections] = useState<Record<string, number>>({});

  // Thief: curation deck submission URLs, keyed by `${weekId}-${slot}`
  const [curationDeckUrls, setCurationDeckUrls] = useState<Record<string, string>>({});
  // Thief: steal selections, keyed by weekId -> curation_deck_id[]
  const [thiefStealSelections, setThiefStealSelections] = useState<Record<number, number[]>>({});

  // Sealed Alliance: pod selections keyed by `${weekId}-${userId}` -> 3 "deckId:house" strings
  const [alliancePods, setAlliancePods] = useState<Record<string, string[]>>({});
  const [allianceTokenIds, setAllianceTokenIds] = useState<Record<string, number>>({});
  const [allianceProphecyIds, setAllianceProphecyIds] = useState<Record<string, number>>({});

  const refresh = useCallback(() => {
    if (!leagueId) return;
    setSealedPools({});
    getLeague(parseInt(leagueId, 10))
      .then((l) => {
        setLeague(l);
        const myTeam = l.teams.find((t) => t.id === l.my_team_id);
        if (myTeam) setEditName(myTeam.name);
      })
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => { getSets().then(setSets).catch(() => {}); }, []);

  // Fetch sealed pools for sealed_archon and sealed_alliance weeks
  useEffect(() => {
    if (!league || !user) return;
    const myTeam = league.teams.find((t) => t.id === league.my_team_id);
    if (!myTeam) return;
    const isCaptain = league.is_captain;

    const sealedWeeks = (league.weeks || []).filter(
      (w) => ['sealed_archon', 'sealed_alliance'].includes(w.format_type) && w.sealed_pools_generated,
    );
    if (sealedWeeks.length === 0) return;

    sealedWeeks.forEach((week) => {
      const members = isCaptain
        ? myTeam.members
        : myTeam.members.filter((m) => m.user.id === user.id);

      members.forEach((m) => {
        const key = `${week.id}-${m.user.id}`;
        if (sealedPools[key]) return; // already fetched
        getSealedPool(league.id, week.id, m.user.id)
          .then((pool) => {
            setSealedPools((prev) => ({ ...prev, [key]: pool }));
          })
          .catch(() => {
            // Silently ignore - pool may not be accessible
          });
      });
    });
  }, [league, user]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error && !league) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;
  if (!league || !user) return null;

  if (!league.my_team_id) {
    return (
      <Container sx={{ mt: 3 }}>
        <Alert severity="error">You are not on a team in this league</Alert>
      </Container>
    );
  }

  const myTeam = league.teams.find((t) => t.id === league.my_team_id);
  if (!myTeam) return null;

  const isCaptain = league.is_captain;
  const weeks = league.weeks || [];

  const handleUpdateName = async () => {
    setError('');
    setSuccess('');
    try {
      await updateTeam(league.id, myTeam.id, editName);
      setSuccess('Team name updated');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleToggleFee = async (userId: number, currentPaid: boolean) => {
    setError('');
    try {
      await toggleFeePaid(league.id, myTeam.id, userId, !currentPaid);
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const doSubmitDeck = async (weekId: number, userId: number, slotNumber: number) => {
    const key = `${weekId}-${userId}-${slotNumber}`;
    const url = teammateDeckUrls[key];
    if (!url?.trim()) return;
    setError('');
    setSuccess('');
    try {
      const payload: { deck_url: string; slot_number: number; user_id?: number } = {
        deck_url: url.trim(),
        slot_number: slotNumber,
      };
      if (userId !== user.id) payload.user_id = userId;
      await submitDeckSelection(league.id, weekId, payload);
      setTeammateDeckUrls((prev) => ({ ...prev, [key]: '' }));
      setSuccess('Deck submitted');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const doSubmitSealed = async (weekId: number, userId: number, slotNumber: number) => {
    const key = `${weekId}-${userId}-${slotNumber}`;
    const deckId = sealedSelections[key];
    if (!deckId) return;
    setError('');
    setSuccess('');
    try {
      const payload: { deck_id: number; slot_number: number; user_id?: number } = {
        deck_id: deckId,
        slot_number: slotNumber,
      };
      if (userId !== user.id) payload.user_id = userId;
      await submitDeckSelection(league.id, weekId, payload);
      setSealedSelections((prev) => ({ ...prev, [key]: 0 }));
      setSuccess('Deck submitted');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const doRemoveDeck = async (weekId: number, slot: number, userId: number) => {
    setError('');
    try {
      await removeDeckSelection(league.id, weekId, slot, userId !== user.id ? userId : undefined);
      setSuccess('Deck removed');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  // Returns the player's display name from team member list
  const getPlayerName = (userId: number): string => {
    for (const team of league.teams) {
      const m = team.members.find((tm) => tm.user.id === userId);
      if (m) return m.user.name || `User ${userId}`;
    }
    return `User ${userId}`;
  };

  // Wrap deck actions: captain editing a teammate's deck in PAIRING status gets a confirmation
  const needsPairingWarning = (weekId: number, userId: number): boolean => {
    if (!isCaptain) return false;
    if (userId === user.id) return false;
    const week = (league.weeks || []).find((w) => w.id === weekId);
    return week?.status === 'pairing';
  };

  const handleSubmitDeck = (weekId: number, userId: number, slotNumber: number) => {
    if (needsPairingWarning(weekId, userId)) {
      setPendingDeckAction({ type: 'submit', weekId, userId, slotNumber, playerName: getPlayerName(userId) });
    } else {
      doSubmitDeck(weekId, userId, slotNumber);
    }
  };

  const handleSubmitSealed = (weekId: number, userId: number, slotNumber: number) => {
    if (needsPairingWarning(weekId, userId)) {
      setPendingDeckAction({ type: 'submit', weekId, userId, slotNumber, playerName: getPlayerName(userId) });
    } else {
      doSubmitSealed(weekId, userId, slotNumber);
    }
  };

  const handleRemoveDeck = (weekId: number, slot: number, userId: number) => {
    if (needsPairingWarning(weekId, userId)) {
      setPendingDeckAction({ type: 'remove', weekId, slot, userId, playerName: getPlayerName(userId) });
    } else {
      doRemoveDeck(weekId, slot, userId);
    }
  };

  const handleConfirmDeckAction = () => {
    if (!pendingDeckAction) return;
    const action = pendingDeckAction;
    setPendingDeckAction(null);
    if (action.type === 'submit') {
      doSubmitDeck(action.weekId, action.userId, action.slotNumber);
    } else {
      doRemoveDeck(action.weekId, action.slot, action.userId);
    }
  };

  const getMemberSelections = (week: LeagueWeek, userId: number): DeckSelectionInfo[] => {
    return week.deck_selections.filter((ds) => ds.user_id === userId);
  };

  const renderDeckInput = (week: LeagueWeek, userId: number, slotNumber: number) => {
    if (week.format_type === 'thief' && week.status === 'deck_selection') {
      // Build thief pool for this team
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
      const stolenDecks = (week.thief_curation_decks || []).filter((cd) => stolenByMyTeam.has(cd.id));
      const leftDecks = (week.thief_curation_decks || [])
        .filter((cd) => cd.team_id === myTeam.id && !stolenFromMyTeamIds.has(cd.id));
      const assignedDeckIds = new Set(
        week.deck_selections.filter((ds) => ds.user_id !== userId).map((ds) => ds.deck?.db_id).filter(Boolean)
      );
      const allPoolDecks = [...stolenDecks, ...leftDecks].filter(
        (cd) => cd.deck && !assignedDeckIds.has(cd.deck.db_id)
      );

      const selKey = `${week.id}-${userId}-${slotNumber}`;
      return (
        <Box sx={{ display: 'flex', gap: 1, ml: 4, mt: 0.5, alignItems: 'center' }}>
          <FormControl size="small" fullWidth>
            <InputLabel>Select deck from pool</InputLabel>
            <Select
              value={sealedSelections[selKey] || ''}
              onChange={(e) => setSealedSelections((prev) => ({ ...prev, [selKey]: e.target.value as number }))}
              label="Select deck from pool"
            >
              {allPoolDecks.map((cd) => (
                <MenuItem key={cd.id} value={cd.deck!.db_id!}>
                  {cd.deck!.name}{cd.deck!.sas_rating != null ? ` (SAS: ${cd.deck!.sas_rating})` : ''}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button
            size="small"
            variant="outlined"
            onClick={() => handleSubmitSealed(week.id, userId, slotNumber)}
            disabled={!sealedSelections[selKey]}
          >
            Submit
          </Button>
        </Box>
      );
    }

    if (week.format_type === 'sealed_archon' || week.format_type === 'sealed_alliance') {
      const poolKey = `${week.id}-${userId}`;
      const pool = sealedPools[poolKey];
      if (!pool) {
        return (
          <Typography variant="body2" color="text.secondary" sx={{ ml: 4 }}>
            Pools not yet generated
          </Typography>
        );
      }

      // Filter out already-selected decks
      const selections = getMemberSelections(week, userId);
      const selectedDeckIds = new Set(selections.map((s) => s.deck?.db_id).filter(Boolean));
      const availableDecks = pool.filter((p) => p.deck && !selectedDeckIds.has(p.deck.db_id));

      const selKey = `${week.id}-${userId}-${slotNumber}`;
      return (
        <Box sx={{ display: 'flex', gap: 1, ml: 4, mt: 0.5, alignItems: 'center' }}>
          <FormControl size="small" fullWidth>
            <InputLabel>Select deck from pool</InputLabel>
            <Select
              value={sealedSelections[selKey] || ''}
              onChange={(e) => setSealedSelections((prev) => ({
                ...prev,
                [selKey]: e.target.value as number,
              }))}
              label="Select deck from pool"
            >
              {availableDecks.map((p) => (
                <MenuItem key={p.deck!.db_id} value={p.deck!.db_id}>
                  {p.deck!.name} {p.deck!.sas_rating != null ? `(SAS: ${p.deck!.sas_rating})` : ''}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button
            size="small"
            variant="outlined"
            onClick={() => handleSubmitSealed(week.id, userId, slotNumber)}
            disabled={!sealedSelections[selKey]}
          >
            Submit
          </Button>
        </Box>
      );
    }

    // Normal URL input for non-sealed formats
    const urlKey = `${week.id}-${userId}-${slotNumber}`;
    return (
      <Box sx={{ display: 'flex', gap: 1, ml: 4, mt: 0.5 }}>
        <TextField
          label="Deck URL"
          value={teammateDeckUrls[urlKey] || ''}
          onChange={(e) => setTeammateDeckUrls((prev) => ({
            ...prev,
            [urlKey]: e.target.value,
          }))}
          size="small"
          fullWidth
          placeholder="https://decksofkeyforge.com/decks/..."
        />
        <Button
          size="small"
          variant="outlined"
          onClick={() => handleSubmitDeck(week.id, userId, slotNumber)}
        >
          Submit
        </Button>
      </Box>
    );
  };

  const handleSetFeature = async (weekId: number, userId: number) => {
    setError('');
    try {
      await setFeatureDesignation(league.id, weekId, userId);
      setFeatureSelectUserId((prev) => ({ ...prev, [weekId]: 0 }));
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleClearFeature = async (weekId: number) => {
    setError('');
    try {
      await clearFeatureDesignation(league.id, weekId);
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleSubmitCurationDeck = async (weekId: number, slot: number, key: string) => {
    const url = curationDeckUrls[key];
    if (!url?.trim()) return;
    setError('');
    setSuccess('');
    try {
      await submitCurationDeck(league.id, weekId, { deck_url: url.trim(), slot_number: slot });
      setCurationDeckUrls((prev) => ({ ...prev, [key]: '' }));
      setSuccess('Curation deck submitted');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleRemoveCurationDeck = async (weekId: number, slot: number) => {
    setError('');
    try {
      await removeCurationDeck(league.id, weekId, slot);
      setSuccess('Curation deck removed');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleSubmitSteals = async (weekId: number) => {
    const selected = thiefStealSelections[weekId] || [];
    setError('');
    setSuccess('');
    try {
      await submitSteals(league.id, weekId, selected);
      setSuccess('Steals submitted!');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleSubmitAlliance = async (weekId: number, userId: number) => {
    const key = `${weekId}-${userId}`;
    const pods = (alliancePods[key] || ['', '', ''])
      .filter(Boolean)
      .map((s) => {
        const colonIdx = s.indexOf(':');
        return { deck_id: parseInt(s.slice(0, colonIdx), 10), house: s.slice(colonIdx + 1) };
      });
    setError('');
    setSuccess('');
    try {
      const payload: Parameters<typeof submitAllianceSelection>[2] = { pods };
      if (allianceTokenIds[key]) payload.token_deck_id = allianceTokenIds[key];
      if (allianceProphecyIds[key]) payload.prophecy_deck_id = allianceProphecyIds[key];
      if (userId !== user!.id) payload.user_id = userId;
      await submitAllianceSelection(league.id, weekId, payload);
      setAlliancePods((prev) => ({ ...prev, [key]: ['', '', ''] }));
      setAllianceTokenIds((prev) => ({ ...prev, [key]: 0 }));
      setAllianceProphecyIds((prev) => ({ ...prev, [key]: 0 }));
      setSuccess('Alliance selection submitted!');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleClearAllianceTeam = async (weekId: number, userId: number) => {
    setError('');
    try {
      await clearAllianceSelection(league.id, weekId, userId !== user!.id ? userId : undefined);
      setSuccess('Alliance selection cleared');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const renderWeekContent = (week: LeagueWeek) => {
    const thiefEditableStatuses = new Set(['curation', 'thief', 'deck_selection', 'team_paired', 'pairing']);
    const isWeekEditable = week.format_type === 'thief'
      ? thiefEditableStatuses.has(week.status)
      : week.status === 'deck_selection' || week.status === 'team_paired' || week.status === 'pairing';
    const maxSlots = week.format_type === 'triad' ? 3 : 1;
    const showFeature = league.team_size % 2 === 0 &&
      (week.status === 'deck_selection' || week.status === 'team_paired');
    const currentFeature = showFeature
      ? week.feature_designations?.find((fd) => fd.team_id === myTeam.id)
      : null;

    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">{week.name || `Week ${week.week_number}`}</Typography>
            <Chip label={FORMAT_LABELS[week.format_type] || week.format_type} size="small" />
            <Chip label={week.status.replace('_', ' ')} size="small" color="info" />
            <WeekConstraints week={week} sets={sets} />
          </Box>

          {/* Feature player designation (even team_size leagues only) */}
          {showFeature && (
            <Box sx={{ mb: 2, p: 1.5, border: 1, borderColor: 'warning.main', borderRadius: 1 }}>
              <Typography variant="subtitle2" gutterBottom>Feature Player</Typography>
              {currentFeature ? (
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                  <Typography variant="body2">
                    {myTeam.members.find((m) => m.user.id === currentFeature.user_id)?.user.name || `User ${currentFeature.user_id}`}
                  </Typography>
                  <Chip label="Feature" size="small" color="warning" />
                  {isCaptain && (
                    <Button size="small" color="error" onClick={() => handleClearFeature(week.id)}>
                      Clear
                    </Button>
                  )}
                </Box>
              ) : (
                <Typography variant="body2" color="text.secondary">Not yet designated</Typography>
              )}
              {isCaptain && (
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mt: 1 }}>
                  <FormControl size="small" sx={{ minWidth: 180 }}>
                    <InputLabel>Set Feature Player</InputLabel>
                    <Select
                      value={featureSelectUserId[week.id] || ''}
                      label="Set Feature Player"
                      onChange={(e) => setFeatureSelectUserId((prev) => ({ ...prev, [week.id]: e.target.value as number }))}
                    >
                      {myTeam.members.map((m) => (
                        <MenuItem key={m.user.id} value={m.user.id}>{m.user.name}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <Button
                    size="small"
                    variant="outlined"
                    color="warning"
                    disabled={!featureSelectUserId[week.id]}
                    onClick={() => handleSetFeature(week.id, featureSelectUserId[week.id])}
                  >
                    Set
                  </Button>
                </Box>
              )}
            </Box>
          )}

          {/* Thief: Curation phase (captain submits decks) */}
          {week.format_type === 'thief' && (week.status === 'curation' || week.status === 'team_paired') && (
            <Box sx={{ mb: 2 }}>
              {isCaptain ? (
                <Box sx={{ p: 1.5, border: 1, borderColor: 'info.main', borderRadius: 1 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Curation Phase — Submit {league.team_size} deck{league.team_size !== 1 ? 's' : ''}
                  </Typography>
                  {Array.from({ length: league.team_size }, (_, i) => i + 1).map((slot) => {
                    const existingDeck = (week.thief_curation_decks || []).find(
                      (cd) => cd.team_id === myTeam.id && cd.slot_number === slot
                    );
                    const key = `${week.id}-${slot}`;
                    return (
                      <Box key={slot} sx={{ display: 'flex', gap: 1, mb: 1, alignItems: 'center' }}>
                        <Typography variant="body2" sx={{ minWidth: 55 }}>Slot {slot}:</Typography>
                        {existingDeck ? (
                          <>
                            {existingDeck.deck?.houses && <HouseIcons houses={existingDeck.deck.houses} />}
                            <Typography variant="body2">{existingDeck.deck?.name || 'Unknown'}</Typography>
                            {existingDeck.deck?.sas_rating != null && (
                              <Chip label={`SAS: ${existingDeck.deck.sas_rating}`} size="small" variant="outlined" />
                            )}
                            <Button size="small" color="error" onClick={() => handleRemoveCurationDeck(week.id, slot)}>
                              Remove
                            </Button>
                          </>
                        ) : (
                          <>
                            <TextField
                              label="Deck URL"
                              value={curationDeckUrls[key] || ''}
                              onChange={(e) => setCurationDeckUrls((prev) => ({ ...prev, [key]: e.target.value }))}
                              size="small"
                              fullWidth
                              placeholder="https://decksofkeyforge.com/decks/..."
                            />
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={() => handleSubmitCurationDeck(week.id, slot, key)}
                              disabled={!curationDeckUrls[key]?.trim()}
                            >
                              Submit
                            </Button>
                          </>
                        )}
                      </Box>
                    );
                  })}
                </Box>
              ) : (
                <Typography color="text.secondary">
                  Curation phase: captain is submitting decks.
                </Typography>
              )}
              {(week.thief_curation_decks || []).filter((cd) => cd.team_id === myTeam.id).length > 0 && (
                <Box sx={{ mt: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    Submitted: {(week.thief_curation_decks || []).filter((cd) => cd.team_id === myTeam.id).length} / {league.team_size}
                  </Typography>
                </Box>
              )}
            </Box>
          )}

          {/* Thief: Steal phase */}
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
            const isFloor = myTeam.id === week.thief_floor_team_id;
            const stealCount = isFloor ? Math.floor(league.team_size / 2) : Math.ceil(league.team_size / 2);
            const currentSteals = (week.thief_steals || []).filter((s) => s.stealing_team_id === myTeam.id);
            const selected = thiefStealSelections[week.id] || [];
            return (
              <Box sx={{ mb: 2, p: 1.5, border: 1, borderColor: 'warning.main', borderRadius: 1 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Thief Phase — Steal {stealCount} deck{stealCount !== 1 ? 's' : ''} from {opponentTeam.name}
                </Typography>
                {opponentDecks.map((cd) => (
                  <Box key={cd.id} sx={{ display: 'flex', gap: 1, mb: 0.5, alignItems: 'center' }}>
                    <Checkbox
                      size="small"
                      checked={selected.includes(cd.id)}
                      onChange={(e) => {
                        setThiefStealSelections((prev) => {
                          const cur = prev[week.id] || [];
                          return {
                            ...prev,
                            [week.id]: e.target.checked
                              ? [...cur, cd.id]
                              : cur.filter((id) => id !== cd.id),
                          };
                        });
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
                <Box sx={{ mt: 1, display: 'flex', gap: 1, alignItems: 'center' }}>
                  <Typography variant="body2">Selected: {selected.length} / {stealCount}</Typography>
                  <Button
                    size="small"
                    variant="contained"
                    onClick={() => handleSubmitSteals(week.id)}
                    disabled={selected.length !== stealCount}
                  >
                    Submit Steals
                  </Button>
                </Box>
                {currentSteals.length > 0 && (
                  <Typography variant="body2" color="success.main" sx={{ mt: 0.5 }}>
                    Current: {currentSteals.length} steal{currentSteals.length !== 1 ? 's' : ''} submitted
                  </Typography>
                )}
              </Box>
            );
          })()}

          {myTeam.members.map((m) => {
            const isMe = m.user.id === user.id;
            const canEditMember = isWeekEditable && (isMe || isCaptain);
            const selections = getMemberSelections(week, m.user.id);
            return (
              <Box key={m.id} sx={{ mb: 2, p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
                  <Avatar src={m.user.avatar_url || undefined} sx={{ width: 24, height: 24 }}>
                    {m.user.name?.[0]}
                  </Avatar>
                  <Typography variant="subtitle2">
                    {m.user.name}
                    {isMe ? ' (you)' : ''}
                  </Typography>
                  {m.is_captain && <Chip label="Captain" size="small" color="primary" />}
                </Box>

                {/* Sealed pool display (sealed_archon and sealed_alliance) */}
                {(week.format_type === 'sealed_archon' || week.format_type === 'sealed_alliance') && (() => {
                  const poolKey = `${week.id}-${m.user.id}`;
                  const pool = sealedPools[poolKey];
                  if (!pool || pool.length === 0) return null;
                  return (
                    <Box sx={{ ml: 4, mb: 1 }}>
                      <Typography variant="caption" color="text.secondary">Sealed Pool:</Typography>
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
                  );
                })()}

                {/* Sealed Alliance: pod selection UI */}
                {week.format_type === 'sealed_alliance' && canEditMember && (() => {
                  const poolKey = `${week.id}-${m.user.id}`;
                  const pool = sealedPools[poolKey] || [];
                  if (pool.length === 0) return null;
                  const podKey = `${week.id}-${m.user.id}`;
                  const memberPods = alliancePods[podKey] || ['', '', ''];
                  const needsToken = (week.allowed_sets || []).some((s) => TOKEN_SETS.has(s));
                  const needsProphecy = (week.allowed_sets || []).includes(PROPHECY_EXPANSION_ID);

                  const allPairs = pool.flatMap((entry) =>
                    (entry.deck?.houses || []).map((house) => ({
                      value: `${entry.deck!.db_id}:${house}`,
                      label: `${entry.deck!.name} — ${house}`,
                      house,
                    }))
                  );
                  const selectedHouses = memberPods.filter(Boolean).map((p) => p.split(':').slice(1).join(':'));
                  const getPodOptions = (podIndex: number) => {
                    const othersSelected = selectedHouses.filter((_, i) => i !== podIndex);
                    return allPairs.filter((p) => !othersSelected.includes(p.house));
                  };
                  const selectedPodDeckIds = memberPods.filter(Boolean).map((p) => parseInt(p.split(':')[0], 10)).filter(Boolean);
                  const podPoolEntries = pool.filter((e) => e.deck?.db_id && selectedPodDeckIds.includes(e.deck.db_id));

                  return (
                    <Box sx={{ ml: 4, mb: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
                      <Typography variant="caption" color="text.secondary">Alliance Pod Selection:</Typography>
                      {[0, 1, 2].map((podIndex) => (
                        <FormControl key={podIndex} size="small" fullWidth>
                          <InputLabel>Pod {podIndex + 1}</InputLabel>
                          <Select
                            value={memberPods[podIndex]}
                            label={`Pod ${podIndex + 1}`}
                            onChange={(e) => {
                              const updated = [...memberPods];
                              updated[podIndex] = e.target.value;
                              setAlliancePods((prev) => ({ ...prev, [podKey]: updated }));
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
                            value={allianceTokenIds[podKey] || ''}
                            label="Token Deck"
                            onChange={(e) => setAllianceTokenIds((prev) => ({ ...prev, [podKey]: e.target.value as number }))}
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
                            value={allianceProphecyIds[podKey] || ''}
                            label="Prophecy Deck"
                            onChange={(e) => setAllianceProphecyIds((prev) => ({ ...prev, [podKey]: e.target.value as number }))}
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
                        size="small"
                        variant="outlined"
                        onClick={() => handleSubmitAlliance(week.id, m.user.id)}
                        disabled={memberPods.filter(Boolean).length < 3}
                      >
                        Submit Alliance
                      </Button>
                      {isMe && (week.alliance_selections || []).filter((s) => s.slot_type === 'pod').length > 0 && (
                        <Button size="small" color="error" onClick={() => handleClearAllianceTeam(week.id, m.user.id)}>
                          Clear My Selection
                        </Button>
                      )}
                    </Box>
                  );
                })()}

                {/* Render all slots (not for sealed_alliance or thief curation/steal phases) */}
                {week.format_type !== 'sealed_alliance' &&
                  !(week.format_type === 'thief' && (week.status === 'curation' || week.status === 'team_paired' || week.status === 'thief')) &&
                  Array.from({ length: maxSlots }, (_, i) => i + 1).map((slotNum) => {
                  const sel = selections.find((s) => s.slot_number === slotNum);
                  if (sel) {
                    return (
                      <Box key={slotNum} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5, ml: 4 }}>
                        {maxSlots > 1 && <Chip label={`Slot ${slotNum}`} size="small" variant="outlined" />}
                        {sel.deck?.houses && <HouseIcons houses={sel.deck.houses} />}
                        <Typography variant="body2">{sel.deck?.name || 'Unknown'}</Typography>
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
                        {canEditMember && (
                          <Button size="small" color="error" onClick={() => handleRemoveDeck(week.id, slotNum, m.user.id)}>
                            Remove
                          </Button>
                        )}
                      </Box>
                    );
                  }
                  // Empty slot
                  if (canEditMember) {
                    return (
                      <Box key={slotNum}>
                        {maxSlots > 1 && (
                          <Typography variant="body2" color="text.secondary" sx={{ ml: 4, mt: 0.5 }}>
                            Slot {slotNum}:
                          </Typography>
                        )}
                        {renderDeckInput(week, m.user.id, slotNum)}
                      </Box>
                    );
                  }
                  return (
                    <Box key={slotNum} sx={{ ml: 4, mb: 0.5 }}>
                      {maxSlots > 1 && <Chip label={`Slot ${slotNum}`} size="small" variant="outlined" sx={{ mr: 1 }} />}
                      <Typography variant="body2" color="text.secondary" component="span">
                        No deck selected
                      </Typography>
                    </Box>
                  );
                })}

                {/* Combined SAS for multi-deck formats */}
                {maxSlots > 1 && selections.length > 1 && (
                  <Box sx={{ ml: 4, mt: 0.5 }}>
                    <CombinedSas selections={selections} />
                  </Box>
                )}
              </Box>
            );
          })}

          {/* Matchups for this week */}
          {week.matchups.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>Match Results</Typography>
              {week.matchups.map((wm) => {
                const isMyTeamMatchup = wm.team1.id === myTeam.id || wm.team2.id === myTeam.id;
                if (!isMyTeamMatchup) return null;
                return (
                  <Box key={wm.id}>
                    {wm.player_matchups.map((pm) => {
                      const p1Wins = pm.games.filter((g) => g.winner_id === pm.player1.id).length;
                      const p2Wins = pm.games.filter((g) => g.winner_id === pm.player2.id).length;
                      return (
                        <Box key={pm.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                          <Typography variant="body2">
                            {pm.player1.name} vs {pm.player2.name}
                          </Typography>
                          {pm.games.length > 0 && (
                            <Chip label={`${p1Wins}-${p2Wins}`} size="small" variant="outlined" />
                          )}
                          {!pm.player1_started || !pm.player2_started ? (
                            <Chip label="Not started" size="small" color="default" />
                          ) : pm.games.length === 0 ? (
                            <Chip label="In progress" size="small" color="info" />
                          ) : null}
                        </Box>
                      );
                    })}
                  </Box>
                );
              })}
            </Box>
          )}
        </CardContent>
      </Card>
    );
  };

  const activeStatuses = new Set(['curation', 'thief', 'deck_selection', 'team_paired', 'pairing', 'published']);
  const sortedWeeks = [...weeks].sort((a, b) => {
    const aActive = activeStatuses.has(a.status) ? 0 : 1;
    const bActive = activeStatuses.has(b.status) ? 0 : 1;
    if (aActive !== bActive) return aActive - bActive;
    return a.week_number - b.week_number;
  });

  return (
    <Container maxWidth="sm" sx={{ mt: 3 }}>
      <Typography variant="h4" gutterBottom>{league.name}</Typography>
      <Typography variant="h5" gutterBottom>My Team</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      <Tabs
        value={weekTab}
        onChange={(_, v) => setWeekTab(v)}
        sx={{ mb: 2 }}
        variant="scrollable"
        scrollButtons="auto"
      >
        <Tab label="Membership" />
        {sortedWeeks.map((w, i) => (
          <Tab
            key={w.id}
            value={i + 1}
            label={
              w.name ? (
                <Box sx={{ textAlign: 'center', lineHeight: 1.2 }}>
                  <Box>{w.name}</Box>
                  <Box sx={{ fontSize: '0.7rem', opacity: 0.7 }}>{`Week ${w.week_number}`}</Box>
                </Box>
              ) : `Week ${w.week_number}`
            }
          />
        ))}
      </Tabs>

      {weekTab === 0 && (
        <>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>Team Name</Typography>
              {isCaptain ? (
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <TextField
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    size="small"
                    fullWidth
                  />
                  <Button variant="contained" onClick={handleUpdateName}>Save</Button>
                </Box>
              ) : (
                <Typography variant="body1">{myTeam.name}</Typography>
              )}
            </CardContent>
          </Card>

          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>Members</Typography>
              <List>
                {myTeam.members.map((m) => (
                  <ListItem key={m.id}>
                    <ListItemAvatar>
                      <Avatar src={m.user.avatar_url || undefined} sx={{ width: 32, height: 32 }}>
                        {m.user.name?.[0]}
                      </Avatar>
                    </ListItemAvatar>
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                          {m.user.name}
                          {m.is_captain && <Chip label="Captain" size="small" color="primary" />}
                        </Box>
                      }
                    />
                    {league.fee_amount != null && (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body2" color="text.secondary">
                          {m.has_paid ? 'Paid' : 'Unpaid'}
                        </Typography>
                        {isCaptain && (
                          <Switch
                            checked={m.has_paid}
                            onChange={() => handleToggleFee(m.user.id, m.has_paid)}
                            size="small"
                          />
                        )}
                      </Box>
                    )}
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </>
      )}

      {weekTab > 0 && sortedWeeks[weekTab - 1] && renderWeekContent(sortedWeeks[weekTab - 1])}

      <Dialog open={pendingDeckAction !== null} onClose={() => setPendingDeckAction(null)}>
        <DialogTitle>Override Deck Selection?</DialogTitle>
        <DialogContent>
          <Typography>
            Player matchups are already generated. Changing{' '}
            <strong>{pendingDeckAction?.playerName ?? ''}</strong>'s deck selection at this stage
            overrides the normal rules. Continue?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingDeckAction(null)}>Cancel</Button>
          <Button onClick={handleConfirmDeckAction} variant="contained" color="warning">Override</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
