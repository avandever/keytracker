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
  FormHelperText,
  InputLabel,
  Link,
  MenuItem,
  Paper,
  Select,
  Tab,
  Tabs,
  TextField,
  Typography,
  CircularProgress,
} from '@mui/material';
import { useAuth } from '../contexts/AuthContext';
import { updateSettings } from '../api/auth';
import { syncCollection, getSyncStatus } from '../api/collection';
import { useSearchParams, Link as RouterLink } from 'react-router-dom';
import { alpha } from '@mui/material/styles';

function buildTimezoneOptions(): { value: string; label: string; offsetMin: number }[] {
  const now = new Date();
  const zones = Intl.supportedValuesOf('timeZone');
  return zones
    .map((tz) => {
      const fmt = new Intl.DateTimeFormat('en-US', {
        timeZone: tz,
        timeZoneName: 'short',
      });
      const parts = fmt.formatToParts(now);
      const abbr = parts.find((p) => p.type === 'timeZoneName')?.value ?? '';

      const utcDate = new Date(now.toLocaleString('en-US', { timeZone: 'UTC' }));
      const tzDate = new Date(now.toLocaleString('en-US', { timeZone: tz }));
      const offsetMin = Math.round((tzDate.getTime() - utcDate.getTime()) / 60000);
      const sign = offsetMin >= 0 ? '+' : '-';
      const abs = Math.abs(offsetMin);
      const h = Math.floor(abs / 60).toString().padStart(2, '0');
      const m = (abs % 60).toString().padStart(2, '0');
      const utcStr = `UTC${sign}${h}:${m}`;

      return { value: tz, label: `${tz} — ${abbr} (${utcStr})`, offsetMin };
    })
    .sort((a, b) => a.offsetMin - b.offsetMin || a.value.localeCompare(b.value));
}

const TIMEZONE_OPTIONS = buildTimezoneOptions();

