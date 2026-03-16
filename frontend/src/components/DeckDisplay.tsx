import {
  Box,
  Chip,
  CircularProgress,
  Collapse,
  IconButton,
  Link,
  Tooltip,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { useState } from 'react';
import type { DeckSummary, DeckCardEntry } from '../types';
import { getDeckCards } from '../api/decks';

interface Props {
  deck: DeckSummary;
}

const HOUSE_COLORS: Record<string, string> = {
  Brobnar: '#c0392b',
  Dis: '#8e44ad',
  Ekwidon: '#16a085',
  Geistoid: '#7f8c8d',
  Logos: '#2980b9',
  Mars: '#27ae60',
  Sanctum: '#f39c12',
  Shadows: '#2c3e50',
  'Star Alliance': '#1abc9c',
  Saurian: '#d35400',
  Unfathomable: '#2471a3',
  Untamed: '#229954',
  Other: '#555',
};

export default function DeckDisplay({ deck }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [cards, setCards] = useState<Record<string, DeckCardEntry[]> | null>(null);
  const [loading, setLoading] = useState(false);

  const handleExpand = async () => {
    if (!expanded && !cards) {
      setLoading(true);
      try {
        const data = await getDeckCards(deck.kf_id);
        setCards(data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    setExpanded((prev) => !prev);
  };

  const mvUrl = `https://www.keyforgegame.com/deck-details/${deck.kf_id}`;
  const dokUrl = `https://decksofkeyforge.com/decks/${deck.kf_id}`;

  return (
    <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1, mb: 1 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 0.5 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mr: 1 }}>
          {deck.name}
        </Typography>
        {deck.expansion_name && <Chip label={deck.expansion_name} size="small" />}
        {deck.houses &&
          deck.houses.map((h: string) => (
            <Chip
              key={h}
              label={h}
              size="small"
              sx={{ bgcolor: HOUSE_COLORS[h] || '#555', color: '#fff' }}
            />
          ))}
        {deck.sas_rating != null && (
          <Chip
            label={`SAS: ${deck.sas_rating}`}
            size="small"
            color="primary"
            variant="outlined"
          />
        )}
        {deck.aerc_score != null && (
          <Chip label={`AERC: ${deck.aerc_score}`} size="small" variant="outlined" />
        )}
        <Tooltip title="Master Vault">
          <Link
            href={mvUrl}
            target="_blank"
            rel="noopener"
            sx={{ display: 'flex', alignItems: 'center' }}
          >
            <OpenInNewIcon fontSize="small" />
          </Link>
        </Tooltip>
        <Tooltip title="Decks of KeyForge">
          <Link
            href={dokUrl}
            target="_blank"
            rel="noopener"
            sx={{ display: 'flex', alignItems: 'center', ml: 0.5 }}
          >
            <OpenInNewIcon fontSize="small" />
          </Link>
        </Tooltip>
        <IconButton size="small" onClick={handleExpand} sx={{ ml: 'auto' }}>
          {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
      </Box>
      <Collapse in={expanded}>
        {loading && <CircularProgress size={20} sx={{ mt: 1 }} />}
        {cards && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 0.5 }}>
            {Object.entries(cards).map(([house, cardList]) => (
              <Box key={house} sx={{ minWidth: 140, flex: '1 1 140px' }}>
                <Typography
                  variant="caption"
                  sx={{
                    fontWeight: 'bold',
                    color: HOUSE_COLORS[house] || 'text.primary',
                    display: 'block',
                    mb: 0.5,
                  }}
                >
                  {house}
                </Typography>
                {cardList.map((card) => (
                  <Box
                    key={card.card_title}
                    sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.25 }}
                  >
                    <Typography variant="body2">{card.card_title}</Typography>
                    {card.is_maverick && (
                      <Chip
                        label="M"
                        size="small"
                        color="warning"
                        sx={{ height: 16, fontSize: '0.6rem' }}
                      />
                    )}
                    {card.is_anomaly && (
                      <Chip
                        label="A"
                        size="small"
                        color="error"
                        sx={{ height: 16, fontSize: '0.6rem' }}
                      />
                    )}
                  </Box>
                ))}
              </Box>
            ))}
          </Box>
        )}
      </Collapse>
    </Box>
  );
}
