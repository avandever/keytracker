import { useEffect, useState } from 'react';
import {
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Paper,
} from '@mui/material';
import { useAuth } from '../contexts/AuthContext';
import { useTestUser } from '../contexts/TestUserContext';
import { listTestUsers } from '../api/leagues';
import type { UserBrief } from '../types';

export default function TestUserPicker() {
  const { user } = useAuth();
  const { testUserId, setTestUserId } = useTestUser();
  const [testUsers, setTestUsers] = useState<UserBrief[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!user?.is_league_admin) return;
    setLoading(true);
    listTestUsers()
      .then(setTestUsers)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user?.is_league_admin]);

  if (!user?.is_league_admin) return null;
  if (loading && testUsers.length === 0) return null;

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'fixed',
        bottom: 16,
        right: 16,
        p: 2,
        zIndex: 1300,
        minWidth: 220,
        opacity: 0.95,
      }}
    >
      <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
        Impersonate Test User
      </Typography>
      <FormControl size="small" fullWidth>
        <InputLabel>Acting as</InputLabel>
        <Select
          value={testUserId != null ? String(testUserId) : ''}
          label="Acting as"
          onChange={(e) => {
            const val = e.target.value as string;
            setTestUserId(val === '' ? null : Number(val));
          }}
        >
          <MenuItem value="">
            <em>Yourself ({user.name})</em>
          </MenuItem>
          {testUsers.map((tu) => (
            <MenuItem key={tu.id} value={String(tu.id)}>
              {tu.name}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      {testUserId != null && (
        <Typography variant="body2" color="warning.main" sx={{ mt: 1 }}>
          Acting as: {testUsers.find((u) => u.id === testUserId)?.name}
        </Typography>
      )}
    </Paper>
  );
}
