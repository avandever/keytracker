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
import type { GameDetail, LogEntry, TurnTimingEntry, KeyForgeEvent, TurnSnapshot } from '../types';
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

const S3_HOUSE_BASE = 'https://mastervault-storage-prod.s3.amazonaws.com/media/houses';
const HOUSE_FILE_OVERRIDES: Record<string, string> = {
  Geistoid: 'KF_Geistoid',
  Ekwidon: 'Ekwidon200',
  'Star Alliance': 'Star_Alliance',
};
function houseIconUrl(house: string): string {
  const n = normalizeHouse(house);
  return `${S3_HOUSE_BASE}/${HOUSE_FILE_OVERRIDES[n] ?? n}.png`;
}

const PIP_URLS: Record<string, string> = {
  amber:   'https://www.keyforgegame.com/images/66f2f00f12feac4368785f6543cfd0b9.png',
  capture: 'https://www.keyforgegame.com/images/18062375103883be1757f1ec09e56c36.png',
  damage:  'https://www.keyforgegame.com/images/4ef12ff91e76087f3e207fbb0698bb63.png',
  draw:    'https://www.keyforgegame.com/images/2ccf3cd9faf3a670c1c19cb67b44fde2.png',
  discard: 'https://www.keyforgegame.com/images/833fdc87b48b2102c8dc43a93fd13347.png',
};
const BONUS_PIP_TYPES = new Set(['amber', 'capture', 'damage', 'draw', 'discard']);
const PIP_ORDER = ['amber', 'capture', 'damage', 'draw', 'discard'] as const;

function CardChip({
  name, house, amber = 0, enhancements, power, exhausted, stunned, taunt, isNew, isBoard,
}: {
  name: string; house: string; amber?: number; enhancements?: string[];
  power?: number; exhausted?: boolean; stunned?: boolean; taunt?: boolean;
  isNew?: boolean; isBoard?: boolean;
}) {
  const hc = getHouseColor(house);
  const normalH = normalizeHouse(house);

  const houseEnhPips = (enhancements ?? []).filter((e) => !BONUS_PIP_TYPES.has(e.toLowerCase()));
  const pipCounts: Record<string, number> = {};
  for (const e of enhancements ?? []) {
    const t = e.toLowerCase();
    if (BONUS_PIP_TYPES.has(t)) pipCounts[t] = (pipCounts[t] ?? 0) + 1;
  }
  const totalAmber = amber + (pipCounts.amber ?? 0);

  const tooltip = [
    name,
    normalH,
    houseEnhPips.map((h) => `+${normalizeHouse(h)}`).join(', '),
    totalAmber ? `${totalAmber}Æ` : '',
    pipCounts.capture ? `${pipCounts.capture} capture` : '',
    pipCounts.damage  ? `${pipCounts.damage} damage`  : '',
    pipCounts.draw    ? `${pipCounts.draw} draw`    : '',
    pipCounts.discard ? `${pipCounts.discard} discard` : '',
    power             ? `power ${power}` : '',
    exhausted         ? 'exhausted' : '',
    stunned           ? 'stunned'   : '',
    taunt             ? 'taunt'     : '',
    isNew             ? (isBoard ? 'played this turn' : 'drawn this turn') : '',
  ].filter(Boolean).join(' · ');

  return (
    <Tooltip title={tooltip} arrow>
      <Box
        sx={{
          display: 'inline-flex', alignItems: 'center', gap: '2px',
          bgcolor: alpha(hc, isNew ? 0.4 : 0.2),
          border: `${isNew ? 2 : 1}px solid ${hc}`,
          borderRadius: 1, px: 0.5, py: '2px',
          fontSize: '0.65rem', cursor: 'default',
          opacity: exhausted ? 0.55 : 1,
          fontStyle: stunned ? 'italic' : 'normal',
        }}
      >
        <img src={houseIconUrl(normalH)} alt={normalH} width={11} height={11} style={{ display: 'block', flexShrink: 0 }} />
        {houseEnhPips.map((h, i) => (
          <img key={i} src={houseIconUrl(h)} alt={normalizeHouse(h)} width={11} height={11} style={{ display: 'block', flexShrink: 0 }} />
        ))}
        {PIP_ORDER.flatMap((t) => {
          const count = t === 'amber' ? totalAmber : (pipCounts[t] ?? 0);
          return Array.from({ length: count }, (_, i) => (
            <img key={`${t}${i}`} src={PIP_URLS[t]} alt={t} width={11} height={11} style={{ display: 'block', flexShrink: 0 }} />
          ));
        })}
        <Box component="span" sx={{ ml: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 90 }}>
          {name}
          {power ? <Box component="span" sx={{ ml: 0.5, opacity: 0.7 }}>{power}</Box> : null}
        </Box>
      </Box>
    </Tooltip>
  );
}

