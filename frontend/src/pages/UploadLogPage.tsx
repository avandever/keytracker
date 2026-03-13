import { Container, Typography, Button, Box } from '@mui/material';

export default function UploadLogPage() {
  return (
    <Container maxWidth="sm" sx={{ mt: 6, textAlign: 'center' }}>
      <Typography variant="h5" gutterBottom>
        Upload a Game
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Games are uploaded automatically by the KeyTracker browser extension.
      </Typography>
      <Box>
        <Button
          variant="contained"
          size="large"
          href="https://chromewebstore.google.com/detail/keytracker/dkpffaedfeifhjlchfechechodlpgegp"
          target="_blank"
          rel="noopener noreferrer"
        >
          Get the KeyTracker Extension
        </Button>
      </Box>
    </Container>
  );
}
