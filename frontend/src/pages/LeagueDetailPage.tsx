import { useEffect, useState, useCallback } from 'react';
import { useParams, Link as RouterLink } from 'react-router-dom';
import {
  Container,
  Typography,
  CircularProgress,
  Alert,
  Box,
  Chip,
  Button,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Divider,
  Tab,
  Tabs,
} from '@mui/material';
import { getLeague, signup, withdraw } from '../api/leagues';
import { useAuth } from '../contexts/AuthContext';
import type { LeagueDetail, LeagueWeek } from '../types';

const FORMAT_LABELS: Record<string, string> = {
  archon_standard: 'Archon Standard',
  triad: 'Triad',
  sealed_archon: 'Sealed Archon',
};

export default function LeagueDetailPage() {
  const { leagueId } = useParams<{ leagueId: string }>();
  const { user } = useAuth();
  const [league, setLeague] = useState<LeagueDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [activeTab, setActiveTab] = useState(0);

  const refresh = useCallback(() => {
    if (!leagueId) return;
    getLeague(parseInt(leagueId, 10))
      .then(setLeague)
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  useEffect(() => { refresh(); }, [refresh]);

  const handleSignup = async () => {
    if (!leagueId) return;
    setActionLoading(true);
    try {
      await signup(parseInt(leagueId, 10));
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleWithdraw = async () => {
    if (!leagueId) return;
    setActionLoading(true);
    try {
      await withdraw(parseInt(leagueId, 10));
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error && !league) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;
  if (!league) return null;

  const weeks = league.weeks || [];
  const tabs = ['Teams & Players', ...weeks.map((w) => w.name || `Week ${w.week_number}`)];

  const renderWeekTab = (week: LeagueWeek) => {
    return (
      <Box>
        <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
          <Chip label={FORMAT_LABELS[week.format_type] || week.format_type} />
          <Chip label={`Bo${week.best_of_n}`} variant="outlined" />
          <Chip
            label={week.status.replace('_', ' ')}
            color={week.status === 'completed' ? 'success' : week.status === 'published' ? 'info' : 'default'}
          />
          {week.max_sas && <Chip label={`Max SAS: ${week.max_sas}`} variant="outlined" />}
        </Box>

        {/* Matchups and results */}
        {week.matchups.length > 0 ? (
          week.matchups.map((wm) => (
            <Card key={wm.id} sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  {wm.team1.name} vs {wm.team2.name}
                </Typography>
                {wm.player_matchups.map((pm) => {
                  const p1Wins = pm.games.filter((g) => g.winner_id === pm.player1.id).length;
                  const p2Wins = pm.games.filter((g) => g.winner_id === pm.player2.id).length;
                  const winsNeeded = Math.ceil(week.best_of_n / 2);
                  const isComplete = p1Wins >= winsNeeded || p2Wins >= winsNeeded;
                  const winnerId = p1Wins >= winsNeeded ? pm.player1.id : p2Wins >= winsNeeded ? pm.player2.id : null;

                  return (
                    <Box key={pm.id} sx={{ mb: 1, p: 1, bgcolor: 'action.hover', borderRadius: 1 }}>
                      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                        <Typography
                          variant="body2"
                          fontWeight={winnerId === pm.player1.id ? 'bold' : 'normal'}
                        >
                          {pm.player1.name}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {pm.games.length > 0 ? `${p1Wins} - ${p2Wins}` : 'vs'}
                        </Typography>
                        <Typography
                          variant="body2"
                          fontWeight={winnerId === pm.player2.id ? 'bold' : 'normal'}
                        >
                          {pm.player2.name}
                        </Typography>
                        {isComplete && <Chip label="Complete" size="small" color="success" />}
                        {!isComplete && pm.player1_started && pm.player2_started && (
                          <Chip label="In progress" size="small" color="info" />
                        )}
                        {!pm.player1_started || !pm.player2_started ? (
                          <Chip label="Not started" size="small" color="default" />
                        ) : null}
                      </Box>

                      {/* Show individual games for completed matches */}
                      {isComplete && pm.games.length > 0 && (
                        <Box sx={{ ml: 2, mt: 0.5 }}>
                          {pm.games.map((g) => {
                            const gameWinner = g.winner_id === pm.player1.id ? pm.player1 : pm.player2;
                            return (
                              <Typography key={g.id} variant="caption" color="text.secondary" display="block">
                                Game {g.game_number}: {gameWinner.name} won ({g.player1_keys}-{g.player2_keys} keys)
                                {g.went_to_time ? ' [time]' : ''}
                                {g.loser_conceded ? ' [conceded]' : ''}
                              </Typography>
                            );
                          })}
                        </Box>
                      )}
                    </Box>
                  );
                })}
              </CardContent>
            </Card>
          ))
        ) : (
          <Typography color="text.secondary">
            {week.status === 'setup' || week.status === 'deck_selection'
              ? 'Matchups have not been generated yet.'
              : 'No matchups for this week.'}
          </Typography>
        )}
      </Box>
    );
  };

  const renderTeamsTab = () => (
    <>
      {league.teams.length === 0 && (
        <Typography color="text.secondary" sx={{ mb: 2 }}>No teams created yet.</Typography>
      )}
      {league.teams.map((team) => (
        <Card key={team.id} sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6">{team.name}</Typography>
            <List dense>
              {team.members.map((m) => (
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
                        {league.fee_amount != null && (
                          <Chip
                            label={m.has_paid ? 'Paid' : 'Unpaid'}
                            size="small"
                            color={m.has_paid ? 'success' : 'default'}
                            variant="outlined"
                          />
                        )}
                      </Box>
                    }
                  />
                </ListItem>
              ))}
              {team.members.length === 0 && (
                <ListItem>
                  <ListItemText secondary="No members yet" />
                </ListItem>
              )}
            </List>
          </CardContent>
        </Card>
      ))}

      {/* Signups - only visible to league admins and team captains */}
      {(league.is_admin || league.is_captain) && (
        <>
          <Divider sx={{ my: 3 }} />
          <Typography variant="h5" sx={{ mb: 2 }}>Signups ({league.signups.length})</Typography>
          <List dense>
            {league.signups.map((s) => (
              <ListItem key={s.id}>
                <ListItemAvatar>
                  <Avatar src={s.user.avatar_url || undefined} sx={{ width: 28, height: 28 }}>
                    {s.user.name?.[0]}
                  </Avatar>
                </ListItemAvatar>
                <ListItemText
                  primary={s.user.name}
                  secondary={`#${s.signup_order} - ${s.status}`}
                />
              </ListItem>
            ))}
          </List>
        </>
      )}
    </>
  );

  return (
    <Container maxWidth="md" sx={{ mt: 3 }}>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
        <Box>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Typography variant="h4">{league.name}</Typography>
            {league.is_test && <Chip label="Test" size="small" color="secondary" />}
          </Box>
          {league.description && (
            <Typography color="text.secondary" sx={{ mt: 1 }}>{league.description}</Typography>
          )}
        </Box>
        <Chip label={league.status} color={league.status === 'active' ? 'success' : league.status === 'drafting' ? 'warning' : 'info'} />
      </Box>

      <Box sx={{ display: 'flex', gap: 1, mb: 3, flexWrap: 'wrap' }}>
        <Chip label={`${league.num_teams} teams`} variant="outlined" />
        <Chip label={`${league.team_size} per team`} variant="outlined" />
        {league.fee_amount != null && <Chip label={`$${league.fee_amount} fee`} variant="outlined" />}
        <Chip label={`${league.signup_count} signups`} variant="outlined" />
      </Box>

      {/* Action buttons */}
      <Box sx={{ display: 'flex', gap: 1, mb: 3, flexWrap: 'wrap' }}>
        {user && league.status === 'setup' && !league.is_signed_up && (
          <Button variant="contained" onClick={handleSignup} disabled={actionLoading}>
            Sign Up
          </Button>
        )}
        {user && league.status === 'setup' && league.is_signed_up && (
          <Button variant="outlined" color="warning" onClick={handleWithdraw} disabled={actionLoading}>
            Withdraw
          </Button>
        )}
        {league.is_admin && (
          <Button variant="outlined" component={RouterLink} to={`/league/${league.id}/admin`}>
            Admin
          </Button>
        )}
        {(league.is_admin || league.is_captain) && (league.status === 'drafting' || league.status === 'active') && (
          <Button variant="outlined" component={RouterLink} to={`/league/${league.id}/draft`}>
            Draft Board
          </Button>
        )}
        {league.my_team_id && (
          <>
            <Button variant="outlined" component={RouterLink} to={`/league/${league.id}/my-info`}>
              My Info
            </Button>
            {league.is_captain && (
              <Button variant="outlined" component={RouterLink} to={`/league/${league.id}/my-team`}>
                My Team
              </Button>
            )}
          </>
        )}
      </Box>

      {/* Tabbed content */}
      {weeks.length > 0 ? (
        <>
          <Tabs
            value={activeTab}
            onChange={(_, v) => setActiveTab(v)}
            sx={{ mb: 2 }}
            variant="scrollable"
            scrollButtons="auto"
          >
            {tabs.map((label, i) => (
              <Tab key={i} label={label} />
            ))}
          </Tabs>

          {activeTab === 0 && renderTeamsTab()}
          {activeTab > 0 && weeks[activeTab - 1] && renderWeekTab(weeks[activeTab - 1])}
        </>
      ) : (
        <>
          <Typography variant="h5" sx={{ mb: 2 }}>Teams</Typography>
          {renderTeamsTab()}
        </>
      )}
    </Container>
  );
}
