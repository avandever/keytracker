import { useEffect, useState } from 'react';
import {
  Alert,
  Avatar,
  Box,
  Button,
  Chip,
  Container,
  Divider,
  FormControl,
  InputLabel,
  Link,
  MenuItem,
  Paper,
  Select,
  TextField,
  Typography,
  CircularProgress,
} from '@mui/material';
import { useAuth } from '../contexts/AuthContext';
import { updateSettings } from '../api/auth';
import { useSearchParams } from 'react-router-dom';

export default function AccountPage() {
  const { user, loading, refresh } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [alert, setAlert] = useState<{ severity: 'success' | 'error'; message: string } | null>(null);
  const [dokKey, setDokKey] = useState(user?.dok_api_key || '');
  const [dokSaving, setDokSaving] = useState(false);
  const [newTcoName, setNewTcoName] = useState('');
  const [tcoSaving, setTcoSaving] = useState(false);
  const [dokProfileUrl, setDokProfileUrl] = useState(user?.dok_profile_url || '');
  const [country, setCountry] = useState(user?.country || '');
  const [timezone, setTimezone] = useState(user?.timezone || '');
  const [profileSaving, setProfileSaving] = useState(false);

  useEffect(() => {
    if (user) {
      setDokKey(user.dok_api_key || '');
      setDokProfileUrl(user.dok_profile_url || '');
      setCountry(user.country || '');
      setTimezone(user.timezone || '');
    }
  }, [user]);

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
    } else if (searchParams.get('google_linked') === 'true') {
      setAlert({ severity: 'success', message: 'Google account linked successfully!' });
      refresh();
      searchParams.delete('google_linked');
      setSearchParams(searchParams, { replace: true });
    } else if (searchParams.get('google_error')) {
      const googleErrorMap: Record<string, string> = {
        oauth_failed: 'Failed to connect to Google. Please try again.',
        already_linked: 'This Google account is already linked to another user.',
        cannot_unlink_no_password: 'Cannot unlink Google — no password set on this account.',
      };
      const code = searchParams.get('google_error') || '';
      setAlert({ severity: 'error', message: googleErrorMap[code] || 'An unknown error occurred.' });
      searchParams.delete('google_error');
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
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              Not a patron yet?{' '}
              <Link href="https://www.patreon.com/AV8R772" target="_blank" rel="noopener noreferrer">
                Support Bear Tracks on Patreon
              </Link>
            </Typography>
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
                  No active membership found. If you recently subscribed, try refreshing.{' '}
                  <Link href="https://www.patreon.com/AV8R772" target="_blank" rel="noopener noreferrer">
                    Support Bear Tracks on Patreon
                  </Link>
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

        <Typography variant="h6" gutterBottom>
          Google
        </Typography>

        {!user.google_linked ? (
          <>
            <Typography color="text.secondary" sx={{ mb: 2 }}>
              Link your Google account to enable Google sign-in.
            </Typography>
            <Button variant="contained" href="/auth/google/link">
              Link Google Account
            </Button>
          </>
        ) : (
          <>
            <Chip label="Google Linked" color="success" sx={{ mb: 1 }} />
            <Box sx={{ mt: 1 }}>
              <Button variant="outlined" size="small" color="error" href="/auth/google/unlink">
                Unlink
              </Button>
            </Box>
          </>
        )}

        <Divider sx={{ my: 3 }} />

        <Typography variant="h6" gutterBottom>
          League Profile
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Required for league signup. Set your DoK profile, country, and timezone.
        </Typography>
        <TextField
          fullWidth
          size="small"
          value={dokProfileUrl}
          onChange={(e) => setDokProfileUrl(e.target.value)}
          placeholder="https://decksofkeyforge.com/users/your-username"
          label="DoK Profile URL"
          sx={{ mb: 2 }}
        />
        <FormControl fullWidth size="small" sx={{ mb: 2 }}>
          <InputLabel>Country</InputLabel>
          <Select value={country} label="Country" onChange={(e) => setCountry(e.target.value)}>
            <MenuItem value="">-- Select --</MenuItem>
            {[
              'Argentina', 'Australia', 'Austria', 'Belgium', 'Brazil', 'Canada',
              'Chile', 'China', 'Colombia', 'Czech Republic', 'Denmark', 'Finland',
              'France', 'Germany', 'Greece', 'Hungary', 'India', 'Indonesia',
              'Ireland', 'Israel', 'Italy', 'Japan', 'Malaysia', 'Mexico',
              'Netherlands', 'New Zealand', 'Norway', 'Peru', 'Philippines',
              'Poland', 'Portugal', 'Romania', 'Russia', 'Singapore',
              'South Africa', 'South Korea', 'Spain', 'Sweden', 'Switzerland',
              'Taiwan', 'Thailand', 'Turkey', 'Ukraine', 'United Kingdom',
              'United States', 'Vietnam',
            ].map((c) => (
              <MenuItem key={c} value={c}>{c}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl fullWidth size="small" sx={{ mb: 2 }}>
          <InputLabel>Timezone</InputLabel>
          <Select value={timezone} label="Timezone" onChange={(e) => setTimezone(e.target.value)}>
            <MenuItem value="">-- Select --</MenuItem>
            {[
              'NZST (UTC+12)', 'AEST (UTC+10)', 'JST (UTC+9)', 'CST-Asia (UTC+8)',
              'IST (UTC+5:30)', 'EET (UTC+2)', 'CET (UTC+1)', 'GMT (UTC+0)',
              'BRT (UTC-3)', 'EST (UTC-5)', 'CST (UTC-6)', 'MST (UTC-7)',
              'PST (UTC-8)', 'AKST (UTC-9)', 'HST (UTC-10)',
            ].map((tz) => (
              <MenuItem key={tz} value={tz}>{tz}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button
          variant="contained"
          size="small"
          disabled={profileSaving}
          onClick={async () => {
            setProfileSaving(true);
            try {
              await updateSettings({
                dok_profile_url: dokProfileUrl,
                country,
                timezone,
              });
              await refresh();
              setAlert({ severity: 'success', message: 'League profile saved.' });
            } catch (e: any) {
              setAlert({ severity: 'error', message: e.response?.data?.error || 'Failed to save.' });
            } finally {
              setProfileSaving(false);
            }
          }}
        >
          {profileSaving ? 'Saving...' : 'Save Profile'}
        </Button>

        <Divider sx={{ my: 3 }} />

        <Typography variant="h6" gutterBottom>
          Decks of Keyforge
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Enter your personal DoK API key to enable enhanced deck lookups.
        </Typography>
        <TextField
          fullWidth
          size="small"
          value={dokKey}
          onChange={(e) => setDokKey(e.target.value)}
          placeholder="xxxxxxxx-xxxx-4xxx-xxxx-xxxxxxxxxxxx"
          inputProps={{ style: { fontFamily: 'monospace' } }}
          sx={{ mb: 1 }}
        />
        <Button
          variant="contained"
          size="small"
          disabled={dokSaving}
          onClick={async () => {
            setDokSaving(true);
            try {
              await updateSettings({ dok_api_key: dokKey });
              await refresh();
              setAlert({ severity: 'success', message: 'DoK API key saved.' });
            } catch (e: any) {
              setAlert({ severity: 'error', message: e.response?.data?.error || 'Failed to save.' });
            } finally {
              setDokSaving(false);
            }
          }}
        >
          {dokSaving ? 'Saving...' : 'Save'}
        </Button>

        <Divider sx={{ my: 3 }} />

        <Typography variant="h6" gutterBottom>
          TCO Usernames
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Link your Crucible Online usernames to track your games.
        </Typography>
        {user.tco_usernames.length > 0 && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2, justifyContent: 'center' }}>
            {user.tco_usernames.map((name) => (
              <Chip
                key={name}
                label={name}
                onDelete={async () => {
                  setTcoSaving(true);
                  try {
                    await updateSettings({
                      tco_usernames: user.tco_usernames.filter((u) => u !== name),
                    });
                    await refresh();
                  } catch (e: any) {
                    setAlert({ severity: 'error', message: 'Failed to remove username.' });
                  } finally {
                    setTcoSaving(false);
                  }
                }}
                disabled={tcoSaving}
              />
            ))}
          </Box>
        )}
        <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center' }}>
          <TextField
            size="small"
            value={newTcoName}
            onChange={(e) => setNewTcoName(e.target.value)}
            placeholder="TCO username"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                const trimmed = newTcoName.trim();
                if (!trimmed || user.tco_usernames.includes(trimmed)) return;
                setTcoSaving(true);
                updateSettings({ tco_usernames: [...user.tco_usernames, trimmed] })
                  .then(() => refresh())
                  .then(() => { setNewTcoName(''); })
                  .catch(() => setAlert({ severity: 'error', message: 'Failed to add username.' }))
                  .finally(() => setTcoSaving(false));
              }
            }}
          />
          <Button
            variant="contained"
            size="small"
            disabled={tcoSaving || !newTcoName.trim()}
            onClick={async () => {
              const trimmed = newTcoName.trim();
              if (!trimmed || user.tco_usernames.includes(trimmed)) return;
              setTcoSaving(true);
              try {
                await updateSettings({ tco_usernames: [...user.tco_usernames, trimmed] });
                await refresh();
                setNewTcoName('');
              } catch {
                setAlert({ severity: 'error', message: 'Failed to add username.' });
              } finally {
                setTcoSaving(false);
              }
            }}
          >
            Add
          </Button>
        </Box>

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
