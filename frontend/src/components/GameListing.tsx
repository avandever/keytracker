import { Card, CardContent, Typography, Box, Chip } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import type { GameSummary } from '../types';

const DOK_COMPARE_TEMPLATE = 'https://decksofkeyforge.com/compare-decks?decks={0}&decks={1}';

interface Props {
  game: GameSummary;
  highlightUser?: string;
  highlightDeckId?: string;
}

function formatDate(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString();
}

function PlayerName({ name, highlight }: { name: string; highlight?: string }) {
  if (name === highlight) {
    return <Typography component="span" fontWeight="bold">{name}</Typography>;
  }
  return (
    <Typography
      component={RouterLink}
      to={`/user/${name}`}
      sx={{ color: 'primary.main', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
    >
      {name}
    </Typography>
  );
}

function DeckName({ name, deckId, sas, aerc, highlight }: {
  name: string;
  deckId: string | null;
  sas: number | null;
  aerc: number | null;
  highlight?: string;
}) {
  const stats = `${sas ?? '?'} SAS, ${aerc ?? '?'} AERC`;
  if (deckId === highlight) {
    return <Typography component="span" variant="body2">{name} - {stats}</Typography>;
  }
  return (
    <Typography variant="body2">
      {deckId ? (
        <>
          <Typography
            component={RouterLink}
            to={`/deck/${deckId}`}
            sx={{ color: 'primary.main', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
          >
            {name}
          </Typography>
          {' - '}{stats}{' '}
          {deckId && (
            <>
              (<Typography component="a" href={`https://www.keyforgegame.com/deck-details/${deckId}`} target="_blank" rel="noopener" sx={{ fontSize: 'inherit' }}>MV</Typography>)
              {' '}
              (<Typography component="a" href={`https://decksofkeyforge.com/decks/${deckId}`} target="_blank" rel="noopener" sx={{ fontSize: 'inherit' }}>DoK</Typography>)
            </>
          )}
        </>
      ) : (
        <>{name} - {stats}</>
      )}
    </Typography>
  );
}

export default function GameListing({ game, highlightUser, highlightDeckId }: Props) {
  const isWinnerFirst = game.winner === game.first_player;
  const firstPlayer = isWinnerFirst ? game.winner : game.loser;
  const secondPlayer = isWinnerFirst ? game.loser : game.winner;
  const firstDeckName = isWinnerFirst ? game.winner_deck_name : game.loser_deck_name;
  const secondDeckName = isWinnerFirst ? game.loser_deck_name : game.winner_deck_name;
  const firstDeckId = isWinnerFirst ? game.winner_deck_id : game.loser_deck_id;
  const secondDeckId = isWinnerFirst ? game.loser_deck_id : game.winner_deck_id;
  const firstSas = isWinnerFirst ? game.winner_sas_rating : game.loser_sas_rating;
  const secondSas = isWinnerFirst ? game.loser_sas_rating : game.winner_sas_rating;
  const firstAerc = isWinnerFirst ? game.winner_aerc_score : game.loser_aerc_score;
  const secondAerc = isWinnerFirst ? game.loser_aerc_score : game.winner_aerc_score;

  const compareUrl = game.winner_deck_id && game.loser_deck_id
    ? DOK_COMPARE_TEMPLATE.replace('{0}', game.winner_deck_id).replace('{1}', game.loser_deck_id)
    : null;

  return (
    <Card variant="outlined" sx={{ mb: 1 }}>
      <CardContent sx={{ py: 1, '&:last-child': { pb: 1 } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
          <PlayerName name={firstPlayer} highlight={highlightUser} />
          <Typography component="span" variant="body2" color="text.secondary">vs.</Typography>
          <PlayerName name={secondPlayer} highlight={highlightUser} />
          <Chip
            label={`${game.winner} wins ${game.winner_keys}-${game.loser_keys}`}
            size="small"
            color="primary"
            variant="outlined"
          />
          <Typography
            component={RouterLink}
            to={`/game/${game.crucible_game_id}`}
            variant="body2"
            sx={{ color: 'primary.main', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
          >
            Details
          </Typography>
          {compareUrl && (
            <Typography
              component="a"
              href={compareUrl}
              target="_blank"
              rel="noopener"
              variant="body2"
              sx={{ color: 'primary.main', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
            >
              DoK Compare
            </Typography>
          )}
          <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
            {formatDate(game.date)}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <DeckName name={firstDeckName} deckId={firstDeckId} sas={firstSas} aerc={firstAerc} highlight={highlightDeckId} />
          <Typography variant="body2" color="text.secondary">vs.</Typography>
          <DeckName name={secondDeckName} deckId={secondDeckId} sas={secondSas} aerc={secondAerc} highlight={highlightDeckId} />
        </Box>
      </CardContent>
    </Card>
  );
}
