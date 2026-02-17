import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  ListItemButton,
} from '@mui/material';
import { getDraft, makePick } from '../api/leagues';
import { useAuth } from '../contexts/AuthContext';
import { useTestUser } from '../contexts/TestUserContext';
import type { DraftState } from '../types';

export default function DraftBoardPage() {
  const { leagueId } = useParams<{ leagueId: string }>();
  const { user } = useAuth();
  const [draft, setDraft] = useState<DraftState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [pickLoading, setPickLoading] = useState(false);
  const intervalRef = useRef<number | null>(null);

  const refresh = useCallback(() => {
    if (!leagueId) return;
    getDraft(parseInt(leagueId, 10))
      .then(setDraft)
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  useEffect(() => {
    refresh();
    intervalRef.current = window.setInterval(refresh, 5000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [refresh]);

  const handlePick = async (userId: number) => {
    if (!leagueId) return;
    setPickLoading(true);
    setError('');
    try {
      const updated = await makePick(parseInt(leagueId, 10), userId);
      setDraft(updated);
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setPickLoading(false);
    }
  };

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error && !draft) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;
  if (!draft) return null;

  // Can current user pick? They must be captain of current team
  const { testUserId } = useTestUser();
  const effectiveUserId = testUserId ?? user?.id;
  const currentTeamCaptainId = draft.current_team?.members.find((m) => m.is_captain)?.user.id;
  const isMyPick = user && draft.current_team && currentTeamCaptainId === effectiveUserId;

  return (
    <Container maxWidth="lg" sx={{ mt: 3 }}>
      <Typography variant="h4" gutterBottom>Draft Board</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Status */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, alignItems: 'center' }}>
        <Chip
          label={draft.is_complete ? 'Complete' : 'In Progress'}
          color={draft.is_complete ? 'success' : 'warning'}
        />
        <Typography>
          {draft.picks_made}/{draft.total_picks} picks made
        </Typography>
      </Box>

      {/* Current pick info */}
      {!draft.is_complete && draft.current_team && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6">
              Round {draft.current_round}, Pick {draft.current_pick}
            </Typography>
            <Typography variant="subtitle1" color="primary">
              {draft.current_team.name}'s pick
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* Draft board table */}
      {draft.draft_board.length > 0 && (
        <TableContainer component={Paper} sx={{ mb: 3 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Round</TableCell>
                {draft.teams.map((t) => (
                  <TableCell key={t.id} align="center">{t.name}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {draft.draft_board.map((round) => (
                <TableRow key={round.round}>
                  <TableCell>{round.round}</TableCell>
                  {round.picks.map((slot) => (
                    <TableCell key={slot.team_id} align="center">
                      {slot.pick?.picked_user ? (
                        <Chip label={slot.pick.picked_user.name} size="small" />
                      ) : (
                        <Typography variant="body2" color="text.secondary">-</Typography>
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Available players (only show if it's user's pick or they're admin) */}
      {!draft.is_complete && draft.available_players.length > 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Available Players ({draft.available_players.length})
            </Typography>
            <List dense>
              {draft.available_players.map((p) => (
                <ListItem key={p.id} disablePadding>
                  <ListItemButton
                    onClick={() => handlePick(p.id)}
                    disabled={pickLoading || !isMyPick}
                  >
                    <ListItemAvatar>
                      <Avatar src={p.avatar_url || undefined} sx={{ width: 28, height: 28 }}>
                        {p.name?.[0]}
                      </Avatar>
                    </ListItemAvatar>
                    <ListItemText primary={p.name} />
                    {isMyPick && (
                      <Button size="small" variant="outlined" disabled={pickLoading}>
                        Pick
                      </Button>
                    )}
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      )}
    </Container>
  );
}
