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
import type { GameDetail, TurnTimingEntry, KeyForgeEvent, TurnSnapshot } from '../types';
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

function normalizeHouse(h: string): string {
  if (!h) return '';
  if (h.toLowerCase() === 'staralliance') return 'Star Alliance';
  return h.charAt(0).toUpperCase() + h.slice(1).toLowerCase();
}

function getHouseColor(house: string): string {
  return HOUSE_COLORS[normalizeHouse(house)] ?? '#bdbdbd';
}

// Detail panel shown below the timeline when a turn is selected.
function TurnDetailPanel({
  snap,
  prevSnap,
  players,
}: {
  snap: TurnSnapshot;
  prevSnap: TurnSnapshot | undefined;
  players: string[];
}) {
  const playerList = players.length > 0 ? players : Object.keys(snap.boards);

  // Card IDs present in previous snapshot — used to mark newly arrived cards.
  const prevHandIds = new Set(prevSnap?.local_hand.map((c) => c.id) ?? []);
  const prevBoardIds: Record<string, Set<string>> = {};
  for (const p of playerList) {
    prevBoardIds[p] = new Set(prevSnap?.boards[p]?.map((c) => c.id) ?? []);
  }

  return (
    <Box sx={{ p: 1.5 }}>
      {/* Amber + discard counts per player */}
      <Box sx={{ display: 'flex', gap: 3, mb: 1.5, flexWrap: 'wrap' }}>
        {playerList.map((p) => (
          <Box key={p}>
            <Typography variant="caption" sx={{ fontWeight: 'bold' }}>
              {p}
            </Typography>
            <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
              {snap.amber[p] ?? 0}Æ &nbsp;·&nbsp; {snap.discard_size[p] ?? 0} disc
              {snap.deck_size[p] ? ` · ${snap.deck_size[p]} deck` : ''}
              {snap.archive_size[p] ? ` · ${snap.archive_size[p]} arch` : ''}
            </Typography>
          </Box>
        ))}
      </Box>

      {/* Board state — both players */}
      {playerList.map((p) => {
        const board = snap.boards[p] ?? [];
        const newIds = prevBoardIds[p] ?? new Set();
        return (
          <Box key={p} sx={{ mb: 1 }}>
            <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary' }}>
              {p} board ({board.length})
            </Typography>
            {board.length > 0 ? (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.25 }}>
                {board.map((c, i) => {
                  const hc = getHouseColor(c.house);
                  const isNew = prevSnap !== undefined && !newIds.has(c.id);
                  const label = [
                    c.name,
                    c.power ? `${c.power}` : '',
                    c.exhausted ? 'exhausted' : '',
                    c.stunned ? 'stunned' : '',
                    c.taunt ? 'taunt' : '',
                    isNew ? 'played this turn' : '',
                  ]
                    .filter(Boolean)
                    .join(' · ');
                  return (
                    <Tooltip key={i} title={label} arrow>
                      <Box
                        sx={{
                          bgcolor: alpha(hc, isNew ? 0.4 : 0.15),
                          border: `${isNew ? 2 : 1}px solid ${hc}`,
                          borderRadius: 1,
                          px: 0.75,
                          py: 0.25,
                          fontSize: '0.65rem',
                          maxWidth: 110,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          opacity: c.exhausted ? 0.55 : 1,
                          cursor: 'default',
                          fontStyle: c.stunned ? 'italic' : 'normal',
                        }}
                      >
                        {c.name}
                        {c.power ? (
                          <Box component="span" sx={{ ml: 0.5, opacity: 0.7 }}>
                            {c.power}
                          </Box>
                        ) : null}
                      </Box>
                    </Tooltip>
                  );
                })}
              </Box>
            ) : (
              <Typography variant="caption" sx={{ color: 'text.disabled', ml: 1 }}>
                empty
              </Typography>
            )}
          </Box>
        );
      })}

      {/* Local player hand */}
      {snap.local_hand.length > 0 && (
        <Box sx={{ mt: 0.5 }}>
          <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary' }}>
            Hand ({snap.local_hand.length})
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.25 }}>
            {snap.local_hand.map((c, i) => {
              const hc = getHouseColor(c.house);
              const isNew = prevSnap !== undefined && !prevHandIds.has(c.id);
              return (
                <Tooltip
                  key={i}
                  title={`${c.name} · ${normalizeHouse(c.house)}${c.amber ? ` · ${c.amber}Æ` : ''}${isNew ? ' · drawn this turn' : ''}`}
                  arrow
                >
                  <Box
                    sx={{
                      bgcolor: alpha(hc, isNew ? 0.4 : 0.15),
                      border: `${isNew ? 2 : 1}px solid ${hc}`,
                      borderRadius: 1,
                      px: 0.75,
                      py: 0.25,
                      fontSize: '0.65rem',
                      maxWidth: 110,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      cursor: 'default',
                    }}
                  >
                    {c.name}
                    {c.amber ? (
                      <Box component="span" sx={{ ml: 0.5, opacity: 0.7 }}>
                        {c.amber}Æ
                      </Box>
                    ) : null}
                  </Box>
                </Tooltip>
              );
            })}
          </Box>
        </Box>
      )}
    </Box>
  );
}