function TurnDetailPanel({
  snap, prevSnap, players, localHandPlayer,
}: {
  snap: TurnSnapshot; prevSnap: TurnSnapshot | undefined;
  players: string[]; localHandPlayer: string;
}) {
  const playerList = players.length > 0 ? players : Object.keys(snap.boards);
  const prevHandIds = new Set(prevSnap?.local_hand.map((c) => c.id) ?? []);
  const prevBoardIds: Record<string, Set<string>> = {};
  for (const p of playerList) {
    prevBoardIds[p] = new Set(prevSnap?.boards[p]?.map((c) => c.id) ?? []);
  }

  return (
    <Box sx={{ px: 1.5, pt: 1, pb: 0.5 }}>
      {/* Amber + counts per player */}
      <Box sx={{ display: 'flex', gap: 3, mb: 1, flexWrap: 'wrap' }}>
        {playerList.map((p) => (
          <Box key={p}>
            <Typography variant="caption" sx={{ fontWeight: 'bold' }}>{p}</Typography>
            <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
              {snap.amber[p] ?? 0}Æ · {snap.discard_size[p] ?? 0} disc
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
          <Box key={p} sx={{ mb: 0.75 }}>
            <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary' }}>
              {p} board ({board.length})
            </Typography>
            {board.length > 0 ? (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.25 }}>
                {board.map((c, i) => (
                  <CardChip
                    key={i} name={c.name} house={c.house} amber={c.amber}
                    enhancements={c.enhancements} power={c.power}
                    exhausted={c.exhausted} stunned={c.stunned} taunt={c.taunt}
                    isNew={prevSnap !== undefined && !newIds.has(c.id)} isBoard
                  />
                ))}
              </Box>
            ) : (
              <Typography variant="caption" sx={{ color: 'text.disabled', ml: 1 }}>empty</Typography>
            )}
          </Box>
        );
      })}

      {/* Local player hand */}
      {snap.local_hand.length > 0 && (
        <Box sx={{ mb: 0.75 }}>
          <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary' }}>
            {localHandPlayer ? `${localHandPlayer} hand` : 'Hand'} ({snap.local_hand.length})
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.25 }}>
            {snap.local_hand.map((c, i) => (
              <CardChip
                key={i} name={c.name} house={c.house} amber={c.amber}
                enhancements={c.enhancements}
                isNew={prevSnap !== undefined && !prevHandIds.has(c.id)}
              />
            ))}
          </Box>
        </Box>
      )}
    </Box>
  );
}

// Slice game.logs into per-turn segments.
// Extension-reconstructed logs don't have "TURN N -" markers, but every turn
// starts with "X chooses Y as their active house this turn". We pair each such
// line (in order) with the corresponding TurnTimingEntry (sorted by turn number).
const HOUSE_CHOICE_RE = /^.* chooses .* as their active house this turn/;

