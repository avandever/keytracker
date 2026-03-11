import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Container,
  Typography,
  CircularProgress,
  Alert,
  Paper,
  Box,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
} from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { getGame } from '../api/games';
import type { GameDetail, TurnTimingEntry, KeyForgeEvent } from '../types';
import { alpha } from '@mui/material/styles';
import GameLogEntry from '../components/GameLogEntry';

const HOUSE_COLORS: Record<string, string> = {
  Brobnar: '#e57373',
  Dis: '#ba68c8',
  Ekwidon: '#f48fb1',
  Geistoid: '#b0bec5',
  Logos: '#64b5f6',
  Mars: '#81c784',
  Sanctum: '#fff176',
  Saurian: '#ffb74d',
  Shadows: '#90a4ae',
  'Star Alliance': '#4dd0e1',
  Unfathomable: '#7986cb',
  Untamed: '#a5d6a7',
};

const KEY_DOT_COLORS: Record<string, string> = {
  Red: '#ef5350',
  Yellow: '#fdd835',
  Blue: '#42a5f5',
};

function getHouseColor(house: string): string {
  return HOUSE_COLORS[house] ?? '#bdbdbd';
}

function VerticalTimeline({
  entries,
  keyEvents,
}: {
  entries: TurnTimingEntry[];
  keyEvents: KeyForgeEvent[];
}) {
  const sorted = [...entries].sort((a, b) => a.turn - b.turn);

  // Map turn number → key events for that turn
  const keysByTurn = new Map<number, KeyForgeEvent[]>();
  for (const ke of keyEvents) {
    if (!keysByTurn.has(ke.turn)) keysByTurn.set(ke.turn, []);
    keysByTurn.get(ke.turn)!.push(ke);
  }

  return (
    <Box>
      {sorted.map((entry, i) => {
        const next = sorted[i + 1];
        const durationMs = next ? next.timestamp_ms - entry.timestamp_ms : null;
        const durationSec = durationMs !== null ? Math.round(durationMs / 1000) : null;
        const houseColor = getHouseColor(entry.house);
        const turnKeys = keysByTurn.get(entry.turn) ?? [];
        return (
          <Box
            key={i}
            sx={{
              borderLeft: `4px solid ${houseColor}`,
              pl: 1,
              py: 0.25,
              display: 'flex',
              gap: 0.5,
              alignItems: 'center',
              bgcolor: i % 2 !== 0 ? 'action.hover' : 'transparent',
            }}
          >
            <Typography
              variant="caption"
              sx={{ fontWeight: 'bold', minWidth: 26, color: 'text.secondary', flexShrink: 0 }}
            >
              T{entry.turn}
            </Typography>
            <Typography
              variant="caption"
              sx={{
                minWidth: 44,
                maxWidth: 44,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                flexShrink: 0,
              }}
            >
              {entry.player.slice(0, 7)}
            </Typography>
            <Typography
              variant="caption"
              sx={{
                flex: 1,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                fontSize: '0.65rem',
              }}
            >
              {entry.house}
            </Typography>
            {durationSec !== null && (
              <Typography
                variant="caption"
                sx={{ color: 'text.secondary', minWidth: 28, textAlign: 'right', fontSize: '0.65rem', flexShrink: 0 }}
              >
                {durationSec}s
              </Typography>
            )}
            {turnKeys.map((ke, ki) => (
              <Tooltip
                key={ki}
                title={`${ke.player} forged ${ke.key_color} key (${ke.amber_paid} Æ)`}
                arrow
              >
                <Box
                  sx={{
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    bgcolor: KEY_DOT_COLORS[ke.key_color] ?? '#bdbdbd',
                    flexShrink: 0,
                    cursor: 'default',
                  }}
                />
              </Tooltip>
            ))}
          </Box>
        );
      })}
    </Box>
  );
}

