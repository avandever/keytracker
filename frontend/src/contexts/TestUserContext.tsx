import { createContext, useContext, useState, type ReactNode } from 'react';
import { setTestUserIdForApi } from '../api/client';

interface TestUserContextValue {
  testUserId: number | null;
  setTestUserId: (id: number | null) => void;
}

const TestUserContext = createContext<TestUserContextValue>({
  testUserId: null,
  setTestUserId: () => {},
});

export function TestUserProvider({ children }: { children: ReactNode }) {
  const [testUserId, setTestUserIdState] = useState<number | null>(null);

  const setTestUserId = (id: number | null) => {
    setTestUserIdState(id);
    setTestUserIdForApi(id);
  };

  return (
    <TestUserContext.Provider value={{ testUserId, setTestUserId }}>
      {children}
    </TestUserContext.Provider>
  );
}

export function useTestUser() {
  return useContext(TestUserContext);
}
