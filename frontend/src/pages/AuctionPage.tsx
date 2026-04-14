import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  List,
  ListItem,
  ListItemText,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { useParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  getAuction,
  joinAuction,
  startAuction,
  submitAuctionDeck,
  pickAuctionDeck,
  placeBid,
  passBid,
} from '../api/auction';
import type { AuctionDetail } from '../types';
import DeckDisplay from '../components/DeckDisplay';

export default function AuctionPage() {
  const { auctionId } = useParams<{ auctionId: string }>();
  const { user } = useAuth();
  const [auction, setAuction] = useState<AuctionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Join form
  const [passphrase, setPassphrase] = useState('');
  // Deck submission form
  const [deckUrl, setDeckUrl] = useState('');
  // Bid form
  const [bidChains, setBidChains] = useState('');

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchAuction = useCallback(async () => {
    if (!auctionId) return;
    try {
      const data = await getAuction(parseInt(auctionId));
      setAuction(data);
      setError(null);
    } catch {
      setError('Failed to load auction');
    } finally {
      setLoading(false);
    }
  }, [auctionId]);

  useEffect(() => {
    fetchAuction();
  }, [fetchAuction]);

  useEffect(() => {
    if (!auction) return;
    if (auction.status === 'deck_submission' || auction.status === 'auction') {
      pollRef.current = setInterval(fetchAuction, 5000);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [auction?.status, fetchAuction]);

  const wrap = async (fn: () => Promise<AuctionDetail>) => {
    setBusy(true);
    setActionError(null);
    try {
      const data = await fn();
      setAuction(data);
    } catch (e: unknown) {
      let msg = 'An error occurred';
      const axErr = e as { response?: { data?: { error?: string } }; message?: string };
      if (axErr.response?.data?.error) {
        msg = axErr.response.data.error;
      } else if (axErr.message) {
        msg = axErr.message;
      }
      setActionError(msg);
    } finally {
      setBusy(false);
    }
  };

  const id = parseInt(auctionId || '0');
  const myUserId = user?.id;
  const isParticipant = auction?.participants.some((p) => p.user_id === myUserId) ?? false;
  const isCreator = auction?.creator_id === myUserId;
  const myDeck = auction?.decks.find((d) => d.brought_by_user_id === myUserId);

  if (loading) return <Box sx={{ p: 3 }}><CircularProgress /></Box>;
  if (error || !auction) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error || 'Auction not found'}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 900, mx: 'auto', p: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <Typography variant="h5">Deck Auction #{auction.id}</Typography>
        <Chip
          label={auction.status.replace('_', ' ')}
          color={
            auction.status === 'completed'
              ? 'success'
              : auction.status === 'auction'
              ? 'secondary'
              : auction.status === 'deck_submission'
              ? 'primary'
              : 'default'
          }
        />
      </Box>

      {actionError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {actionError}
        </Alert>
      )}

      {auction.status === 'setup' && (
        <SetupPhase
          auction={auction}
          isParticipant={isParticipant}
          isCreator={isCreator}
          busy={busy}
          passphrase={passphrase}
          setPassphrase={setPassphrase}
          onJoin={() => wrap(() => joinAuction(id, passphrase))}
          onStart={() => wrap(() => startAuction(id))}
        />
      )}

      {auction.status === 'deck_submission' && isParticipant && (
        <DeckSubmissionPhase
          auction={auction}
          myDeck={myDeck}
          busy={busy}
          deckUrl={deckUrl}
          setDeckUrl={setDeckUrl}
          onSubmit={() => wrap(() => submitAuctionDeck(id, { deck_url: deckUrl }))}
        />
      )}
      {auction.status === 'deck_submission' && !isParticipant && (
        <Alert severity="info">
          This auction is in the deck submission phase. You cannot join now.
        </Alert>
      )}

      {auction.status === 'auction' && (
        <AuctionPhase
          auction={auction}
          myUserId={myUserId}
          busy={busy}
          bidChains={bidChains}
          setBidChains={setBidChains}
          onPick={(deckId: number) => wrap(() => pickAuctionDeck(id, deckId))}
          onBid={() => wrap(() => placeBid(id, parseInt(bidChains)))}
          onPass={() => wrap(() => passBid(id))}
        />
      )}

      {auction.status === 'completed' && <CompletedPhase auction={auction} />}
    </Box>
  );
}

