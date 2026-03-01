/**
 * AlliancePodBuilder - UI for forging an open Alliance deck.
 *
 * Supports:
 * 1. Optional DoK Alliance URL import (auto-fills all 3 pods)
 * 2. Manual pod building: 3 slots, each with a deck URL field + house select
 * 3. Token selector (if any loaded pod deck is from ToC/WoE)
 * 4. Prophecy selector (if any loaded pod deck is from PV)
 */

import { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import type { AlliancePodSelectionInfo } from '../types';
import { importDeckByUrl, importDokAlliance, type DeckImportResult } from '../api/standalone';

const TOKEN_EXPANSION_IDS = new Set([855, 600]); // ToC, WoE
const PROPHECY_EXPANSION_ID = 886; // PV

export interface PodEntry {
  deck_id: number;
  house: string;
}

interface LoadedDeck {
  id: number;
  name: string;
  expansion: number;
  houses: string[];
  sas_rating: number | null;
}

interface AlliancePodBuilderProps {
  allowedSets?: number[] | null;
  onPodsChange: (
    pods: PodEntry[],
    tokenDeckId: number | null,
    prophecyDeckId: number | null,
  ) => void;
  existingPods?: AlliancePodSelectionInfo[];
  disabled?: boolean;
}

export default function AlliancePodBuilder({
  allowedSets,
  onPodsChange,
  existingPods = [],
  disabled = false,
}: AlliancePodBuilderProps) {
  const [dokUrl, setDokUrl] = useState('');
  const [dokLoading, setDokLoading] = useState(false);
  const [dokError, setDokError] = useState('');

  // Three pod slots: each has a URL field, a loaded deck, and a chosen house
  const [podUrls, setPodUrls] = useState<string[]>(['', '', '']);
  const [podDecks, setPodDecks] = useState<(LoadedDeck | null)[]>([null, null, null]);
  const [podHouses, setPodHouses] = useState<string[]>(['', '', '']);
  const [podLoading, setPodLoading] = useState<boolean[]>([false, false, false]);
  const [podErrors, setPodErrors] = useState<string[]>(['', '', '']);

  const [tokenDeckId, setTokenDeckId] = useState<number | ''>('');
  const [prophecyDeckId, setProphecyDeckId] = useState<number | ''>('');

  // Determine if token/prophecy selectors are needed based on loaded decks
  const loadedExpansions = new Set(podDecks.filter(Boolean).map((d) => d!.expansion));
  const needsToken = [...loadedExpansions].some((e) => TOKEN_EXPANSION_IDS.has(e));
  const needsProphecy = loadedExpansions.has(PROPHECY_EXPANSION_ID);

  // Houses already chosen in other pods (for disabling duplicates)
  const chosenHouses = podHouses.filter(Boolean);

  // Notify parent whenever pods/token/prophecy change
  const notify = (
    decks: (LoadedDeck | null)[],
    houses: string[],
    tok: number | '',
    proph: number | '',
  ) => {
    const pods: PodEntry[] = decks
      .map((d, i) => (d && houses[i] ? { deck_id: d.id, house: houses[i] } : null))
      .filter(Boolean) as PodEntry[];
    onPodsChange(
      pods,
      typeof tok === 'number' ? tok : null,
      typeof proph === 'number' ? proph : null,
    );
  };

  const handleDokImport = async () => {
    setDokError('');
    setDokLoading(true);
    try {
      const result = await importDokAlliance(dokUrl);
      if (result.pods.length !== 3) {
        setDokError(`Expected 3 pods, got ${result.pods.length}`);
        return;
      }

      // Use deck info already embedded in the pods response
      const newDecks: (LoadedDeck | null)[] = [null, null, null];
      const newHouses: string[] = ['', '', ''];
      const newUrls: string[] = ['', '', ''];
      for (let i = 0; i < 3; i++) {
        const pod = result.pods[i];
        newDecks[i] = {
          id: pod.deck_id,
          name: pod.deck_name,
          expansion: pod.expansion,
          houses: pod.houses,
          sas_rating: pod.sas_rating,
        };
        newHouses[i] = pod.house;
        newUrls[i] = String(pod.deck_id);
      }

      setPodUrls(newUrls);
      setPodDecks(newDecks);
      setPodHouses(newHouses);
      setPodErrors(['', '', '']);

      const newToken = result.token_deck_id ?? '';
      const newProphecy = result.prophecy_deck_id ?? '';
      setTokenDeckId(newToken);
      setProphecyDeckId(newProphecy);
      notify(newDecks, newHouses, newToken, newProphecy);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setDokError(err.response?.data?.error || 'Failed to import alliance deck');
    } finally {
      setDokLoading(false);
    }
  };

  const handleLoadDeck = async (podIndex: number) => {
    const url = podUrls[podIndex];
    if (!url.trim()) return;

    const newLoading = [...podLoading];
    newLoading[podIndex] = true;
    setPodLoading(newLoading);

    const newErrors = [...podErrors];
    newErrors[podIndex] = '';
    setPodErrors(newErrors);

    try {
      let result: DeckImportResult;
      // Use the numeric ID if the previous load set it
      result = await importDeckByUrl(url.trim());

      // Validate against allowedSets if specified
      if (allowedSets && allowedSets.length > 0 && !allowedSets.includes(result.expansion)) {
        newErrors[podIndex] = `Deck set (${result.expansion}) not allowed in this week/match`;
        setPodErrors([...newErrors]);
        newLoading[podIndex] = false;
        setPodLoading([...newLoading]);
        return;
      }

      const newDecks = [...podDecks];
      newDecks[podIndex] = result;

      // Reset house for this pod (new deck)
      const newHouses = [...podHouses];
      newHouses[podIndex] = '';

      setPodDecks(newDecks);
      setPodHouses(newHouses);
      notify(newDecks, newHouses, tokenDeckId, prophecyDeckId);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      newErrors[podIndex] = err.response?.data?.error || 'Failed to load deck';
      setPodErrors([...newErrors]);
    } finally {
      newLoading[podIndex] = false;
      setPodLoading([...newLoading]);
    }
  };

  const handleHouseChange = (podIndex: number, house: string) => {
    const newHouses = [...podHouses];
    newHouses[podIndex] = house;
    setPodHouses(newHouses);
    notify(podDecks, newHouses, tokenDeckId, prophecyDeckId);
  };

  const handleClear = () => {
    setPodUrls(['', '', '']);
    setPodDecks([null, null, null]);
    setPodHouses(['', '', '']);
    setPodErrors(['', '', '']);
    setTokenDeckId('');
    setProphecyDeckId('');
    setDokUrl('');
    setDokError('');
    onPodsChange([], null, null);
  };

  // Display existing (submitted) pods
  const existingPodSelections = existingPods.filter((s) => s.slot_type === 'pod');
  const existingToken = existingPods.find((s) => s.slot_type === 'token');
  const existingProphecy = existingPods.find((s) => s.slot_type === 'prophecy');

  if (existingPodSelections.length === 3) {
    return (
      <Box>
        <Typography variant="caption" color="text.secondary">Submitted Alliance:</Typography>
        {existingPodSelections
          .sort((a, b) => a.slot_number - b.slot_number)
          .map((s) => (
            <Box key={s.id} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
              <Chip label={`Pod ${s.slot_number}`} size="small" variant="outlined" />
              <Typography variant="body2">
                {s.deck_name || `Deck ${s.deck_id}`} — {s.house_name}
              </Typography>
              {s.deck?.mv_url && (
                <Typography
                  variant="body2"
                  component="a"
                  href={s.deck.mv_url}
                  target="_blank"
                  rel="noopener"
                >
                  MV
                </Typography>
              )}
              {s.deck?.dok_url && (
                <Typography
                  variant="body2"
                  component="a"
                  href={s.deck.dok_url}
                  target="_blank"
                  rel="noopener"
                >
                  DoK
                </Typography>
              )}
            </Box>
          ))}
        {existingToken && (
          <Typography variant="body2" color="text.secondary">
            Token: {existingToken.deck_name}
          </Typography>
        )}
        {existingProphecy && (
          <Typography variant="body2" color="text.secondary">
            Prophecy: {existingProphecy.deck_name}
          </Typography>
        )}
      </Box>
    );
  }

  const loadedPodDecksForSelector = podDecks.filter(Boolean) as LoadedDeck[];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {/* DoK Alliance Import */}
      <Box>
        <Typography variant="caption" color="text.secondary" gutterBottom>
          DoK Alliance Import (optional)
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start', mt: 0.5 }}>
          <TextField
            size="small"
            label="DoK Alliance URL"
            placeholder="https://decksofkeyforge.com/alliance-decks/..."
            value={dokUrl}
            onChange={(e) => setDokUrl(e.target.value)}
            disabled={disabled || dokLoading}
            sx={{ flex: 1 }}
          />
          <Button
            variant="outlined"
            size="small"
            onClick={handleDokImport}
            disabled={disabled || dokLoading || !dokUrl.trim()}
          >
            {dokLoading ? <CircularProgress size={16} /> : 'Import'}
          </Button>
        </Box>
        {dokError && (
          <Typography variant="caption" color="error">
            {dokError}
          </Typography>
        )}
      </Box>

      <Divider />

      {/* Manual Pod Building */}
      {[0, 1, 2].map((i) => (
        <Box key={i}>
          <Typography variant="caption" color="text.secondary">
            Pod {i + 1}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start', mt: 0.5 }}>
            <TextField
              size="small"
              label="Deck URL or UUID"
              value={podUrls[i]}
              onChange={(e) => {
                const updated = [...podUrls];
                updated[i] = e.target.value;
                setPodUrls(updated);
              }}
              disabled={disabled || podLoading[i]}
              sx={{ flex: 1 }}
            />
            <Button
              variant="outlined"
              size="small"
              onClick={() => handleLoadDeck(i)}
              disabled={disabled || podLoading[i] || !podUrls[i].trim()}
            >
              {podLoading[i] ? <CircularProgress size={16} /> : 'Load'}
            </Button>
          </Box>
          {podErrors[i] && (
            <Typography variant="caption" color="error">
              {podErrors[i]}
            </Typography>
          )}
          {podDecks[i] && (
            <Box sx={{ mt: 0.5, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
              <Typography variant="body2">{podDecks[i]!.name}</Typography>
              {podDecks[i]!.sas_rating != null && (
                <Chip label={`SAS ${podDecks[i]!.sas_rating}`} size="small" variant="outlined" />
              )}
              <FormControl size="small" sx={{ minWidth: 140 }}>
                <InputLabel>House</InputLabel>
                <Select
                  value={podHouses[i]}
                  label="House"
                  onChange={(e) => handleHouseChange(i, e.target.value)}
                  disabled={disabled}
                >
                  <MenuItem value="">
                    <em>Select house</em>
                  </MenuItem>
                  {podDecks[i]!.houses.map((h) => (
                    <MenuItem
                      key={h}
                      value={h}
                      disabled={
                        chosenHouses.includes(h) && podHouses[i] !== h
                      }
                    >
                      {h}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
          )}
        </Box>
      ))}

      {/* Token selector */}
      {needsToken && loadedPodDecksForSelector.length > 0 && (
        <FormControl size="small" fullWidth>
          <InputLabel>Token Deck</InputLabel>
          <Select
            value={tokenDeckId}
            label="Token Deck"
            onChange={(e) => {
              const val = e.target.value as number;
              setTokenDeckId(val);
              notify(podDecks, podHouses, val, prophecyDeckId);
            }}
            disabled={disabled}
          >
            <MenuItem value="">
              <em>Select token deck</em>
            </MenuItem>
            {loadedPodDecksForSelector.map((d) => (
              <MenuItem key={d.id} value={d.id}>
                {d.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )}

      {/* Prophecy selector */}
      {needsProphecy && loadedPodDecksForSelector.length > 0 && (
        <FormControl size="small" fullWidth>
          <InputLabel>Prophecy Deck</InputLabel>
          <Select
            value={prophecyDeckId}
            label="Prophecy Deck"
            onChange={(e) => {
              const val = e.target.value as number;
              setProphecyDeckId(val);
              notify(podDecks, podHouses, tokenDeckId, val);
            }}
            disabled={disabled}
          >
            <MenuItem value="">
              <em>Select prophecy deck</em>
            </MenuItem>
            {loadedPodDecksForSelector.map((d) => (
              <MenuItem key={d.id} value={d.id}>
                {d.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )}

      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button
          size="small"
          variant="outlined"
          color="error"
          onClick={handleClear}
          disabled={disabled}
        >
          Clear
        </Button>
      </Box>
    </Box>
  );
}
