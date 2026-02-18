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
} from '@mui/material';
import {
  getLeague,
  updateTeam,
  toggleFeePaid,
  submitDeckSelection,
  removeDeckSelection,
} from '../api/leagues';
import { useAuth } from '../contexts/AuthContext';
import type { LeagueDetail, LeagueWeek, DeckSelectionInfo } from '../types';

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

  // Captain deck submission for teammates
  const [teammateDeckUrls, setTeammateDeckUrls] = useState<Record<string, string>>({});

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

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error && !league) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;
  if (!league || !user) return null;

  if (!league.is_captain) {
    return (
      <Container sx={{ mt: 3 }}>
        <Alert severity="error">Captain access required</Alert>
      </Container>
    );
  }

  const myTeam = league.teams.find((t) => t.id === league.my_team_id);
  if (!myTeam) return null;

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

  const handleSubmitForTeammate = async (weekId: number, userId: number, slotNumber: number) => {
    const key = `${weekId}-${userId}-${slotNumber}`;
    const url = teammateDeckUrls[key];
    if (!url?.trim()) return;
    setError('');
    setSuccess('');
    try {
      await submitDeckSelection(league.id, weekId, {
        deck_url: url.trim(),
        slot_number: slotNumber,
        user_id: userId,
      });
      setTeammateDeckUrls((prev) => ({ ...prev, [key]: '' }));
      setSuccess('Deck submitted for teammate');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleRemoveForTeammate = async (weekId: number, slot: number, userId: number) => {
    setError('');
    try {
      await removeDeckSelection(league.id, weekId, slot, userId);
      setSuccess('Deck removed');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const getMemberSelections = (week: LeagueWeek, userId: number): DeckSelectionInfo[] => {
    return week.deck_selections.filter((ds) => ds.user_id === userId);
  };

  const renderWeekContent = (week: LeagueWeek) => {
    const canEdit = week.status === 'deck_selection' || week.status === 'pairing';
    const maxSlots = week.format_type === 'triad' ? 3 : 1;

    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">{week.name || `Week ${week.week_number}`}</Typography>
            <Chip label={FORMAT_LABELS[week.format_type] || week.format_type} size="small" />
            <Chip label={week.status.replace('_', ' ')} size="small" color="info" />
          </Box>

          {myTeam.members.map((m) => {
            const selections = getMemberSelections(week, m.user.id);
            return (
              <Box key={m.id} sx={{ mb: 2, p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
                  <Avatar src={m.user.avatar_url || undefined} sx={{ width: 24, height: 24 }}>
                    {m.user.name?.[0]}
                  </Avatar>
                  <Typography variant="subtitle2">{m.user.name}</Typography>
                  {m.is_captain && <Chip label="Captain" size="small" color="primary" />}
                </Box>

                {/* Show existing selections */}
                {selections.map((sel) => (
                  <Box key={sel.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5, ml: 4 }}>
                    {maxSlots > 1 && <Chip label={`Slot ${sel.slot_number}`} size="small" variant="outlined" />}
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
                    {canEdit && (
                      <Button size="small" color="error" onClick={() => handleRemoveForTeammate(week.id, sel.slot_number, m.user.id)}>
                        Remove
                      </Button>
                    )}
                  </Box>
                ))}

                {/* Submit for teammate */}
                {canEdit && selections.length < maxSlots && (
                  <Box sx={{ display: 'flex', gap: 1, ml: 4, mt: 0.5 }}>
                    <TextField
                      label="Deck URL"
                      value={teammateDeckUrls[`${week.id}-${m.user.id}-${selections.length + 1}`] || ''}
                      onChange={(e) => setTeammateDeckUrls((prev) => ({
                        ...prev,
                        [`${week.id}-${m.user.id}-${selections.length + 1}`]: e.target.value,
                      }))}
                      size="small"
                      fullWidth
                      placeholder="https://decksofkeyforge.com/decks/..."
                    />
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => handleSubmitForTeammate(week.id, m.user.id, selections.length + 1)}
                    >
                      Submit
                    </Button>
                  </Box>
                )}

                {selections.length === 0 && !canEdit && (
                  <Typography variant="body2" color="text.secondary" sx={{ ml: 4 }}>
                    No deck selected
                  </Typography>
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

  return (
    <Container maxWidth="sm" sx={{ mt: 3 }}>
      <Typography variant="h4" gutterBottom>{league.name}</Typography>
      <Typography variant="h5" gutterBottom>My Team</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>Team Name</Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <TextField
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              size="small"
              fullWidth
            />
            <Button variant="contained" onClick={handleUpdateName}>Save</Button>
          </Box>
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
                    <Switch
                      checked={m.has_paid}
                      onChange={() => handleToggleFee(m.user.id, m.has_paid)}
                      size="small"
                    />
                  </Box>
                )}
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>

      {/* Weekly tabs */}
      {weeks.length > 0 && (
        <>
          <Typography variant="h6" gutterBottom>Weeks</Typography>
          <Tabs
            value={weekTab}
            onChange={(_, v) => setWeekTab(v)}
            sx={{ mb: 2 }}
            variant="scrollable"
            scrollButtons="auto"
          >
            {weeks.map((w) => (
              <Tab key={w.id} label={w.name || `Week ${w.week_number}`} />
            ))}
          </Tabs>
          {weeks[weekTab] && renderWeekContent(weeks[weekTab])}
        </>
      )}
    </Container>
  );
}