function SetupPhase({
  auction,
  isParticipant,
  isCreator,
  busy,
  passphrase,
  setPassphrase,
  onJoin,
  onStart,
}: {
  auction: AuctionDetail;
  isParticipant: boolean;
  isCreator: boolean;
  busy: boolean;
  passphrase: string;
  setPassphrase: (v: string) => void;
  onJoin: () => void;
  onStart: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    if (auction.passphrase) {
      navigator.clipboard.writeText(auction.passphrase);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <Box>
      {!isParticipant && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="h6" gutterBottom>
            Join Auction
          </Typography>
          <TextField
            label="Passphrase"
            value={passphrase}
            onChange={(e) => setPassphrase(e.target.value)}
            size="small"
            sx={{ mr: 1 }}
          />
          <Button variant="contained" onClick={onJoin} disabled={busy || !passphrase}>
            Join
          </Button>
        </Paper>
      )}
      {isParticipant && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="h6" gutterBottom>
            Waiting for Players
          </Typography>
          <List dense>
            {auction.participants.map((p) => (
              <ListItem key={p.user_id}>
                <ListItemText primary={p.username} />
              </ListItem>
            ))}
          </List>
          {isCreator && auction.passphrase && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
              <Typography variant="body2" color="text.secondary">
                Passphrase:
              </Typography>
              <Typography variant="body1" sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}>
                {auction.passphrase}
              </Typography>
              <Tooltip title={copied ? 'Copied!' : 'Copy passphrase'}>
                <Button size="small" startIcon={<ContentCopyIcon />} onClick={handleCopy}>
                  {copied ? 'Copied' : 'Copy'}
                </Button>
              </Tooltip>
            </Box>
          )}
          {isCreator && (
            <Button
              variant="contained"
              sx={{ mt: 2 }}
              onClick={onStart}
              disabled={busy || auction.participants.length < 2}
            >
              Start Deck Submission ({auction.participants.length} / 2+ players)
            </Button>
          )}
          {!isCreator && (
            <Typography color="text.secondary" sx={{ mt: 1 }}>
              Waiting for the creator to start the auction.
            </Typography>
          )}
        </Paper>
      )}
    </Box>
  );
}

function DeckSubmissionPhase({
  auction,
  myDeck,
  busy,
  deckUrl,
  setDeckUrl,
  onSubmit,
}: {
  auction: AuctionDetail;
  myDeck: AuctionDetail['decks'][0] | undefined;
  busy: boolean;
  deckUrl: string;
  setDeckUrl: (v: string) => void;
  onSubmit: () => void;
}) {
  return (
    <Box>
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" gutterBottom>
          Deck Submission
        </Typography>
        <List dense>
          {auction.participants.map((p) => (
            <ListItem key={p.user_id}>
              {p.has_submitted ? (
                <CheckCircleIcon color="success" fontSize="small" sx={{ mr: 1 }} />
              ) : (
                <HourglassEmptyIcon color="disabled" fontSize="small" sx={{ mr: 1 }} />
              )}
              <ListItemText
                primary={p.username}
                secondary={p.has_submitted ? 'Submitted' : 'Waiting...'}
              />
            </ListItem>
          ))}
        </List>
      </Paper>
      {myDeck && myDeck.has_submitted && myDeck.deck ? (
        <Paper sx={{ p: 2 }}>
          <Typography variant="body1" gutterBottom>
            Your deck:
          </Typography>
          <DeckDisplay deck={myDeck.deck} />
          <Typography color="text.secondary">
            Waiting for other players to submit their decks...
          </Typography>
        </Paper>
      ) : (
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Submit Your Deck
          </Typography>
          <TextField
            label="Deck URL (Master Vault or DoK)"
            value={deckUrl}
            onChange={(e) => setDeckUrl(e.target.value)}
            fullWidth
            size="small"
            sx={{ mb: 1 }}
            placeholder="https://www.keyforgegame.com/deck-details/..."
          />
          <Button variant="contained" onClick={onSubmit} disabled={busy || !deckUrl}>
            Submit Deck
          </Button>
        </Paper>
      )}
    </Box>
  );
}

