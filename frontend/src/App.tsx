import { BrowserRouter, Routes, Route, Outlet, Link as RouterLink, useParams } from 'react-router-dom';
import { Box, Typography, CircularProgress, Alert, Container } from '@mui/material';
import { GoogleReCaptchaProvider } from 'react-google-recaptcha-v3';
import { useState, useEffect } from 'react';
import { AuthProvider } from './contexts/AuthContext';
import { TestUserProvider } from './contexts/TestUserContext';
import { LeagueIdProvider } from './contexts/LeagueContext';
import { getLeagueByName } from './api/leagues';
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
import TimingLeaderboardPage from './pages/TimingLeaderboardPage';
import MyCollectionPage from './pages/MyCollectionPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import VerifyEmailPage from './pages/VerifyEmailPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';

function LeagueByIdWrapper() {
  const { leagueId } = useParams<{ leagueId: string }>();
  const numericId = parseInt(leagueId!, 10);
  return (
    <LeagueIdProvider value={numericId}>
      <Outlet />
    </LeagueIdProvider>
  );
}

function LeagueByNameWrapper() {
  const { leagueName } = useParams<{ leagueName: string }>();
  const [numericId, setNumericId] = useState<number | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const asNum = parseInt(leagueName!, 10);
    if (!isNaN(asNum) && String(asNum) === leagueName) {
      setNumericId(asNum);
      return;
    }
    getLeagueByName(leagueName!)
      .then((league) => setNumericId(league.id))
      .catch(() => setError('League not found'));
  }, [leagueName]);

  if (error) return <Container sx={{ mt: 3 }}><Alert severity="error">{error}</Alert></Container>;
  if (numericId === null) return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}><CircularProgress /></Box>;
  return (
    <LeagueIdProvider value={numericId}>
      <Outlet />
    </LeagueIdProvider>
  );
}

function Layout() {
  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', display: 'flex', flexDirection: 'column' }}>
      <AppBar />
      <Box sx={{ flex: 1 }}>
        <Outlet />
      </Box>
      <Box component="footer" sx={{ py: 2, textAlign: 'center', borderTop: 1, borderColor: 'divider' }}>
        <Typography variant="caption" color="text.secondary">
          <RouterLink to="/privacy" style={{ color: 'inherit' }}>Privacy Policy</RouterLink>
          {' · '}Bear Tracks
        </Typography>
      </Box>
    </Box>
  );
}

const RECAPTCHA_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY as string | undefined;

export default function App() {
  const inner = (
    <AuthProvider>
      <TestUserProvider>
        <BrowserRouter basename="/">
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/game/:crucibleGameId" element={<GameDetailPage />} />
              <Route path="/games/:crucibleGameId" element={<GameDetailPage />} />
              <Route path="/games" element={<GamesSearchPage />} />
              <Route path="/deck/:deckId" element={<DeckDetailPage />} />
              <Route path="/decks" element={<DecksSearchPage />} />
              <Route path="/user" element={<UserSearchPage />} />
              <Route path="/user/:username" element={<UserProfilePage />} />
              <Route path="/upload" element={<RequireAuth><UploadLogPage /></RequireAuth>} />
              <Route path="/csv_to_pods" element={<RequireAuth><CsvToPodsPage /></RequireAuth>} />
              <Route path="/account" element={<AccountPage />} />
              <Route path="/my-games" element={<RequireAuth><MyGamesPage /></RequireAuth>} />
              <Route path="/leagues" element={<LeagueListPage />} />
              <Route path="/leagues/new" element={<RequireAuth><CreateLeaguePage /></RequireAuth>} />
              <Route path="/league/by_id/:leagueId" element={<LeagueByIdWrapper />}>
                <Route index element={<LeagueDetailPage />} />
                <Route path="admin" element={<RequireAuth><LeagueAdminPage /></RequireAuth>} />
                <Route path="draft" element={<RequireAuth><DraftBoardPage /></RequireAuth>} />
                <Route path="my-info" element={<RequireAuth><MyLeagueInfoPage /></RequireAuth>} />
                <Route path="my-team" element={<RequireAuth><MyTeamPage /></RequireAuth>} />
              </Route>
              <Route path="/league/:leagueName" element={<LeagueByNameWrapper />}>
                <Route index element={<LeagueDetailPage />} />
                <Route path="admin" element={<RequireAuth><LeagueAdminPage /></RequireAuth>} />
                <Route path="draft" element={<RequireAuth><DraftBoardPage /></RequireAuth>} />
                <Route path="my-info" element={<RequireAuth><MyLeagueInfoPage /></RequireAuth>} />
                <Route path="my-team" element={<RequireAuth><MyTeamPage /></RequireAuth>} />
              </Route>
              <Route path="/admin/users" element={<RequireAuth><UserAdminPage /></RequireAuth>} />
              <Route path="/matches" element={<StandaloneMatchesPage />} />
              <Route path="/matches/:matchId" element={<StandaloneMatchPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/verify-email" element={<VerifyEmailPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              <Route path="/privacy" element={<PrivacyPage />} />
              <Route path="/timing" element={<TimingLeaderboardPage />} />
              <Route path="/collection" element={<RequireAuth><MyCollectionPage /></RequireAuth>} />
              <Route path="/fame" element={<ComingSoonPage title="Hall of Fame" />} />
              <Route path="/leaderboard" element={<ComingSoonPage title="Leaderboard" />} />
            </Route>
          </Routes>
          <TestUserPicker />
        </BrowserRouter>
      </TestUserProvider>
    </AuthProvider>
  );

  if (RECAPTCHA_SITE_KEY) {
    return (
      <GoogleReCaptchaProvider reCaptchaKey={RECAPTCHA_SITE_KEY}>
        {inner}
      </GoogleReCaptchaProvider>
    );
  }
  return inner;
}
