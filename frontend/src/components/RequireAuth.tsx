import { Box, Button, CircularProgress, Container, Typography } from '@mui/material';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

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
          Sign in required
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          You need to sign in to access this page.
        </Typography>
        <Button
          variant="contained"
          href={`/auth/google/login?next=${encodeURIComponent(location.pathname)}`}
        >
          Sign in with Google
        </Button>
      </Container>
    );
  }

  return <>{children}</>;
}