function VerticalTimeline({
  entries,
  keyEvents,
  snapshots,
  players,
  selectedTurn,
  onSelectTurn,
}: {
  entries: TurnTimingEntry[];
  keyEvents: KeyForgeEvent[];
  snapshots: Map<number, TurnSnapshot>;
  players: string[];
  selectedTurn: number | null;
  onSelectTurn: (turn: number | null) => void;
}) {
  const sorted = [...entries].sort((a, b) => a.turn - b.turn);

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
        const snap = snapshots.get(entry.turn);
        const prevSnap = i > 0 ? snapshots.get(sorted[i - 1].turn) : undefined;
        const isSelected = selectedTurn === entry.turn;

        // Compact amber summary: "3/5" using player order
        const amberStr = snap
          ? players.map((p) => snap.amber[p] ?? 0).join('/')
          : null;

        return (
          <Box key={i}>
            <Box
              onClick={() => onSelectTurn(isSelected ? null : entry.turn)}
              sx={{
                borderLeft: `4px solid ${houseColor}`,
                pl: 1,
                py: 0.25,
                display: 'flex',
                gap: 0.5,
                alignItems: 'center',
                bgcolor: isSelected
                  ? alpha(houseColor, 0.18)
                  : i % 2 !== 0
                    ? 'action.hover'
                    : 'transparent',
                cursor: snap ? 'pointer' : 'default',
                '&:hover': snap ? { bgcolor: alpha(houseColor, 0.12) } : {},
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
                {normalizeHouse(entry.house)}
              </Typography>
              {amberStr !== null && (
                <Typography
                  variant="caption"
                  sx={{ color: '#f9a825', fontSize: '0.6rem', flexShrink: 0 }}
                >
                  {amberStr}Æ
                </Typography>
              )}
              {durationSec !== null && (
                <Typography
                  variant="caption"
                  sx={{
                    color: 'text.secondary',
                    minWidth: 28,
                    textAlign: 'right',
                    fontSize: '0.65rem',
                    flexShrink: 0,
                  }}
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

            {/* Inline detail panel for selected turn */}
            {isSelected && snap && (
              <Box
                sx={{
                  borderLeft: `4px solid ${houseColor}`,
                  bgcolor: alpha(houseColor, 0.07),
                }}
              >
                <TurnDetailPanel snap={snap} prevSnap={prevSnap} players={players} />
              </Box>
            )}
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
  const [selectedTurn, setSelectedTurn] = useState<number | null>(null);

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

  const ext = game.extended_data;
  let merged: TurnTimingEntry[] = [];
  let allKeyEvents: KeyForgeEvent[] = [];
  let hasTimeline = false;
  const snapshotsByTurn = new Map<number, TurnSnapshot>();

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

    // Merge turn snapshots: prefer the perspective with more hand data
    const s1 = ext.turn_snapshots ?? [];
    const s2 = ext.player2_turn_snapshots ?? [];
    const base = s1.length >= s2.length ? s1 : s2;
    const other = s1.length >= s2.length ? s2 : s1;
    for (const snap of base) snapshotsByTurn.set(snap.turn, snap);
    for (const snap of other) {
      if (!snapshotsByTurn.has(snap.turn)) snapshotsByTurn.set(snap.turn, snap);
    }
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
            sx={{ width: 260, maxHeight: 600, overflow: 'auto', p: 1, flexShrink: 0 }}
          >
            <Typography variant="subtitle2" gutterBottom>
              Timeline{' '}
              {ext!.both_perspectives && (
                <Chip size="small" label="Both" color="info" variant="outlined" />
              )}
              {snapshotsByTurn.size > 0 && (
                <Chip size="small" label="Snapshots" color="success" variant="outlined" sx={{ ml: 0.5 }} />
              )}
            </Typography>
            <VerticalTimeline
              entries={merged}
              keyEvents={allKeyEvents}
              snapshots={snapshotsByTurn}
              players={players}
              selectedTurn={selectedTurn}
              onSelectTurn={setSelectedTurn}
            />
          </Paper>
        )}
      </Box>
    </Container>
  );
}
