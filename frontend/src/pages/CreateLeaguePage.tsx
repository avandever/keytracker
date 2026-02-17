import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Typography,
  TextField,
  Button,
  Box,
  Alert,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import { createLeague } from '../api/leagues';
import { useAuth } from '../contexts/AuthContext';

export default function CreateLeaguePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [feeAmount, setFeeAmount] = useState('');
  const [teamSize, setTeamSize] = useState('4');
  const [numTeams, setNumTeams] = useState('4');
  const [isTest, setIsTest] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!user?.is_league_admin) {
    return (
      <Container sx={{ mt: 3 }}>
        <Alert severity="error">You need league admin permissions to create a league.</Alert>
      </Container>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const league = await createLeague({
        name,
        description: description || undefined,
        fee_amount: feeAmount ? parseFloat(feeAmount) : null,
        team_size: parseInt(teamSize, 10),
        num_teams: parseInt(numTeams, 10),
        is_test: isTest,
      });
      navigate(`/league/${league.id}`);
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>Create League</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <TextField
          label="League Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <TextField
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          multiline
          rows={3}
        />
        <TextField
          label="Entry Fee"
          value={feeAmount}
          onChange={(e) => setFeeAmount(e.target.value)}
          type="number"
          inputProps={{ step: '0.01', min: '0' }}
          helperText="Leave blank for no fee"
        />
        <TextField
          label="Team Size"
          value={teamSize}
          onChange={(e) => setTeamSize(e.target.value)}
          type="number"
          inputProps={{ min: '2' }}
          required
        />
        <TextField
          label="Number of Teams"
          value={numTeams}
          onChange={(e) => setNumTeams(e.target.value)}
          type="number"
          inputProps={{ min: '2' }}
          required
        />
        <FormControlLabel
          control={<Checkbox checked={isTest} onChange={(e) => setIsTest(e.target.checked)} />}
          label="Test League"
        />
        <Button type="submit" variant="contained" disabled={submitting}>
          {submitting ? 'Creating...' : 'Create League'}
        </Button>
      </Box>
    </Container>
  );
}
