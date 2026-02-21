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
} from '@mui/material';
import {
  getLeague,
  updateTeam,
  toggleFeePaid,
  submitDeckSelection,
  removeDeckSelection,
  getSealedPool,
  getSets,
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
};

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

  // Deck submission state
  const [teammateDeckUrls, setTeammateDeckUrls] = useState<Record<string, string>>({});

  // Sealed pool state: keyed by `${weekId}-${userId}`
  const [sealedPools, setSealedPools] = useState<Record<string, SealedPoolEntry[]>>({});
  // Sealed selection state: keyed by `${weekId}-${userId}-${slotNumber}`
  const [sealedSelections, setSealedSelections] = useState<Record<string, number>>({});

  const refresh = useCallback(() => {
    if (!leagueId) return;
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

  // Fetch sealed pools for sealed_archon weeks
  useEffect(() => {
    if (!league || !user) return;
    const myTeam = league.teams.find((t) => t.id === league.my_team_id);
    if (!myTeam) return;
    const isCaptain = league.is_captain;

    const sealedWeeks = (league.weeks || []).filter(
      (w) => w.format_type === 'sealed_archon' && w.sealed_pools_generated,
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
    if (week.format_type === 'sealed_archon') {
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

  const renderWeekContent = (week: LeagueWeek) => {
    const isWeekEditable = week.status === 'deck_selection' || week.status === 'pairing';
    const maxSlots = week.format_type === 'triad' ? 3 : 1;

    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">{week.name || `Week ${week.week_number}`}</Typography>
            <Chip label={FORMAT_LABELS[week.format_type] || week.format_type} size="small" />
            <Chip label={week.status.replace('_', ' ')} size="small" color="info" />
            <WeekConstraints week={week} sets={sets} />
          </Box>

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

                {/* Sealed pool display */}
                {week.format_type === 'sealed_archon' && (() => {
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

                {/* Render all slots */}
                {Array.from({ length: maxSlots }, (_, i) => i + 1).map((slotNum) => {
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

  const topTabs = ['Membership', ...weeks.map((w) => w.name || `Week ${w.week_number}`)];

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
        {topTabs.map((label, i) => (
          <Tab key={i} label={label} />
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

      {weekTab > 0 && weeks[weekTab - 1] && renderWeekContent(weeks[weekTab - 1])}

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
