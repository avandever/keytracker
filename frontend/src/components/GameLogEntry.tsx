import { Typography, Tooltip, Box, useTheme } from '@mui/material';
import type { PaletteMode } from '@mui/material';

const SYSTEM_PATTERNS = [
  /^.* brings .* to The Crucible/,
  /^Compare Decks/,
  /^.* has connected to the game server/,
  /^(\w+) phase - (\w+)/,
];

const TURN_START_PATTERNS = [
  /^TURN [0-9]+ - .*/,
];

const UPKEEP_PATTERNS = [
  /^.* chooses to randomize the first player/,
  /^.* won the flip and is first player/,
  /^.* draws [0-9]+ card ?s to their maximum of [0-9]+/,
  /^.* is shuffling their deck/,
  /^.* draws [0-9]+ cards?/,
  /^.* does not forge a key.*/,
  /^.* readies their cards/,
  /^End of turn [0-9]+/,
  /^.* chooses (.*) as their active house this turn/,
  /^(\w+): [0-9]+ [aÆ]mber .*keys?.*(\w+): [0-9]+ [aÆ]mber.*keys?.*/,
  /^.*in their archives to their hand.*/,
  /^.* declares Check!/,
];

const CARD_PLAY_PATTERNS = [
  /^.* plays .*/,
];

const FORGED_KEY_PATTERNS = [
  /^.* forges the (.*) key.*/,
];

interface CategoryStyle {
  color: string;
  bg: string;
}

/**
 * Each log category gets a tint, in light and dark flavours.
 *
 * The light tints are the MUI 50-level pastels they always were; the dark ones
 * are the same hues at low lightness, with text light enough to read on them.
 */
interface CategoryColors {
  light: CategoryStyle;
  dark: CategoryStyle;
}

const CATEGORIES: { patterns: RegExp[]; colors: CategoryColors }[] = [
  {
    patterns: SYSTEM_PATTERNS,
    colors: {
      light: { color: '#999', bg: 'transparent' },
      dark: { color: '#8f8a83', bg: 'transparent' },
    },
  },
  {
    patterns: TURN_START_PATTERNS,
    colors: {
      light: { color: '#000', bg: '#e3f2fd' },
      dark: { color: '#cfe4f7', bg: '#17293a' },
    },
  },
  {
    patterns: CARD_PLAY_PATTERNS,
    colors: {
      light: { color: '#1b5e20', bg: '#e8f5e9' },
      dark: { color: '#b3e0b8', bg: '#16301a' },
    },
  },
  {
    patterns: UPKEEP_PATTERNS,
    colors: {
      light: { color: '#795548', bg: '#fff8e1' },
      dark: { color: '#dcc3ae', bg: '#2c2318' },
    },
  },
  {
    patterns: FORGED_KEY_PATTERNS,
    colors: {
      light: { color: '#e65100', bg: '#fff3e0' },
      dark: { color: '#f5b276', bg: '#35220f' },
    },
  },
];

const DEFAULT_COLORS: CategoryColors = {
  light: { color: '#333', bg: 'transparent' },
  dark: { color: '#ded7ce', bg: 'transparent' },
};

function categorize(message: string, mode: PaletteMode): CategoryStyle {
  for (const { patterns, colors } of CATEGORIES) {
    for (const pattern of patterns) {
      if (pattern.test(message)) {
        return colors[mode];
      }
    }
  }
  return DEFAULT_COLORS[mode];
}

// Split a message into alternating plain-text / card-name segments.
// Returns an array of { text, cardImage? } parts.
function splitByCardNames(
  message: string,
  sortedNames: string[],
  cardImages: Record<string, string>,
): { text: string; cardImage?: string }[] {
  if (sortedNames.length === 0) return [{ text: message }];

  const pattern = new RegExp(
    '(' + sortedNames.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')',
    'g',
  );

  const parts: { text: string; cardImage?: string }[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(message)) !== null) {
    if (match.index > last) parts.push({ text: message.slice(last, match.index) });
    parts.push({ text: match[1], cardImage: cardImages[match[1]] });
    last = match.index + match[1].length;
  }
  if (last < message.length) parts.push({ text: message.slice(last) });
  return parts;
}

interface Props {
  message: string;
  cardImages?: Record<string, string>;
  sortedCardNames?: string[];
}

export default function GameLogEntry({ message, cardImages, sortedCardNames }: Props) {
  const theme = useTheme();
  const style = categorize(message, theme.palette.mode);
  const parts =
    cardImages && sortedCardNames && sortedCardNames.length > 0
      ? splitByCardNames(message, sortedCardNames, cardImages)
      : null;

  return (
    <Typography
      variant="body2"
      component="div"
      sx={{
        color: style.color,
        backgroundColor: style.bg,
        px: 1,
        py: 0.25,
        fontFamily: 'monospace',
        fontSize: '0.8rem',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}
    >
      {parts
        ? parts.map((part, i) =>
            part.cardImage ? (
              <Tooltip
                key={i}
                arrow
                title={
                  <Box component="img" src={part.cardImage} alt={part.text}
                    sx={{ width: 200, height: 'auto', display: 'block', borderRadius: 1 }}
                  />
                }
              >
                <Box
                  component="span"
                  sx={{
                    borderBottom: '1px dotted currentColor',
                    cursor: 'help',
                    '&:hover': { opacity: 0.75 },
                  }}
                >
                  {part.text}
                </Box>
              </Tooltip>
            ) : (
              <span key={i}>{part.text}</span>
            )
          )
        : message}
    </Typography>
  );
}