function buildTurnLogSlices(
  logs: LogEntry[],
  sortedEntries: TurnTimingEntry[],
): Map<number, LogEntry[]> {
  // Also support explicit "TURN N - ..." markers (logs from full Crucible log files).
  const TURN_MARKER_RE = /^TURN (\d+) - /;

  // Try explicit markers first.
  const markerBoundaries: { turn: number; idx: number }[] = [];
  for (let i = 0; i < logs.length; i++) {
    const m = TURN_MARKER_RE.exec(logs[i].message);
    if (m) markerBoundaries.push({ turn: parseInt(m[1]), idx: i });
  }
  if (markerBoundaries.length > 0) {
    const slices = new Map<number, LogEntry[]>();
    for (let b = 0; b < markerBoundaries.length; b++) {
      const { turn, idx } = markerBoundaries[b];
      const end = b + 1 < markerBoundaries.length ? markerBoundaries[b + 1].idx : logs.length;
      slices.set(turn, logs.slice(idx, end));
    }
    return slices;
  }

  // Fall back: use "chooses house" lines paired with sorted TurnTimingEntries.
  const choiceIndices: number[] = [];
  for (let i = 0; i < logs.length; i++) {
    if (HOUSE_CHOICE_RE.test(logs[i].message)) choiceIndices.push(i);
  }
  const slices = new Map<number, LogEntry[]>();
  for (let t = 0; t < sortedEntries.length && t < choiceIndices.length; t++) {
    const turn = sortedEntries[t].turn;
    const start = choiceIndices[t];
    const end = t + 1 < choiceIndices.length ? choiceIndices[t + 1] : logs.length;
    slices.set(turn, logs.slice(start, end));
  }
  return slices;
}

