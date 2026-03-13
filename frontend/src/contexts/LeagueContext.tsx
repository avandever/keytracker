import { createContext, useContext } from 'react';

const LeagueIdContext = createContext<number | null>(null);

export const LeagueIdProvider = LeagueIdContext.Provider;

export function useLeagueNumericId(): number {
  const id = useContext(LeagueIdContext);
  if (id === null) throw new Error('useLeagueNumericId must be used within a league route');
  return id;
}
