import { useEffect, useState } from 'react';
import {
  Alert,
  Avatar,
  Box,
  Button,
  Chip,
  Container,
  Divider,
  Paper,
  Typography,
  CircularProgress,
} from '@mui/material';
import { useAuth } from '../contexts/AuthContext';
import { useSearchParams } from 'react-router-dom';

export default function AccountPage() {
  const { user, loading, refresh } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [alert, setAlert] = useState<{ severity: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    if (searchParams.get('patreon_linked') === 'true') {
      setAlert({ severity: 'success', message: 'Patreon account linked successfully!' });
      refresh();
      searchParams.delete('patreon_linked');
      setSearchParams(searchParams, { replace: true });
    } else if (searchParams.get('patreon_refreshed') === 'true') {
      setAlert({ severity: 'success', message: 'Patreon status refreshed.' });
      refresh();
      searchParams.delete('patreon_refreshed');
      setSearchParams(searchParams, { replace: true });
    } else if (searchParams.get('patreon_error')) {
      const errorMap: Record<string, string> = {
        oauth_failed: 'Failed to connect to Patreon. Please try again.',
        identity_failed: 'Failed to retrieve Patreon account info.',
        already_linked: 'This Patreon account is already linked to another user.',
        not_linked: 'No Patreon account linked.',
        refresh_failed: 'Failed to refresh Patreon status. Try unlinking and re-linking.',
      };
      const code = searchParams.get('patreon_error') || '';
      setAlert({ severity: 'error', message: errorMap[code] || 'An unknown error occurred.' });
      searchParams.delete('patreon_error');
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams, refresh]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!user) {
    return (
      <Container maxWidth="sm" sx={{ textAlign: 'center', mt: 8 }}>
        <Typography variant="h5" gutterBottom>
          Account
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          Sign in to view your account.
        </Typography>
        <Button variant="contained" href="/auth/google/login?next=/account">
          Sign in with Google
        </Button>
      </Container>
    );
  }

  return (
    <Container maxWidth="sm" sx={{ mt: 4 }}>
      {alert && (
        <Alert severity={alert.severity} onClose={() => setAlert(null)} sx={{ mb: 2 }}>
          {alert.message}
        </Alert>
      )}
      <Paper sx={{ p: 4, textAlign: 'center' }}>
        <Avatar
          src={user.avatar_url || undefined}
          alt={user.name}
          sx={{ width: 80, height: 80, mx: 'auto', mb: 2 }}
        />
        <Typography variant="h5" gutterBottom>
          {user.name}
        </Typography>
        <Typography color="text.secondary" gutterBottom>
          {user.email}
        </Typography>

        <Divider sx={{ my: 3 }} />

        <Typography variant="h6" gutterBottom>
          Patreon
        </Typography>

        {!user.patreon_linked ? (
          <>
            <Typography color="text.secondary" sx={{ mb: 2 }}>
              Link your Patreon account to access supporter features.
            </Typography>
            <Button
              variant="contained"
              href="/auth/patreon/link"
              sx={{
                backgroundColor: '#FF424D',
                '&:hover': { backgroundColor: '#e03640' },
              }}
            >
              Link Patreon
            </Button>
          </>
        ) : (
          <>
            {user.is_patron ? (
              <>
                <Chip
                  label={user.patreon_tier_title || 'Active Patron'}
                  color="success"
                  sx={{ mb: 1 }}
                />
                <Typography color="text.secondary" sx={{ mt: 1, mb: 2 }}>
                  Thank you for your support!
                </Typography>
              </>
            ) : (
              <>
                <Chip label="Patreon Linked" sx={{ mb: 1 }} />
                <Typography color="text.secondary" sx={{ mt: 1, mb: 2 }}>
                  No active membership found. If you recently subscribed, try refreshing.
                </Typography>
              </>
            )}
            <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center' }}>
              <Button variant="outlined" size="small" href="/auth/patreon/refresh">
                Refresh Status
              </Button>
              <Button variant="outlined" size="small" color="error" href="/auth/patreon/unlink">
                Unlink
              </Button>
            </Box>
          </>
        )}

        <Divider sx={{ my: 3 }} />

        <Button
          variant="outlined"
          href="/auth/logout?next=/"
        >
          Sign Out
        </Button>
      </Paper>
    </Container>
  );
}