function VerticalTimeline({
  entries, keyEvents, snapshots, players, localHandPlayer,
  logs, expandedTurns, onToggleTurn,
}: {
  entries: TurnTimingEntry[];
  keyEvents: KeyForgeEvent[];
  snapshots: Map<number, TurnSnapshot>;
  players: string[];
  localHandPlayer: string;
  logs: LogEntry[];
  expandedTurns: Set<number>;
  onToggleTurn: (turn: number) => void;
}) {
  const sorted = [...entries].sort((a, b) => a.turn - b.turn);

  const keysByTurn = new Map<number, KeyForgeEvent[]>();
  for (const ke of keyEvents) {
    if (!keysByTurn.has(ke.turn)) keysByTurn.set(ke.turn, []);
    keysByTurn.get(ke.turn)!.push(ke);
  }

  const turnLogSlices = buildTurnLogSlices(logs, sorted);

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
        const logSlice = turnLogSlices.get(entry.turn) ?? [];
        const isExpanded = expandedTurns.has(entry.turn);
        const isExpandable = !!(snap || logSlice.length > 0);

        const amberStr = snap
          ? players.map((p) => snap.amber[p] ?? 0).join('/')
          : null;

        return (
          <Box key={i}>
            {/* Turn row */}
            <Box
              onClick={() => isExpandable && onToggleTurn(entry.turn)}
              sx={{
                borderLeft: `4px solid ${houseColor}`,
                pl: 1, py: 0.25,
                display: 'flex', gap: 0.5, alignItems: 'center',
                bgcolor: isExpanded
                  ? alpha(houseColor, 0.18)
                  : i % 2 !== 0
                    ? 'action.hover'
                    : 'transparent',
                cursor: isExpandable ? 'pointer' : 'default',
                '&:hover': isExpandable ? { bgcolor: alpha(houseColor, 0.12) } : {},
              }}
            >
              <Typography variant="caption" sx={{ fontWeight: 'bold', minWidth: 26, color: 'text.secondary', flexShrink: 0 }}>
                T{entry.turn}
              </Typography>
              <Typography variant="caption" sx={{ minWidth: 44, maxWidth: 44, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flexShrink: 0 }}>
                {entry.player.slice(0, 7)}
              </Typography>
              <Typography variant="caption" sx={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.65rem' }}>
                {normalizeHouse(entry.house)}
              </Typography>
              {amberStr !== null && (
                <Typography variant="caption" sx={{ color: '#f9a825', fontSize: '0.6rem', flexShrink: 0 }}>
                  {amberStr}Æ
                </Typography>
              )}
              {durationSec !== null && (
                <Typography variant="caption" sx={{ color: 'text.secondary', minWidth: 28, textAlign: 'right', fontSize: '0.65rem', flexShrink: 0 }}>
                  {durationSec}s
                </Typography>
              )}
              {turnKeys.map((ke, ki) => (
                <Tooltip key={ki} title={`${ke.player} forged ${ke.key_color} key (${ke.amber_paid} Æ)`} arrow>
                  <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: KEY_DOT_COLORS[ke.key_color] ?? '#bdbdbd', flexShrink: 0, cursor: 'default' }} />
                </Tooltip>
              ))}
            </Box>

            {/* Expanded content: board/hand state then log */}
            {isExpanded && (
              <Box sx={{ borderLeft: `4px solid ${houseColor}`, bgcolor: alpha(houseColor, 0.05) }}>
                {snap && (
                  <TurnDetailPanel
                    snap={snap} prevSnap={prevSnap}
                    players={players} localHandPlayer={localHandPlayer}
                  />
                )}
                {logSlice.length > 0 && (
                  <Box sx={{ borderTop: snap ? `1px solid ${alpha(houseColor, 0.3)}` : undefined, pt: snap ? 0.5 : 0 }}>
                    {logSlice.map((log, li) => (
                      <GameLogEntry key={li} message={log.message} />
                    ))}
                  </Box>
                )}
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
  const [expandedTurns, setExpandedTurns] = useState<Set<number>>(new Set());

  const onToggleTurn = (turn: number) => {
    setExpandedTurns((prev) => {
      const next = new Set(prev);
      if (next.has(turn)) next.delete(turn);
      else next.add(turn);
      return next;
    });
  };

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
  let localHandPlayer = '';
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

    const s1 = ext.turn_snapshots ?? [];
    const s2 = ext.player2_turn_snapshots ?? [];
    const base = s1.length >= s2.length ? s1 : s2;
    const other = s1.length >= s2.length ? s2 : s1;
    localHandPlayer = s1.length >= s2.length
      ? ext.submitter_username
      : (ext.player2_username ?? '');
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
          <Typography component={RouterLink} to={`/deck/${game.winner_deck_id}`} sx={{ color: 'primary.main', textDecoration: 'none' }}>
            {game.winner_deck_name}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {game.winner_sas_rating} SAS, {game.winner_aerc_score} AERC
          </Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2">{game.loser}'s Deck</Typography>
          <Typography component={RouterLink} to={`/deck/${game.loser_deck_id}`} sx={{ color: 'primary.main', textDecoration: 'none' }}>
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

      {/* Unified timeline — full width, log segments embedded in expanded turns */}
      {hasTimeline && (
        <Paper variant="outlined" sx={{ mb: 3 }}>
          <Box sx={{ px: 1.5, py: 1, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="subtitle2">Game Log</Typography>
            {ext!.both_perspectives && (
              <Chip size="small" label="Both perspectives" color="info" variant="outlined" />
            )}
            {snapshotsByTurn.size > 0 && (
              <Chip size="small" label="Snapshots" color="success" variant="outlined" />
            )}
          </Box>
          <VerticalTimeline
            entries={merged}
            keyEvents={allKeyEvents}
            snapshots={snapshotsByTurn}
            players={players}
            localHandPlayer={localHandPlayer}
            logs={game.logs}
            expandedTurns={expandedTurns}
            onToggleTurn={onToggleTurn}
          />
          {/* Pre-game log lines (deck bring, flip, initial draw — before turn 1) */}
          {(() => {
            const firstIdx = game.logs.findIndex(
              (l) => /^TURN \d+ - /.test(l.message) || HOUSE_CHOICE_RE.test(l.message)
            );
            if (firstIdx <= 0) return null;
            const preGame = game.logs.slice(0, firstIdx);
            return (
              <Box sx={{ borderTop: '1px solid', borderColor: 'divider' }}>
                {preGame.map((log, i) => <GameLogEntry key={i} message={log.message} />)}
              </Box>
            );
          })()}
        </Paper>
      )}

      {/* Fallback: plain game log when no timeline data */}
      {!hasTimeline && game.logs.length > 0 && (
        <>
          <Typography variant="h6" sx={{ mb: 1 }}>Game Log</Typography>
          <Paper variant="outlined" sx={{ maxHeight: 600, overflow: 'auto', p: 1, mb: 3 }}>
            {game.logs.map((log, i) => (
              <GameLogEntry key={i} message={log.message} />
            ))}
          </Paper>
        </>
      )}
    </Container>
  );
}
