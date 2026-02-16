import { useState } from 'react';
import {
  AppBar as MuiAppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Avatar,
  Menu,
  MenuItem,
  IconButton,
} from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function AppBar() {
  const { user, loading } = useAuth();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

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
        {!loading && (
          user ? (
            <>
              <IconButton onClick={(e) => setAnchorEl(e.currentTarget)} sx={{ p: 0 }}>
                <Avatar
                  src={user.avatar_url || undefined}
                  alt={user.name}
                  sx={{ width: 32, height: 32 }}
                />
              </IconButton>
              <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={() => setAnchorEl(null)}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
              >
                <MenuItem component={RouterLink} to="/account" onClick={() => setAnchorEl(null)}>
                  Profile
                </MenuItem>
                <MenuItem component="a" href="/auth/logout?next=/">
                  Sign Out
                </MenuItem>
              </Menu>
            </>
          ) : (
            <Button color="inherit" href="/auth/google/login?next=/">
              Sign in with Google
            </Button>
          )
        )}
      </Toolbar>
    </MuiAppBar>
  );
}
