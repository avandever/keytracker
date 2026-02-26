import { BrowserRouter, Routes, Route, Outlet } from 'react-router-dom';
import { Box } from '@mui/material';
import { AuthProvider } from './contexts/AuthContext';
import { TestUserProvider } from './contexts/TestUserContext';
import AppBar from './components/AppBar';
import TestUserPicker from './components/TestUserPicker';
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
import MyGamesPage from './pages/MyGamesPage';
import LeagueListPage from './pages/LeagueListPage';
import CreateLeaguePage from './pages/CreateLeaguePage';
import LeagueDetailPage from './pages/LeagueDetailPage';
import LeagueAdminPage from './pages/LeagueAdminPage';
import DraftBoardPage from './pages/DraftBoardPage';
import MyLeagueInfoPage from './pages/MyLeagueInfoPage';
import MyTeamPage from './pages/MyTeamPage';
import UserAdminPage from './pages/UserAdminPage';
import StandaloneMatchesPage from './pages/StandaloneMatchesPage';
import StandaloneMatchPage from './pages/StandaloneMatchPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import VerifyEmailPage from './pages/VerifyEmailPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';

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
      <TestUserProvider>
        <BrowserRouter basename="/">
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
              <Route path="/my-games" element={<RequireAuth><MyGamesPage /></RequireAuth>} />
              <Route path="/leagues" element={<LeagueListPage />} />
              <Route path="/leagues/new" element={<RequireAuth><CreateLeaguePage /></RequireAuth>} />
              <Route path="/league/:leagueId" element={<LeagueDetailPage />} />
              <Route path="/league/:leagueId/admin" element={<RequireAuth><LeagueAdminPage /></RequireAuth>} />
              <Route path="/league/:leagueId/draft" element={<RequireAuth><DraftBoardPage /></RequireAuth>} />
              <Route path="/league/:leagueId/my-info" element={<RequireAuth><MyLeagueInfoPage /></RequireAuth>} />
              <Route path="/league/:leagueId/my-team" element={<RequireAuth><MyTeamPage /></RequireAuth>} />
              <Route path="/admin/users" element={<RequireAuth><UserAdminPage /></RequireAuth>} />
              <Route path="/matches" element={<StandaloneMatchesPage />} />
              <Route path="/matches/:matchId" element={<StandaloneMatchPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/verify-email" element={<VerifyEmailPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              <Route path="/privacy" element={<PrivacyPage />} />
              <Route path="/fame" element={<ComingSoonPage title="Hall of Fame" />} />
              <Route path="/leaderboard" element={<ComingSoonPage title="Leaderboard" />} />
            </Route>
          </Routes>
          <TestUserPicker />
        </BrowserRouter>
      </TestUserProvider>
    </AuthProvider>
  );
}
