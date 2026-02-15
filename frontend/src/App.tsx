import { BrowserRouter, Routes, Route, Outlet } from 'react-router-dom';
import { Box } from '@mui/material';
import { AuthProvider } from './contexts/AuthContext';
import AppBar from './components/AppBar';
import RequireAuth from './components/RequireAuth';
import HomePage from './pages/HomePage';
import GameDetailPage from './pages/GameDetailPage';
import GamesSearchPage from './pages/GamesSearchPage';
import DeckDetailPage from './pages/DeckDetailPage';
import DecksSearchPage from './pages/DecksSearchPage';
import UserSearchPage from './pages/UserSearchPage';
import UserProfilePage from './pages/UserProfilePage';
import UploadLogPage from './pages/UploadLogPage';
import UploadSimplePage from './pages/UploadSimplePage';
import CsvToPodsPage from './pages/CsvToPodsPage';
import PrivacyPage from './pages/PrivacyPage';
import ComingSoonPage from './pages/ComingSoonPage';
import AccountPage from './pages/AccountPage';

function Layout() {
  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar />
      <Outlet />
    </Box>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter basename="/mui">
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/game/:crucibleGameId" element={<GameDetailPage />} />
            <Route path="/games" element={<GamesSearchPage />} />
            <Route path="/deck/:deckId" element={<DeckDetailPage />} />
            <Route path="/decks" element={<DecksSearchPage />} />
            <Route path="/user" element={<UserSearchPage />} />
            <Route path="/user/:username" element={<UserProfilePage />} />
            <Route path="/upload" element={<RequireAuth><UploadLogPage /></RequireAuth>} />
            <Route path="/upload_simple" element={<RequireAuth><UploadSimplePage /></RequireAuth>} />
            <Route path="/csv_to_pods" element={<RequireAuth><CsvToPodsPage /></RequireAuth>} />
            <Route path="/account" element={<AccountPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/fame" element={<ComingSoonPage title="Hall of Fame" />} />
            <Route path="/leaderboard" element={<ComingSoonPage title="Leaderboard" />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
