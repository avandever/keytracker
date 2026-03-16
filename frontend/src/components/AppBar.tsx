import { useState } from 'react';
import {
  AppBar as MuiAppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Avatar,
  Badge,
  Menu,
  MenuItem,
  IconButton,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Divider,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const NAV_LINKS = [
  { label: 'Games', to: '/games' },
  { label: 'Decks', to: '/decks' },
  { label: 'Players', to: '/user' },
  { label: 'Leagues', to: '/leagues' },
  { label: 'Quick Match', to: '/matches' },
  { label: 'Auction', to: '/auctions' },
  { label: 'Upload', to: '/upload' },
  { label: 'CSV Pods', to: '/csv_to_pods' },
];

export default function AppBar() {
  const { user, loading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const handleDrawerNav = (to: string) => {
    setDrawerOpen(false);
    navigate(to);
  };

  return (
    <MuiAppBar position="static">
      <Toolbar>
        {/* Mobile hamburger */}
        <IconButton
          color="inherit"
          edge="start"
          onClick={() => setDrawerOpen(true)}
          sx={{ mr: 1, display: { md: 'none' } }}
        >
          <MenuIcon />
        </IconButton>

        <Typography
          variant="h6"
          component={RouterLink}
          to="/"
          sx={{ flexGrow: 0, textDecoration: 'none', color: 'inherit', mr: 3 }}
        >
          Bear Tracks
        </Typography>

        {/* Desktop nav */}
        <Box sx={{ flexGrow: 1, display: { xs: 'none', md: 'flex' }, gap: 1 }}>
          {NAV_LINKS.map((link) => (
            <Button key={link.to} color="inherit" component={RouterLink} to={link.to}>
              {link.label}
            </Button>
          ))}
        </Box>

        {/* Spacer on mobile so user controls stay right */}
        <Box sx={{ flexGrow: 1, display: { xs: 'flex', md: 'none' } }} />

        {!loading && (
          user ? (
            <>
              <Button color="inherit" component={RouterLink} to="/my-games" sx={{ display: { xs: 'none', md: 'inline-flex' } }}>
                My Games
              </Button>
              <Button color="inherit" component={RouterLink} to="/collection" sx={{ display: { xs: 'none', md: 'inline-flex' } }}>
                My Collection
              </Button>
              {user.email === 'andrew.vandever@gmail.com' && (
                <Button color="inherit" component={RouterLink} to="/admin/users" sx={{ display: { xs: 'none', md: 'inline-flex' } }}>
                  Admin
                </Button>
              )}
              <IconButton onClick={(e) => setAnchorEl(e.currentTarget)} sx={{ p: 0 }}>
                <Badge
                  invisible={!user.is_patron}
                  overlap="circular"
                  anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                  badgeContent="★"
                  sx={{
                    '& .MuiBadge-badge': {
                      fontSize: '0.6rem',
                      minWidth: 14,
                      height: 14,
                      backgroundColor: '#FF424D',
                      color: '#fff',
                    },
                  }}
                >
                  <Avatar
                    src={user.avatar_url || undefined}
                    alt={user.name}
                    sx={{ width: 32, height: 32 }}
                  />
                </Badge>
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
            <>
              <Button color="inherit" component={RouterLink} to={`/login?next=${encodeURIComponent(location.pathname)}`}>
                Sign In
              </Button>
              <Button color="inherit" component={RouterLink} to="/register">
                Register
              </Button>
            </>
          )
        )}
      </Toolbar>

      {/* Mobile drawer */}
      <Drawer anchor="left" open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        <Box sx={{ width: 240 }} role="presentation">
          <List>
            {NAV_LINKS.map((link) => (
              <ListItem key={link.to} disablePadding>
                <ListItemButton onClick={() => handleDrawerNav(link.to)}>
                  <ListItemText primary={link.label} />
                </ListItemButton>
              </ListItem>
            ))}
            {!loading && user && (
              <>
                <Divider />
                <ListItem disablePadding>
                  <ListItemButton onClick={() => handleDrawerNav('/my-games')}>
                    <ListItemText primary="My Games" />
                  </ListItemButton>
                </ListItem>
                <ListItem disablePadding>
                  <ListItemButton onClick={() => handleDrawerNav('/collection')}>
                    <ListItemText primary="My Collection" />
                  </ListItemButton>
                </ListItem>
                {user.email === 'andrew.vandever@gmail.com' && (
                  <ListItem disablePadding>
                    <ListItemButton onClick={() => handleDrawerNav('/admin/users')}>
                      <ListItemText primary="Admin" />
                    </ListItemButton>
                  </ListItem>
                )}
              </>
            )}
          </List>
        </Box>
      </Drawer>
    </MuiAppBar>
  );
}
