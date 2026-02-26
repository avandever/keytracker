import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Container,
  Paper,
  Typography,
} from '@mui/material';
import { useSearchParams } from 'react-router-dom';
import { resendVerification } from '../api/auth';
import { useAuth } from '../contexts/AuthContext';

export default function VerifyEmailPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const expired = searchParams.get('expired') === '1';

  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  async function handleResend() {
    setStatus('sending');
    setErrorMsg('');
    try {
      await resendVerification();
      setStatus('sent');
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: string } } })?.response?.data?.error ||
        'Failed to resend. Please try again.';
      setErrorMsg(msg);
      setStatus('error');
    }
  }

  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <Paper sx={{ p: 4 }}>
        <Typography variant="h5" gutterBottom>
          Verify your email
        </Typography>

        {expired && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Your verification link has expired. Request a new one below.
          </Alert>
        )}

        {user?.email ? (
          <Typography gutterBottom>
            We sent a verification link to <strong>{user.email}</strong>. Check your inbox and click
            the link to activate your account.
          </Typography>
        ) : (
          <Typography gutterBottom>
            Check your inbox for a verification link.
          </Typography>
        )}

        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          You can continue browsing while you wait, but some features require a verified email.
        </Typography>

        {status === 'sent' && (
          <Alert severity="success" sx={{ mb: 2 }}>
            Verification email resent. Check your inbox.
          </Alert>
        )}
        {status === 'error' && (
          <Alert severity="error" sx={{ mb: 2 }}>{errorMsg}</Alert>
        )}

        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            onClick={handleResend}
            disabled={status === 'sending' || status === 'sent'}
          >
            {status === 'sending' ? 'Sending…' : 'Resend verification email'}
          </Button>
          <Button variant="text" href="/">
            Continue to site
          </Button>
        </Box>
      </Paper>
    </Container>
  );
}
