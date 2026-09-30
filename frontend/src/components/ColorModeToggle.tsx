import { useState } from 'react';
import { IconButton, Menu, MenuItem, ListItemIcon, ListItemText, Tooltip } from '@mui/material';
import LightModeIcon from '@mui/icons-material/LightMode';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import BrightnessAutoIcon from '@mui/icons-material/BrightnessAuto';
import { useColorMode } from '../contexts/ColorModeContext';
import type { ColorModePreference } from '../contexts/ColorModeContext';

const OPTIONS: { value: ColorModePreference; label: string }[] = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'Match device' },
];

function icon(preference: ColorModePreference) {
  if (preference === 'light') return <LightModeIcon fontSize="small" />;
  if (preference === 'dark') return <DarkModeIcon fontSize="small" />;
  return <BrightnessAutoIcon fontSize="small" />;
}

export default function ColorModeToggle() {
  const { preference, setPreference } = useColorMode();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const choose = (next: ColorModePreference) => {
    setPreference(next);
    setAnchorEl(null);
  };

  return (
    <>
      <Tooltip title="Appearance">
        <IconButton
          color="inherit"
          aria-label="Appearance"
          onClick={(e) => setAnchorEl(e.currentTarget)}
          sx={{ mr: 0.5 }}
        >
          {icon(preference)}
        </IconButton>
      </Tooltip>
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        {OPTIONS.map((option) => (
          <MenuItem
            key={option.value}
            selected={option.value === preference}
            onClick={() => choose(option.value)}
          >
            <ListItemIcon>{icon(option.value)}</ListItemIcon>
            <ListItemText>{option.label}</ListItemText>
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