export default function AccountPage() {
  const { user, loading, refresh } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [alert, setAlert] = useState<{ severity: 'success' | 'error'; message: string } | null>(null);
  const [dokKey, setDokKey] = useState(user?.dok_api_key || '');
  const [dokSaving, setDokSaving] = useState(false);
  const [collectionSyncing, setCollectionSyncing] = useState(false);
  const [newTcoName, setNewTcoName] = useState('');
  const [tcoSaving, setTcoSaving] = useState(false);
  const [dokProfileUrl, setDokProfileUrl] = useState(user?.dok_profile_url || '');
  const [country, setCountry] = useState(user?.country || '');
  const [timezone, setTimezone] = useState(user?.timezone || '');
  const [profileSaving, setProfileSaving] = useState(false);
  const [tab, setTab] = useState(0);
  const [mailingLine1, setMailingLine1] = useState(user?.mailing_address_line1 || '');
  const [mailingLine2, setMailingLine2] = useState(user?.mailing_address_line2 || '');
  const [mailingCity, setMailingCity] = useState(user?.mailing_city || '');
  const [mailingState, setMailingState] = useState(user?.mailing_state || '');
  const [mailingPostal, setMailingPostal] = useState(user?.mailing_postal_code || '');
  const [mailingCountry, setMailingCountry] = useState(user?.mailing_country || '');
  const [mailingSaving, setMailingSaving] = useState(false);

  useEffect(() => {
    if (user) {
      setDokKey(user.dok_api_key || '');
      setDokProfileUrl(user.dok_profile_url || '');
      setCountry(user.country || '');
      setTimezone(user.timezone || '');
      setMailingLine1(user.mailing_address_line1 || '');
      setMailingLine2(user.mailing_address_line2 || '');
      setMailingCity(user.mailing_city || '');
      setMailingState(user.mailing_state || '');
      setMailingPostal(user.mailing_postal_code || '');
      setMailingCountry(user.mailing_country || '');
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
    } else if (searchParams.get('discord_linked') === 'true') {
      setAlert({ severity: 'success', message: 'Discord account linked successfully!' });
      refresh();
      searchParams.delete('discord_linked');
      setSearchParams(searchParams, { replace: true });
    } else if (searchParams.get('discord_error')) {
      const discordErrorMap: Record<string, string> = {
        oauth_failed: 'Failed to connect to Discord. Please try again.',
        identity_failed: 'Failed to retrieve Discord account info.',
        already_linked: 'This Discord account is already linked to another user.',
      };
      const code = searchParams.get('discord_error') || '';
      setAlert({ severity: 'error', message: discordErrorMap[code] || 'An unknown error occurred.' });
      searchParams.delete('discord_error');
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
      <Paper sx={{ textAlign: 'center' }}>
        <Box sx={{ pt: 4, pb: 2, px: 4 }}>
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
        </Box>

        <Tabs value={tab} onChange={(_, v) => setTab(v)} centered sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tab label="My Info" />
          <Tab label="Integrations" />
        </Tabs>

        {/* My Info tab */}
        {tab === 0 && (
        <Box sx={{ p: 4 }}>
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
          label="DoK Collection URL (My Decks)"
          helperText="Displayed publicly on your player profile"
          sx={{ mb: 2 }}
        />
        <FormControl fullWidth size="small" sx={{ mb: 2 }}>
          <InputLabel>Country</InputLabel>
          <Select value={country} label="Country" onChange={(e) => setCountry(e.target.value)}>
            <MenuItem value="">-- Select --</MenuItem>
            {/* prettier-ignore */}
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
          <FormHelperText>Used for league organization; not displayed publicly</FormHelperText>
        </FormControl>
        <FormControl fullWidth size="small" sx={{ mb: 2 }}>
          <InputLabel>Timezone</InputLabel>
          <Select value={timezone} label="Timezone" onChange={(e) => setTimezone(e.target.value)}>
            <MenuItem value="">-- Select --</MenuItem>
            {timezone && !TIMEZONE_OPTIONS.find((o) => o.value === timezone) && (
              <MenuItem value={timezone}>{timezone} (legacy)</MenuItem>
            )}
            {TIMEZONE_OPTIONS.map((o) => (
              <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>
            ))}
          </Select>
          <FormHelperText>Shared with league admins, captains, and opponents to help schedule matches</FormHelperText>
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
          Mailing Address
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Used for physical prize delivery. Not shared publicly.
        </Typography>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, mb: 2 }}>
          <TextField
            fullWidth size="small" label="Address Line 1"
            value={mailingLine1} onChange={(e) => setMailingLine1(e.target.value)}
          />
          <TextField
            fullWidth size="small" label="Address Line 2"
            value={mailingLine2} onChange={(e) => setMailingLine2(e.target.value)}
          />
          <Box sx={{ display: 'flex', gap: 1.5 }}>
            <TextField
              fullWidth size="small" label="City"
              value={mailingCity} onChange={(e) => setMailingCity(e.target.value)}
            />
            <TextField
              sx={{ width: 180 }} size="small" label="State / Province"
              value={mailingState} onChange={(e) => setMailingState(e.target.value)}
            />
            <TextField
              sx={{ width: 140 }} size="small" label="Postal Code"
              value={mailingPostal} onChange={(e) => setMailingPostal(e.target.value)}
            />
          </Box>
          <TextField
            fullWidth size="small" label="Country"
            value={mailingCountry} onChange={(e) => setMailingCountry(e.target.value)}
          />
        </Box>
        <Button
          variant="contained"
          size="small"
          disabled={mailingSaving}
          onClick={async () => {
            setMailingSaving(true);
            try {
              await updateSettings({
                mailing_address_line1: mailingLine1,
                mailing_address_line2: mailingLine2,
                mailing_city: mailingCity,
                mailing_state: mailingState,
                mailing_postal_code: mailingPostal,
                mailing_country: mailingCountry,
              });
              await refresh();
              setAlert({ severity: 'success', message: 'Mailing address saved.' });
            } catch (e: any) {
              setAlert({ severity: 'error', message: e.response?.data?.error || 'Save failed.' });
            } finally {
              setMailingSaving(false);
            }
          }}
        >
          {mailingSaving ? 'Saving...' : 'Save Address'}
        </Button>

        <Divider sx={{ my: 3 }} />

        <Button variant="outlined" href="/auth/logout?next=/">
          Sign Out
        </Button>
        </Box>
        )}

        {/* Integrations tab */}
        {tab === 1 && (
        <Box sx={{ p: 4 }}>
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
            <Chip label="Google Linked" sx={(theme) => ({ mb: 1, bgcolor: alpha(theme.palette.success.main, 0.12), color: theme.palette.success.dark })} />
            <Box sx={{ mt: 1 }}>
              <Button variant="outlined" size="small" color="error" href="/auth/google/unlink">
                Unlink
              </Button>
            </Box>
          </>
        )}

        <Divider sx={{ my: 3 }} />

        <Typography variant="h6" gutterBottom>
          Discord
        </Typography>

        {!user.discord_linked ? (
          <>
            <Typography color="text.secondary" sx={{ mb: 2 }}>
              Link your Discord account. Required for league signup.
            </Typography>
            <Button
              variant="contained"
              href="/auth/discord/link"
              sx={{
                backgroundColor: '#5865F2',
                '&:hover': { backgroundColor: '#4752c4' },
              }}
            >
              Link Discord
            </Button>
          </>
        ) : (
          <>
            <Chip
              label={`@${user.discord_username}`}
              sx={(theme) => ({ mb: 1, bgcolor: alpha(theme.palette.success.main, 0.12), color: theme.palette.success.dark })}
            />
            <Box sx={{ mt: 1 }}>
              <Button variant="outlined" size="small" color="error" href="/auth/discord/unlink">
                Unlink
              </Button>
            </Box>
          </>
        )}

        <Divider sx={{ my: 3 }} />

        <Typography variant="h6" gutterBottom>
          Decks of Keyforge
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Enter your personal DoK API key to enable enhanced deck lookups. Find yours on the{' '}
          <Link href="https://decksofkeyforge.com/about/sellers-and-devs" target="_blank" rel="noopener noreferrer">
            DoK Sellers &amp; Devs page
          </Link>
          . "You may provide this to other sites for them to sync your DoK deck list with their site, but you should
          only give it to sites or tools you trust."
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
        <Button
          variant="outlined"
          size="small"
          disabled={collectionSyncing || !user?.dok_api_key}
          sx={{ ml: 1 }}
          onClick={async () => {
            setCollectionSyncing(true);
            try {
              await syncCollection();
              // Poll until the job finishes
              const poll = async (): Promise<void> => {
                const status = await getSyncStatus();
                const d = status.data;
                if (d.status === 'done') {
                  setAlert({
                    severity: 'success',
                    message: `Synced ${d.standard_decks} standard + ${d.alliance_decks} alliance decks. View your collection.`,
                  });
                  setCollectionSyncing(false);
                } else if (d.status === 'failed') {
                  setAlert({ severity: 'error', message: d.error || 'Sync failed.' });
                  setCollectionSyncing(false);
                } else {
                  setTimeout(poll, 2000);
                }
              };
              setTimeout(poll, 2000);
            } catch (e: any) {
              const msg = e.response?.data?.error || 'Sync failed.';
              setAlert({ severity: 'error', message: msg });
              setCollectionSyncing(false);
            }
          }}
        >
          {collectionSyncing ? <CircularProgress size={16} sx={{ mr: 1 }} /> : null}
          {collectionSyncing ? 'Syncing...' : 'Sync Collection'}
        </Button>
        {user?.dok_api_key && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            <RouterLink to="/collection">View My Collection</RouterLink>
          </Typography>
        )}

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

        </Box>
        )}

      </Paper>
    </Container>
  );
}
