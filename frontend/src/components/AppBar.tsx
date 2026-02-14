import {
  AppBar as MuiAppBar,
  Toolbar,
  Typography,
  Button,
  Box,
} from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';

export default function AppBar() {
  return (
    <MuiAppBar position="static">
      <Toolbar>
        <Typography
          variant="h6"
          component={RouterLink}
          to="/"
          sx={{ flexGrow: 0, textDecoration: 'none', color: 'inherit', mr: 3 }}
        >
          Bear Tracks
        </Typography>
        <Box sx={{ flexGrow: 1, display: 'flex', gap: 1 }}>
          <Button color="inherit" component={RouterLink} to="/games">
            Games
          </Button>
          <Button color="inherit" component={RouterLink} to="/decks">
            Decks
          </Button>
          <Button color="inherit" component={RouterLink} to="/user">
            Players
          </Button>
          <Button color="inherit" component={RouterLink} to="/upload">
            Upload
          </Button>
          <Button color="inherit" component={RouterLink} to="/upload_simple">
            Simple Upload
          </Button>
          <Button color="inherit" component={RouterLink} to="/csv_to_pods">
            CSV Pods
          </Button>
        </Box>
      </Toolbar>
    </MuiAppBar>
  );
}
