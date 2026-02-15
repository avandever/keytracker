import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    primary: {
      main: '#8B4513',
    },
    secondary: {
      main: '#C41E3A',
    },
    success: {
      main: '#2E5930',
    },
    background: {
      default: '#FAFAF5',
      paper: '#FFFFFF',
    },
  },
  typography: {
    fontFamily: 'Roboto, Arial, sans-serif',
  },
});

export default theme;
