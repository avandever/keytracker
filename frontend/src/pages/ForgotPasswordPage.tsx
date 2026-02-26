import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Container,
  Paper,
  TextField,
  Typography,
} from '@mui/material';
import { useSearchParams } from 'react-router-dom';
import { forgotPassword } from '../api/auth';

export default function ForgotPasswordPage() {
  const [searchParams] = useSearchParams();
  const expired = searchParams.get('expired') === '1';

  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await forgotPassword(email);
      setSubmitted(true);
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Container maxWidth="xs" sx={{ mt: 8 }}>
      <Paper sx={{ p: 4 }}>
        <Typography variant="h5" gutterBottom>
          Forgot Password
        </Typography>

        {expired && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Your reset link has expired. Request a new one below.
          </Alert>
        )}

        {submitted ? (
          <Alert severity="success">
            If an account with that email exists, we&apos;ve sent a password reset link.
            Check your inbox.
          </Alert>
        ) : (
          <>
            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
            <Typography variant="body2" sx={{ mb: 2 }}>
              Enter your email address and we&apos;ll send you a link to reset your password.
            </Typography>
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
              <Button type="submit" variant="contained" fullWidth disabled={loading}>
                {loading ? 'Sending…' : 'Send reset link'}
              </Button>
            </Box>
          </>
        )}
      </Paper>
    </Container>
  );
}
