import { Container, Typography } from '@mui/material';

export default function PrivacyPage() {
  return (
    <Container maxWidth="md" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>Privacy Policy</Typography>
      <Typography variant="body1">
        Bear Tracks collects game data from The Crucible Online. Player usernames
        are stored as part of game records. Players may request anonymization of
        their game records.
      </Typography>
    </Container>
  );
}
