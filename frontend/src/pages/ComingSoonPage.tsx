import { Container, Typography } from '@mui/material';

interface Props {
  title: string;
}

export default function ComingSoonPage({ title }: Props) {
  return (
    <Container maxWidth="md" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>{title}</Typography>
      <Typography variant="body1" color="text.secondary">Coming soon!</Typography>
    </Container>
  );
}
