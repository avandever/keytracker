import { Box, TextField, Typography } from '@mui/material';

interface Props {
  label: string;
  prefix: string;
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
}

export default function PlayerFilterGroup({ label, prefix, values, onChange }: Props) {
  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>{label}</Typography>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <TextField
          label="Username"
          size="small"
          value={values[`user${prefix}`] || ''}
          onChange={(e) => onChange(`user${prefix}`, e.target.value)}
          sx={{ width: 160 }}
        />
        <TextField
          label="Deck ID"
          size="small"
          value={values[`deck${prefix}`] || ''}
          onChange={(e) => onChange(`deck${prefix}`, e.target.value)}
          sx={{ width: 200 }}
        />
        <TextField
          label="SAS Min"
          size="small"
          type="number"
          value={values[`sas_min${prefix}`] || ''}
          onChange={(e) => onChange(`sas_min${prefix}`, e.target.value)}
          sx={{ width: 90 }}
        />
        <TextField
          label="SAS Max"
          size="small"
          type="number"
          value={values[`sas_max${prefix}`] || ''}
          onChange={(e) => onChange(`sas_max${prefix}`, e.target.value)}
          sx={{ width: 90 }}
        />
        <TextField
          label="AERC Min"
          size="small"
          type="number"
          value={values[`aerc_min${prefix}`] || ''}
          onChange={(e) => onChange(`aerc_min${prefix}`, e.target.value)}
          sx={{ width: 90 }}
        />
        <TextField
          label="AERC Max"
          size="small"
          type="number"
          value={values[`aerc_max${prefix}`] || ''}
          onChange={(e) => onChange(`aerc_max${prefix}`, e.target.value)}
          sx={{ width: 90 }}
        />
      </Box>
    </Box>
  );
}
