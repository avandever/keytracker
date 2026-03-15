import { Typography, Tooltip, Box } from '@mui/material';

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

const CATEGORIES: { patterns: RegExp[]; style: CategoryStyle }[] = [
  { patterns: SYSTEM_PATTERNS, style: { color: '#999', bg: 'transparent' } },
  { patterns: TURN_START_PATTERNS, style: { color: '#000', bg: '#e3f2fd' } },
  { patterns: CARD_PLAY_PATTERNS, style: { color: '#1b5e20', bg: '#e8f5e9' } },
  { patterns: UPKEEP_PATTERNS, style: { color: '#795548', bg: '#fff8e1' } },
  { patterns: FORGED_KEY_PATTERNS, style: { color: '#e65100', bg: '#fff3e0' } },
];

function categorize(message: string): CategoryStyle {
  for (const { patterns, style } of CATEGORIES) {
    for (const pattern of patterns) {
      if (pattern.test(message)) {
        return style;
      }
    }
  }
  return { color: '#333', bg: 'transparent' };
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
  const style = categorize(message);
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
