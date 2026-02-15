import { Avatar, Box, Button, Container, Paper, Typography, CircularProgress } from '@mui/material';
import { useAuth } from '../contexts/AuthContext';

export default function AccountPage() {
  const { user, loading } = useAuth();

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
        <Button variant="contained" href="/auth/google/login?next=/mui/account">
          Sign in with Google
        </Button>
      </Container>
    );
  }

  return (
    <Container maxWidth="sm" sx={{ mt: 4 }}>
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
        <Button
          variant="outlined"
          href="/auth/logout?next=/mui/"
          sx={{ mt: 3 }}
        >
          Sign Out
        </Button>
      </Paper>
    </Container>
  );
}
