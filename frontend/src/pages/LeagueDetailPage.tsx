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
  Tab,
  Tabs,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import { getLeague, signup, withdraw, getSets, getAdminLog, getCompletedMatchDecks } from '../api/leagues';
import { useAuth } from '../contexts/AuthContext';
import WeekConstraints from '../components/WeekConstraints';
import type { AdminLogEntry, AlliancePodEntry, CompletedMatchDecks, KeyforgeSetInfo, LeagueDetail, LeagueWeek, TeamDetail } from '../types';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';

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
  const [signupDialogOpen, setSignupDialogOpen] = useState(false);
  const [sets, setSets] = useState<KeyforgeSetInfo[]>([]);
  const [adminLog, setAdminLog] = useState<AdminLogEntry[] | null>(null);
  const [adminLogLoading, setAdminLogLoading] = useState(false);
  const [completedDecks, setCompletedDecks] = useState<Record<number, CompletedMatchDecks>>({});

  const refresh = useCallback(() => {
    if (!leagueId) return;
    getLeague(parseInt(leagueId, 10))
      .then(setLeague)
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { getSets().then(setSets).catch(() => {}); }, []);

  const handleSignup = async () => {
    if (!leagueId) return;
    setSignupDialogOpen(false);
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
  const showSignups = league.is_admin || league.is_captain;
  const tabs = [
    'Standings',
    'Player Standings',
    'Teams',
    ...(showSignups ? [`Signups (${league.signups.length})`] : []),
    ...weeks.map((w) => w.name || `Week ${w.week_number}`),
    'Admin Log',
  ];
  // tab index offsets
  const playerStandingsIdx = 1;
  const teamsIdx = 2;
  const signupsIdx = showSignups ? 3 : null;
  const weekStartIdx = 3 + (showSignups ? 1 : 0);
  const adminLogIdx = tabs.length - 1;

  const computeMatchWins = (playerId: number, targetWeeks: LeagueWeek[]): number => {
    let wins = 0;
    for (const week of targetWeeks) {
      for (const wm of week.matchups) {
        for (const pm of wm.player_matchups) {
          if (pm.player1.id === playerId || pm.player2.id === playerId) {
            const isP1 = pm.player1.id === playerId;
            const myWins = pm.games.filter((g) => g.winner_id === (isP1 ? pm.player1.id : pm.player2.id)).length;
            const theirWins = pm.games.filter((g) => g.winner_id === (isP1 ? pm.player2.id : pm.player1.id)).length;
            if (myWins > theirWins) wins++;
          }
        }
      }
    }
    return wins;
  };

  const computePowerScore = (playerId: number, weekNumber: number): number => {
    const priorCompleted = weeks.filter(
      (w) => w.week_number < weekNumber && w.status === 'completed',
    );
    if (priorCompleted.length === 0) return 0;
    const myWins = computeMatchWins(playerId, priorCompleted);
    let opponentBonus = 0;
    for (const week of priorCompleted) {
      for (const wm of week.matchups) {
        for (const pm of wm.player_matchups) {
          if (pm.player1.id === playerId) {
            opponentBonus += computeMatchWins(pm.player2.id, priorCompleted) * 0.01;
          } else if (pm.player2.id === playerId) {
            opponentBonus += computeMatchWins(pm.player1.id, priorCompleted) * 0.01;
          }
        }
      }
    }
    return myWins + opponentBonus;
  };

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
          <WeekConstraints week={week} sets={sets} />
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
                          {league.is_admin && (
                            <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                              ({computePowerScore(pm.player1.id, week.week_number).toFixed(2)})
                            </Typography>
                          )}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {pm.games.length > 0 ? `${p1Wins} - ${p2Wins}` : 'vs'}
                        </Typography>
                        <Typography
                          variant="body2"
                          fontWeight={winnerId === pm.player2.id ? 'bold' : 'normal'}
                        >
                          {pm.player2.name}
                          {league.is_admin && (
                            <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                              ({computePowerScore(pm.player2.id, week.week_number).toFixed(2)})
                            </Typography>
                          )}
                        </Typography>
                        {pm.is_feature && <Chip label="Feature" size="small" color="warning" />}
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

                      {/* Show deck info for completed matchups */}
                      {isComplete && completedDecks[week.id]?.[String(pm.id)] && (() => {
                        const deckData = completedDecks[week.id][String(pm.id)];

                        const renderDeckChip = (d: { db_id: number; name: string; sas_rating: number | null; dok_url: string | null }, label: string) => (
                          <Chip
                            key={d.db_id}
                            label={`${label}: ${d.name}${d.sas_rating ? ` (${d.sas_rating})` : ''}`}
                            size="small"
                            variant="outlined"
                            component={d.dok_url ? 'a' : 'div'}
                            href={d.dok_url || undefined}
                            target="_blank"
                            clickable={!!d.dok_url}
                          />
                        );

                        const renderPodChips = (pods: AlliancePodEntry[], playerName: string) =>
                          pods.map((p) => {
                            const slotLabel =
                              p.slot_type === 'token' ? 'Token'
                              : p.slot_type === 'prophecy' ? 'Prophecy'
                              : p.house_name ?? `Pod ${p.slot_number}`;
                            return renderDeckChip(p.deck, `${playerName} (${slotLabel})`);
                          });

                        if (deckData.player1_pods || deckData.player2_pods) {
                          return (
                            <Box sx={{ ml: 2, mt: 0.5, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                              {renderPodChips(deckData.player1_pods ?? [], pm.player1.name)}
                              {renderPodChips(deckData.player2_pods ?? [], pm.player2.name)}
                            </Box>
                          );
                        }

                        return (
                          <Box sx={{ ml: 2, mt: 0.5, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                            {(deckData.player1_decks ?? []).map((d) => renderDeckChip(d, pm.player1.name))}
                            {(deckData.player2_decks ?? []).map((d) => renderDeckChip(d, pm.player2.name))}
                          </Box>
                        );
                      })()}
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

  interface StandingsRow {
    team: TeamDetail;
    week_points: Record<number, number>;
    total: number;
  }

  const computeStandings = (): StandingsRow[] => {
    const qualifyingWeeks = weeks.filter(
      (w) => w.status === 'published' || w.status === 'completed',
    );
    const rows: Record<number, StandingsRow> = {};
    for (const team of league.teams) {
      rows[team.id] = { team, week_points: {}, total: 0 };
    }
    const bonusPoints = league.week_bonus_points ?? 2;
    for (const week of qualifyingWeeks) {
      const winsNeeded = Math.ceil(week.best_of_n / 2);
      for (const wm of week.matchups) {
        const team1MemberIds = new Set(wm.team1.members.map((m) => m.user.id));
        const totalMatchups = wm.player_matchups.length;
        let team1Wins = 0;
        let team2Wins = 0;
        let featureWinnerId: number | null = null;
        for (const pm of wm.player_matchups) {
          const p1Wins = pm.games.filter((g) => g.winner_id === pm.player1.id).length;
          const p2Wins = pm.games.filter((g) => g.winner_id === pm.player2.id).length;
          let winnerOfPm: number | null = null;
          if (p1Wins >= winsNeeded) winnerOfPm = pm.player1.id;
          else if (p2Wins >= winsNeeded) winnerOfPm = pm.player2.id;
          if (winnerOfPm !== null) {
            if (team1MemberIds.has(pm.player1.id)) {
              if (winnerOfPm === pm.player1.id) team1Wins++;
              else team2Wins++;
            } else {
              if (winnerOfPm === pm.player1.id) team2Wins++;
              else team1Wins++;
            }
          }
          if (pm.is_feature && winnerOfPm !== null) {
            featureWinnerId = winnerOfPm;
          }
        }
        // Only award bonus when outcome is certain:
        // - team won strictly more than half the total matchups, OR
        // - team won exactly half AND also won the feature match (tiebreaker)
        let t1Bonus = 0;
        let t2Bonus = 0;
        const team1WonMajority = team1Wins > totalMatchups / 2;
        const team2WonMajority = team2Wins > totalMatchups / 2;
        const team1WonHalfPlusFeature =
          team1Wins === totalMatchups / 2 &&
          featureWinnerId !== null &&
          team1MemberIds.has(featureWinnerId);
        const team2WonHalfPlusFeature =
          team2Wins === totalMatchups / 2 &&
          featureWinnerId !== null &&
          !team1MemberIds.has(featureWinnerId);
        if (team1WonMajority || team1WonHalfPlusFeature) {
          t1Bonus = bonusPoints;
        } else if (team2WonMajority || team2WonHalfPlusFeature) {
          t2Bonus = bonusPoints;
        }
        if (rows[wm.team1.id]) {
          rows[wm.team1.id].week_points[week.week_number] =
            (rows[wm.team1.id].week_points[week.week_number] || 0) + team1Wins + t1Bonus;
          rows[wm.team1.id].total += team1Wins + t1Bonus;
        }
        if (rows[wm.team2.id]) {
          rows[wm.team2.id].week_points[week.week_number] =
            (rows[wm.team2.id].week_points[week.week_number] || 0) + team2Wins + t2Bonus;
          rows[wm.team2.id].total += team2Wins + t2Bonus;
        }
      }
    }
    return Object.values(rows).sort((a, b) => b.total - a.total);
  };

  const renderStandingsTab = () => {
    const qualifyingWeeks = weeks.filter(
      (w) => w.status === 'published' || w.status === 'completed',
    );
    if (qualifyingWeeks.length === 0) {
      return (
        <Typography color="text.secondary">No results yet — standings will appear once weeks are published.</Typography>
      );
    }
    const rows = computeStandings();
    return (
      <>
        <Box sx={{ mb: 1, display: 'flex', justifyContent: 'flex-end' }}>
          <Button size="small" variant="outlined" onClick={handleDownloadTeamStandings}>Download CSV</Button>
        </Box>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell><strong>Team</strong></TableCell>
            {qualifyingWeeks.map((w) => (
              <TableCell key={w.id} align="center">
                <strong>{w.name || `Wk ${w.week_number}`}</strong>
              </TableCell>
            ))}
            <TableCell align="center"><strong>Total</strong></TableCell>
            <TableCell align="center"><strong>Playoff Pts</strong></TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.team.id}>
              <TableCell>{row.team.name}</TableCell>
              {qualifyingWeeks.map((w) => (
                <TableCell key={w.id} align="center">
                  {row.week_points[w.week_number] ?? 0}
                </TableCell>
              ))}
              <TableCell align="center"><strong>{row.total}</strong></TableCell>
              <TableCell align="center" sx={{ color: 'text.secondary' }}>N/A</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      </>
    );
  };

  const renderPlayerStandingsTab = () => {
    const qualifyingWeeks = weeks.filter(
      (w) => w.status === 'published' || w.status === 'completed',
    );
    if (qualifyingWeeks.length === 0) {
      return (
        <Typography color="text.secondary">
          No results yet — player standings will appear once weeks are published.
        </Typography>
      );
    }

    const standingsMap = computeStandings().reduce<Record<number, StandingsRow>>((acc, row) => {
      acc[row.team.id] = row;
      return acc;
    }, {});

    const sortedTeams = [...league.teams].sort((a, b) => a.id - b.id);

    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Button size="small" variant="outlined" onClick={handleDownloadPlayerStandings}>Download CSV</Button>
        </Box>
        {sortedTeams.map((team) => {
          const teamStandings = standingsMap[team.id];

          const sortedMembers = [...team.members].sort((a, b) => {
            if (a.is_captain && !b.is_captain) return -1;
            if (!a.is_captain && b.is_captain) return 1;
            return computeMatchWins(b.user.id, qualifyingWeeks) - computeMatchWins(a.user.id, qualifyingWeeks);
          });

          const playerResults: Record<number, Record<number, string>> = {};
          const playerWins: Record<number, number> = {};
          const playerLosses: Record<number, number> = {};
          for (const member of sortedMembers) {
            playerResults[member.user.id] = {};
            playerWins[member.user.id] = 0;
            playerLosses[member.user.id] = 0;
          }

          const teamWeekWins: Record<number, number> = {};
          const teamWeekLosses: Record<number, number> = {};

          for (const week of qualifyingWeeks) {
            teamWeekWins[week.week_number] = 0;
            teamWeekLosses[week.week_number] = 0;

            const wm = week.matchups.find(
              (m) => m.team1.id === team.id || m.team2.id === team.id,
            );
            if (!wm) continue;

            const teamIsTeam1 = wm.team1.id === team.id;
            const winsNeeded = Math.ceil(week.best_of_n / 2);

            for (const pm of wm.player_matchups) {
              const ourPlayer = teamIsTeam1 ? pm.player1 : pm.player2;
              const p1Wins = pm.games.filter((g) => g.winner_id === pm.player1.id).length;
              const p2Wins = pm.games.filter((g) => g.winner_id === pm.player2.id).length;
              const ourWins = teamIsTeam1 ? p1Wins : p2Wins;
              const ourLosses = teamIsTeam1 ? p2Wins : p1Wins;

              let result = '-';
              if (ourWins >= winsNeeded) {
                result = 'W';
                teamWeekWins[week.week_number]++;
                playerWins[ourPlayer.id] = (playerWins[ourPlayer.id] || 0) + 1;
              } else if (ourLosses >= winsNeeded) {
                result = 'L';
                teamWeekLosses[week.week_number]++;
                playerLosses[ourPlayer.id] = (playerLosses[ourPlayer.id] || 0) + 1;
              }

              if (playerResults[ourPlayer.id] !== undefined) {
                playerResults[ourPlayer.id][week.week_number] = result;
              }
            }
          }

          const teamTotalWins = Object.values(teamWeekWins).reduce((a, b) => a + b, 0);
          const teamTotalLosses = Object.values(teamWeekLosses).reduce((a, b) => a + b, 0);

          return (
            <Card key={team.id} sx={{ width: '100%' }}>
              <CardContent>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell><strong>{team.name}</strong></TableCell>
                        <TableCell align="center"><strong>W-L</strong></TableCell>
                        {qualifyingWeeks.map((w) => (
                          <TableCell key={w.id} align="center">
                            <strong>{w.name || `Wk ${w.week_number}`}</strong>
                          </TableCell>
                        ))}
                        <TableCell />
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {sortedMembers.map((member) => (
                        <TableRow key={member.id}>
                          <TableCell>
                            <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                              <Typography variant="body2">{member.user.name}</Typography>
                              {member.is_captain && (
                                <Chip label="C" size="small" color="primary" sx={{ height: 18, fontSize: '0.65rem' }} />
                              )}
                            </Box>
                          </TableCell>
                          <TableCell align="center">
                            <Typography variant="body2">
                              {playerWins[member.user.id] ?? 0}-{playerLosses[member.user.id] ?? 0}
                            </Typography>
                          </TableCell>
                          {qualifyingWeeks.map((w) => {
                            const isFeature = w.feature_designations.find(
                              (fd) => fd.team_id === team.id && fd.user_id === member.user.id,
                            );
                            const result = playerResults[member.user.id]?.[w.week_number] ?? '-';
                            return (
                              <TableCell
                                key={w.id}
                                align="center"
                                sx={isFeature ? { bgcolor: 'cyan', color: 'black' } : {}}
                              >
                                {result}
                              </TableCell>
                            );
                          })}
                          <TableCell />
                        </TableRow>
                      ))}
                      <TableRow>
                        <TableCell><strong>Weekly Record</strong></TableCell>
                        <TableCell align="center">
                          <strong>{teamTotalWins}-{teamTotalLosses}</strong>
                        </TableCell>
                        {qualifyingWeeks.map((w) => (
                          <TableCell key={w.id} align="center">
                            {teamWeekWins[w.week_number] ?? 0}-{teamWeekLosses[w.week_number] ?? 0}
                          </TableCell>
                        ))}
                        <TableCell align="center"><strong>Total Points</strong></TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Points Earned</TableCell>
                        <TableCell />
                        {qualifyingWeeks.map((w) => (
                          <TableCell key={w.id} align="center">
                            {teamStandings?.week_points[w.week_number] ?? 0}
                          </TableCell>
                        ))}
                        <TableCell align="center">
                          <strong>{teamStandings?.total ?? 0}</strong>
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          );
        })}
      </Box>
    );
  };

  const downloadCsv = (filename: string, rows: string[][]) => {
    const escape = (v: string) => `"${v.replace(/"/g, '""')}"`;
    const csv = rows.map((r) => r.map(escape).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadTeamStandings = () => {
    const qualifyingWeeks = weeks.filter((w) => w.status === 'published' || w.status === 'completed');
    const rows = computeStandings();
    const header = ['Team', ...qualifyingWeeks.map((w) => w.name || `Week ${w.week_number}`), 'Total'];
    const dataRows = rows.map((row) => [
      row.team.name,
      ...qualifyingWeeks.map((w) => String(row.week_points[w.week_number] ?? 0)),
      String(row.total),
    ]);
    downloadCsv('team-standings.csv', [header, ...dataRows]);
  };

  const computePlayerWeekResult = (playerId: number, teamId: number, week: LeagueWeek): 'W' | 'L' | '-' => {
    const wm = week.matchups.find((m) => m.team1.id === teamId || m.team2.id === teamId);
    if (!wm) return '-';
    const teamIsTeam1 = wm.team1.id === teamId;
    const winsNeeded = Math.ceil(week.best_of_n / 2);
    for (const pm of wm.player_matchups) {
      const ourPlayer = teamIsTeam1 ? pm.player1 : pm.player2;
      if (ourPlayer.id !== playerId) continue;
      const p1Wins = pm.games.filter((g) => g.winner_id === pm.player1.id).length;
      const p2Wins = pm.games.filter((g) => g.winner_id === pm.player2.id).length;
      const ourWins = teamIsTeam1 ? p1Wins : p2Wins;
      const ourLosses = teamIsTeam1 ? p2Wins : p1Wins;
      if (ourWins >= winsNeeded) return 'W';
      if (ourLosses >= winsNeeded) return 'L';
    }
    return '-';
  };

  const handleDownloadPlayerStandings = () => {
    const qualifyingWeeks = weeks.filter((w) => w.status === 'published' || w.status === 'completed');
    const header = ['Team', 'Player', 'Captain', 'W-L', ...qualifyingWeeks.map((w) => w.name || `Week ${w.week_number}`)];
    const dataRows: string[][] = [];
    for (const team of league.teams) {
      for (const m of team.members) {
        const wins = qualifyingWeeks.filter((w) => computePlayerWeekResult(m.user.id, team.id, w) === 'W').length;
        const losses = qualifyingWeeks.filter((w) => computePlayerWeekResult(m.user.id, team.id, w) === 'L').length;
        dataRows.push([
          team.name,
          m.user.name,
          m.is_captain ? 'Yes' : 'No',
          `${wins}-${losses}`,
          ...qualifyingWeeks.map((w) => computePlayerWeekResult(m.user.id, team.id, w)),
        ]);
      }
    }
    downloadCsv('player-standings.csv', [header, ...dataRows]);
  };

  const renderAdminLogTab = () => {
    if (adminLogLoading) return <CircularProgress />;
    if (!adminLog) return <Typography color="text.secondary">Loading admin log...</Typography>;
    if (adminLog.length === 0) return <Typography color="text.secondary">No admin actions logged yet.</Typography>;
    return (
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell><strong>Time</strong></TableCell>
            <TableCell><strong>Actor</strong></TableCell>
            <TableCell><strong>Action</strong></TableCell>
            <TableCell><strong>Details</strong></TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {adminLog.map((entry) => (
            <TableRow key={entry.id}>
              <TableCell sx={{ whiteSpace: 'nowrap' }}>{entry.created_at ? new Date(entry.created_at).toLocaleString() : '-'}</TableCell>
              <TableCell>{entry.user.name}</TableCell>
              <TableCell>{entry.action_type.replace(/_/g, ' ')}</TableCell>
              <TableCell>{entry.details || ''}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  };

  const renderTeamsTab = () => (
    <>
      {league.teams.length === 0 && (
        <Typography color="text.secondary" sx={{ mb: 2 }}>No teams created yet.</Typography>
      )}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
        {league.teams.map((team) => (
          <Card key={team.id} sx={{ flex: '1 1 220px', maxWidth: 320 }}>
            <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
              <Typography variant="subtitle1" fontWeight="bold" gutterBottom>{team.name}</Typography>
              <List dense disablePadding>
                {team.members.map((m) => (
                  <ListItem key={m.id} disableGutters sx={{ py: 0.25 }}>
                    <ListItemAvatar sx={{ minWidth: 32 }}>
                      <Avatar src={m.user.avatar_url || undefined} sx={{ width: 24, height: 24 }}>
                        {m.user.name?.[0]}
                      </Avatar>
                    </ListItemAvatar>
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                          <Typography variant="body2">{m.user.name}</Typography>
                          {m.is_captain && <Chip label="C" size="small" color="primary" sx={{ height: 18, fontSize: '0.65rem' }} />}
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
                {team.members.length === 0 && (
                  <ListItem disableGutters>
                    <ListItemText secondary="No members yet" />
                  </ListItem>
                )}
              </List>
            </CardContent>
          </Card>
        ))}
      </Box>
    </>
  );

  const renderSignupsTab = () => (
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
        <Chip label={league.status} color={league.status === 'active' ? 'success' : league.status === 'drafting' || league.status === 'playoffs' ? 'warning' : 'info'} />
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
          <Button variant="contained" onClick={() => setSignupDialogOpen(true)} disabled={actionLoading}>
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
        {(league.is_admin || league.is_captain) && league.status === 'drafting' && (
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
            onChange={(_, v) => {
              setActiveTab(v);
              // Lazy-load admin log on first activation
              if (v === adminLogIdx && adminLog === null && !adminLogLoading) {
                setAdminLogLoading(true);
                getAdminLog(league.id).then(setAdminLog).catch(() => setAdminLog([])).finally(() => setAdminLogLoading(false));
              }
              // Lazy-load completed match decks for published/completed weeks
              if (v >= weekStartIdx) {
                const week = weeks[v - weekStartIdx];
                if (week && (week.status === 'published' || week.status === 'completed') && !completedDecks[week.id]) {
                  getCompletedMatchDecks(league.id, week.id).then((data) => {
                    setCompletedDecks((prev) => ({ ...prev, [week.id]: data }));
                  }).catch(() => {});
                }
              }
            }}
            sx={{ mb: 2 }}
            variant="scrollable"
            scrollButtons="auto"
          >
            {tabs.map((label, i) => (
              <Tab key={i} label={label} />
            ))}
          </Tabs>

          {activeTab === 0 && renderStandingsTab()}
          {activeTab === playerStandingsIdx && renderPlayerStandingsTab()}
          {activeTab === teamsIdx && renderTeamsTab()}
          {showSignups && activeTab === signupsIdx && renderSignupsTab()}
          {activeTab >= weekStartIdx && activeTab < adminLogIdx && weeks[activeTab - weekStartIdx] && renderWeekTab(weeks[activeTab - weekStartIdx])}
          {activeTab === adminLogIdx && renderAdminLogTab()}
        </>
      ) : (
        <>
          <Typography variant="h5" sx={{ mb: 2 }}>Teams</Typography>
          {renderTeamsTab()}
        </>
      )}


      <Dialog open={signupDialogOpen} onClose={() => setSignupDialogOpen(false)}>
        <DialogTitle>Confirm Signup</DialogTitle>
        <DialogContent>
          <Typography>
            This league is more fun if you collaborate with your team! Please commit to actively
            participating in your team's discord channel to participate in this league.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSignupDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleSignup} variant="contained">I Commit</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
