import { Box } from '@mui/material';

const S3_BASE = 'https://mastervault-storage-prod.s3.amazonaws.com/media/houses';

interface HouseIconsProps {
  houses: string[];
  size?: number;
}

export default function HouseIcons({ houses, size = 20 }: HouseIconsProps) {
  if (!houses || houses.length === 0) return null;
  return (
    <Box sx={{ display: 'flex', gap: 0.25, alignItems: 'center' }}>
      {houses.map((house) => (
        <img
          key={house}
          src={`${S3_BASE}/${house}.png`}
          alt={house}
          title={house}
          width={size}
          height={size}
          style={{ display: 'block' }}
        />
      ))}
    </Box>
  );
}
