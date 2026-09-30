import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import type { PaletteMode } from '@mui/material';
import { buildTheme } from '../theme';

/** What the viewer asked for; 'system' follows the device. */
export type ColorModePreference = 'light' | 'dark' | 'system';

const STORAGE_KEY = 'colorMode';

interface ColorModeValue {
  preference: ColorModePreference;
  mode: PaletteMode;
  setPreference: (preference: ColorModePreference) => void;
}

const ColorModeContext = createContext<ColorModeValue>({
  preference: 'system',
  mode: 'light',
  setPreference: () => {},
});

export function useColorMode(): ColorModeValue {
  return useContext(ColorModeContext);
}

function readStored(): ColorModePreference {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === 'light' || raw === 'dark' || raw === 'system') return raw;
  } catch {
    // Private windows and blocked site data both land here; the default is fine.
  }
  return 'system';
}

function systemMode(): PaletteMode {
  if (typeof window === 'undefined' || !window.matchMedia) return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/**
 * Light or dark, remembered per browser.
 *
 * The default follows the device, so someone who has chosen dark everywhere
 * gets it here without asking, and a choice made here is kept for that browser.
 */
export function ColorModeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ColorModePreference>(readStored);
  const [system, setSystem] = useState<PaletteMode>(systemMode);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const query = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => setSystem(query.matches ? 'dark' : 'light');
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, []);

  const setPreference = useCallback((next: ColorModePreference) => {
    setPreferenceState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Not being able to remember it is not a reason to refuse the change.
    }
  }, []);

  const mode: PaletteMode = preference === 'system' ? system : preference;
  const theme = useMemo(() => buildTheme(mode), [mode]);
  const value = useMemo(
    () => ({ preference, mode, setPreference }),
    [preference, mode, setPreference],
  );

  return (
    <ColorModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
}
