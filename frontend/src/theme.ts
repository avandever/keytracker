import { createTheme } from '@mui/material/styles';
import type { PaletteMode, Theme } from '@mui/material';

/**
 * The site's colours, in either mode.
 *
 * The brand is a dark brown on off-white, which has no contrast to spare on a
 * dark background, so the dark palette lifts each hue rather than reusing the
 * light one. The greys stay warm so the two modes look like the same site.
 */
export function buildTheme(mode: PaletteMode): Theme {
  const light = mode === 'light';
  return createTheme({
    palette: {
      mode,
      primary: {
        main: light ? '#8B4513' : '#D08B55',
      },
      secondary: {
        main: light ? '#C41E3A' : '#E8697F',
      },
      success: {
        main: light ? '#2E5930' : '#74B178',
      },
      warning: {
        main: light ? '#ED6C02' : '#F0A755',
      },
      error: {
        main: light ? '#D32F2F' : '#EF6C6C',
      },
      background: {
        default: light ? '#FAFAF5' : '#16130F',
        paper: light ? '#FFFFFF' : '#1F1B16',
      },
      divider: light ? 'rgba(0, 0, 0, 0.12)' : 'rgba(255, 255, 255, 0.14)',
      text: light
        ? undefined
        : {
            primary: '#F2EDE6',
            secondary: 'rgba(242, 237, 230, 0.68)',
          },
    },
    typography: {
      fontFamily: 'Roboto, Arial, sans-serif',
    },
    components: {
      // Native controls (date pickers, scrollbars) follow this rather than the
      // palette, so say it outright.
      MuiCssBaseline: {
        styleOverrides: {
          ':root': {
            colorScheme: mode,
          },
        },
      },
      // The bar is the brand colour in both modes; in dark that is a light
      // brown, which needs dark text on it rather than white.
      MuiAppBar: {
        styleOverrides: {
          colorPrimary: {
            backgroundColor: light ? '#8B4513' : '#2A221B',
            color: '#F2EDE6',
          },
        },
      },
    },
  });
}

/** The light theme, for anything that still imports a theme directly. */
const theme = buildTheme('light');
export default theme;