function AuctionPhase({
  auction,
  myUserId,
  busy,
  bidChains,
  setBidChains,
  onPick,
  onBid,
  onPass,
}: {
  auction: AuctionDetail;
  myUserId: number | undefined;
  busy: boolean;
  bidChains: string;
  setBidChains: (v: string) => void;
  onPick: (deckId: number) => void;
  onBid: () => void;
  onPass: () => void;
}) {
  const pickerName = auction.participants.find(
    (p) => p.user_id === auction.current_picker_id
  )?.username;
  const bidderName = auction.participants.find(
    (p) => p.user_id === auction.current_bidder_id
  )?.username;
  const activeDeck = auction.decks.find((d) => d.id === auction.active_deck_id);
  const unassignedDecks = auction.decks.filter(
    (d) => d.assigned_to_user_id === null && d.has_submitted
  );
  const isMyPickTurn =
    auction.current_picker_id === myUserId && !auction.active_deck_id;
  const isMyBidTurn = auction.current_bidder_id === myUserId;
  const currentHigh = auction.active_deck_bids
    .filter((b) => b.chains !== null)
    .reduce((max, b) => Math.max(max, b.chains ?? 0), 0);

  return (
    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
      <Box sx={{ flex: '1 1 500px', minWidth: 0 }}>
        {/* Active deck being bid on */}
        {activeDeck && activeDeck.deck && (
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="h6" gutterBottom>
              Currently Up for Bid
              {pickerName && (
                <Typography
                  component="span"
                  color="text.secondary"
                  sx={{ ml: 1, fontSize: '0.9rem' }}
                >
                  (picked by {pickerName})
                </Typography>
              )}
            </Typography>
            <DeckDisplay deck={activeDeck.deck} />
            <Divider sx={{ my: 1 }} />
            <Typography variant="subtitle2">Bids:</Typography>
            {auction.active_deck_bids.length === 0 ? (
              <Typography color="text.secondary" variant="body2">
                No bids yet.
              </Typography>
            ) : (
              <List dense>
                {auction.active_deck_bids.map((b) => (
                  <ListItem key={b.user_id}>
                    <ListItemText
                      primary={b.username}
                      secondary={b.chains === null ? 'Pass' : `${b.chains} chains`}
                    />
                  </ListItem>
                ))}
              </List>
            )}
            {currentHigh > 0 && (
              <Typography variant="body2" sx={{ mt: 0.5 }}>
                Current high bid: <strong>{currentHigh} chains</strong>
              </Typography>
            )}
            {isMyBidTurn && (
              <Box sx={{ mt: 2, display: 'flex', gap: 1, alignItems: 'center' }}>
                <TextField
                  label="Your bid (chains)"
                  type="number"
                  inputProps={{ min: currentHigh + 1, max: 24 }}
                  value={bidChains}
                  onChange={(e) => setBidChains(e.target.value)}
                  size="small"
                  sx={{ width: 160 }}
                />
                <Button variant="contained" onClick={onBid} disabled={busy || !bidChains}>
                  Bid
                </Button>
                <Button variant="outlined" onClick={onPass} disabled={busy}>
                  Pass
                </Button>
              </Box>
            )}
            {!isMyBidTurn && auction.current_bidder_id && (
              <Typography color="text.secondary" sx={{ mt: 1 }}>
                Waiting for {bidderName} to bid...
              </Typography>
            )}
          </Paper>
        )}

        {/* Picker choosing a deck */}
        {!auction.active_deck_id && auction.status === 'auction' && (
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="h6" gutterBottom>
              {isMyPickTurn
                ? 'Pick a deck to put up for bid:'
                : `Waiting for ${pickerName} to pick a deck...`}
            </Typography>
            {unassignedDecks.map((d) => (
              <Box key={d.id} sx={{ mb: 1 }}>
                {d.deck && <DeckDisplay deck={d.deck} />}
                {isMyPickTurn && (
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={() => onPick(d.id)}
                    disabled={busy}
                    sx={{ mt: 0.5 }}
                  >
                    Pick This Deck
                  </Button>
                )}
              </Box>
            ))}
          </Paper>
        )}
      </Box>

      {/* Player status sidebar */}
      <Box sx={{ flex: '0 0 220px', minWidth: 200 }}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Players
          </Typography>
          <List dense>
            {auction.player_order.map((uid) => {
              const participant = auction.participants.find((p) => p.user_id === uid);
              const assignedDeck = auction.decks.find(
                (d) => d.assigned_to_user_id === uid && d.has_submitted
              );
              return (
                <ListItem key={uid} sx={{ flexDirection: 'column', alignItems: 'flex-start' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', gap: 0.5 }}>
                    <Typography
                      variant="body2"
                      fontWeight={uid === myUserId ? 'bold' : 'normal'}
                    >
                      {participant?.username}
                      {uid === myUserId && ' (you)'}
                    </Typography>
                    {uid === auction.current_picker_id && !auction.active_deck_id && (
                      <Chip label="picking" size="small" color="secondary" />
                    )}
                    {uid === auction.current_bidder_id && (
                      <Chip label="bidding" size="small" color="primary" />
                    )}
                  </Box>
                  {assignedDeck && (
                    <Typography variant="caption" color="text.secondary">
                      Won: {assignedDeck.deck?.name} ({assignedDeck.chains_bid} chains)
                    </Typography>
                  )}
                </ListItem>
              );
            })}
          </List>
        </Paper>
      </Box>
    </Box>
  );
}

function CompletedPhase({ auction }: { auction: AuctionDetail }) {
  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Auction Results
      </Typography>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Player</TableCell>
            <TableCell>Deck Won</TableCell>
            <TableCell>Chains</TableCell>
            <TableCell>Deck Brought</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {auction.player_order.map((uid) => {
            const participant = auction.participants.find((p) => p.user_id === uid);
            const wonDeck = auction.decks.find((d) => d.assigned_to_user_id === uid);
            const broughtDeck = auction.decks.find((d) => d.brought_by_user_id === uid);
            return (
              <TableRow key={uid}>
                <TableCell>{participant?.username}</TableCell>
                <TableCell>
                  {wonDeck?.deck ? <DeckDisplay deck={wonDeck.deck} /> : '—'}
                </TableCell>
                <TableCell>{wonDeck?.chains_bid ?? '—'}</TableCell>
                <TableCell>
                  {broughtDeck?.deck ? <DeckDisplay deck={broughtDeck.deck} /> : '—'}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Box>
  );
}
