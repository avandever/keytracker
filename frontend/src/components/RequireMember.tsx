import { Box, Button, CircularProgress, Container, Typography } from '@mui/material';
import { useAuth } from '../contexts/AuthContext';

/**
 * Gate for features that need a membership. Mirrors the backend's
 * member_required, which counts Patreon supporters and members of an
 * active league alike.
 */
export default function RequireMember({ children }: { children: React.ReactNode }) {
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
          Sign in required
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          You need to sign in to access this page.
        </Typography>
        <Button variant="contained" href="/auth/google/login?next=/">
          Sign in with Google
        </Button>
      </Container>
    );
  }

  if (!user.is_member) {
    return (
      <Container maxWidth="sm" sx={{ textAlign: 'center', mt: 8 }}>
        <Typography variant="h5" gutterBottom>
          Members Only
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          This feature is available to Patreon supporters and to players in an
          active league.
        </Typography>
        <Button variant="contained" href="/account">
          Link Patreon on Account Page
        </Button>
      </Container>
    );
  }

  return <>{children}</>;
}
