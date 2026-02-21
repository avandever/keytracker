import { Box } from '@mui/material';

const S3_BASE = 'https://mastervault-storage-prod.s3.amazonaws.com/media/houses';

// Some houses use a KF_ prefix in the S3 bucket
const HOUSE_FILE_OVERRIDES: Record<string, string> = {
  Geistoid: 'KF_Geistoid',
};

function houseImageUrl(house: string): string {
  const file = HOUSE_FILE_OVERRIDES[house] || house;
  return `${S3_BASE}/${file}.png`;
}

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
          src={houseImageUrl(house)}
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
