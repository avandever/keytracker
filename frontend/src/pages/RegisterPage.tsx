import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Container,
  Divider,
  Paper,
  TextField,
  Typography,
} from '@mui/material';
import { Link as RouterLink, useNavigate, useSearchParams } from 'react-router-dom';
import { useGoogleReCaptcha } from 'react-google-recaptcha-v3';
import { registerWithPassword } from '../api/auth';
import { useAuth } from '../contexts/AuthContext';

export default function RegisterPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const next = searchParams.get('next') || '/';
  const { refresh } = useAuth();
  const { executeRecaptcha } = useGoogleReCaptcha();

  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      const recaptchaToken = executeRecaptcha ? await executeRecaptcha('register') : undefined;
      const { redirect } = await registerWithPassword(email, name, password, recaptchaToken);
      await refresh();
      navigate(redirect, { replace: true });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: string } } })?.response?.data?.error ||
        'Registration failed. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Container maxWidth="xs" sx={{ mt: 8 }}>
      <Paper sx={{ p: 4 }}>
        <Typography variant="h5" gutterBottom>
          Create Account
        </Typography>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            fullWidth
            autoComplete="email"
          />
          <TextField
            label="Display Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            fullWidth
            autoComplete="name"
          />
          <TextField
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            fullWidth
            autoComplete="new-password"
            helperText="At least 8 characters"
          />
          <TextField
            label="Confirm Password"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            fullWidth
            autoComplete="new-password"
          />
          <Button type="submit" variant="contained" fullWidth disabled={loading}>
            {loading ? 'Creating account…' : 'Create Account'}
          </Button>
        </Box>

        <Divider sx={{ my: 3 }}>or</Divider>

        <Button
          variant="outlined"
          fullWidth
          href={`/auth/google/login?next=${encodeURIComponent(next)}`}
        >
          Sign up with Google
        </Button>

        <Typography variant="body2" align="center" sx={{ mt: 2 }}>
          Already have an account?{' '}
          <RouterLink to="/login">Sign in</RouterLink>
        </Typography>
      </Paper>
    </Container>
  );
}