export default function GameDetailPage() {
  const { crucibleGameId } = useParams<{ crucibleGameId: string }>();
  const [game, setGame] = useState<GameDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!crucibleGameId) return;
    getGame(crucibleGameId)
      .then(setGame)
      .catch((e) => {
        if (e.response?.status === 404) setError('Game not found');
        else setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [crucibleGameId]);

  if (loading) return <Container sx={{ mt: 3 }}><CircularProgress /></Container>;
  if (error) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;
  if (!game) return null;

  const players = [game.winner, game.loser].sort((a, b) =>
    a === game.first_player ? -1 : b === game.first_player ? 1 : 0
  );

  // Compute timeline data
  const ext = game.extended_data;
  let merged: TurnTimingEntry[] = [];
  let allKeyEvents: KeyForgeEvent[] = [];
  let hasTimeline = false;

  if (ext && ext.turn_timing.length > 0) {
    const p1 = ext.turn_timing;
    const p2 = ext.player2_turn_timing;
    const base = p1.length >= p2.length ? p1 : p2;
    const other = p1.length >= p2.length ? p2 : p1;
    const byTurn = new Map<number, TurnTimingEntry>(base.map((e) => [e.turn, e]));
    other.forEach((e) => { if (!byTurn.has(e.turn)) byTurn.set(e.turn, e); });
    merged = Array.from(byTurn.values());
    hasTimeline = merged.length > 0;
  }

  if (ext) {
    const seenKe = new Set<string>();
    allKeyEvents = [...(ext.key_events ?? []), ...(ext.player2_key_events ?? [])].filter((e) => {
      const k = `${e.turn}|${e.player}|${e.key_color}`;
      if (seenKe.has(k)) return false;
      seenKe.add(k);
      return true;
    });
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>
        {players.join(' vs ')}
      </Typography>
      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <Chip label={`Winner: ${game.winner}`} sx={(theme) => ({ bgcolor: alpha(theme.palette.primary.main, 0.12), color: theme.palette.primary.dark })} />
        <Chip label={`Keys: ${game.winner_keys} - ${game.loser_keys}`} variant="outlined" />
        {game.date && <Chip label={new Date(game.date).toLocaleString()} variant="outlined" />}
      </Box>
      <Box sx={{ display: 'flex', gap: 4, mb: 3, flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="subtitle2">{game.winner}'s Deck</Typography>
          <Typography
            component={RouterLink}
            to={`/deck/${game.winner_deck_id}`}
            sx={{ color: 'primary.main', textDecoration: 'none' }}
          >
            {game.winner_deck_name}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {game.winner_sas_rating} SAS, {game.winner_aerc_score} AERC
          </Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2">{game.loser}'s Deck</Typography>
          <Typography
            component={RouterLink}
            to={`/deck/${game.loser_deck_id}`}
            sx={{ color: 'primary.main', textDecoration: 'none' }}
          >
            {game.loser_deck_name}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {game.loser_sas_rating} SAS, {game.loser_aerc_score} AERC
          </Typography>
        </Box>
      </Box>

      {game.house_turn_counts.length > 0 && (
        <>
          <Typography variant="h6" sx={{ mb: 1 }}>House Turn Counts</Typography>
          <TableContainer component={Paper} sx={{ mb: 3, maxWidth: 500 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Player</TableCell>
                  <TableCell>House</TableCell>
                  <TableCell align="right">Turns</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {game.house_turn_counts.map((htc, i) => (
                  <TableRow key={i}>
                    <TableCell>{htc.player}</TableCell>
                    <TableCell>{htc.house}</TableCell>
                    <TableCell align="right">{htc.turns}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      <Typography variant="h6" sx={{ mb: 1 }}>Game Log</Typography>
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
        <Paper variant="outlined" sx={{ flex: '1 1 auto', maxHeight: 600, overflow: 'auto', p: 1 }}>
          {game.logs.map((log, i) => (
            <GameLogEntry key={i} message={log.message} />
          ))}
        </Paper>
        {hasTimeline && (
          <Paper
            variant="outlined"
            sx={{ width: 200, maxHeight: 600, overflow: 'auto', p: 1, flexShrink: 0 }}
          >
            <Typography variant="subtitle2" gutterBottom>
              Timeline{' '}
              {ext!.both_perspectives && (
                <Chip size="small" label="Both" color="info" variant="outlined" />
              )}
            </Typography>
            <VerticalTimeline entries={merged} keyEvents={allKeyEvents} />
          </Paper>
        )}
      </Box>
    </Container>
  );
}
