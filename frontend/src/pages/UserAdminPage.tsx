import { useEffect, useState } from 'react';
import {
  Container,
  Typography,
  CircularProgress,
  Alert,
  Box,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TablePagination,
} from '@mui/material';
import { listUsers, deleteUser, toggleFreeMembership } from '../api/admin';
import type { AdminUser } from '../api/admin';
import { useAuth } from '../contexts/AuthContext';

const ADMIN_EMAIL = 'andrew.vandever@gmail.com';

export default function UserAdminPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [perPage, setPerPage] = useState(50);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [deleteDialogUser, setDeleteDialogUser] = useState<AdminUser | null>(null);

  const refresh = () => {
    setLoading(true);
    listUsers(page + 1, perPage)
      .then((res) => {
        setUsers(res.users);
        setTotal(res.total);
      })
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, [page, perPage]);

  if (!user || user.email !== ADMIN_EMAIL) {
    return (
      <Container sx={{ mt: 3 }}>
        <Alert severity="error">Admin access required</Alert>
      </Container>
    );
  }

  const handleDelete = async () => {
    if (!deleteDialogUser) return;
    const userId = deleteDialogUser.id;
    setDeleteDialogUser(null);
    setError('');
    try {
      await deleteUser(userId);
      setSuccess('User deleted');
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  const handleToggleMembership = async (userId: number) => {
    setError('');
    try {
      const res = await toggleFreeMembership(userId);
      setSuccess(`Free membership ${res.free_membership ? 'granted' : 'revoked'}`);
      refresh();
    } catch (e: any) {
      setError(e.response?.data?.error || e.message);
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 3 }}>
      <Typography variant="h4" gutterBottom>User Admin</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Name</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell>{u.id}</TableCell>
                  <TableCell>{u.name}</TableCell>
                  <TableCell>{u.email}</TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                      {u.is_patron && <Chip label="Patron" size="small" color="success" />}
                      {u.free_membership && <Chip label="Free Member" size="small" color="info" />}
                      {u.is_league_admin && <Chip label="League Admin" size="small" color="warning" />}
                      {u.is_test_user && <Chip label="Test" size="small" />}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', gap: 0.5 }}>
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => handleToggleMembership(u.id)}
                      >
                        {u.free_membership ? 'Revoke Free' : 'Grant Free'}
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        color="error"
                        onClick={() => setDeleteDialogUser(u)}
                        disabled={u.email === ADMIN_EMAIL}
                      >
                        Delete
                      </Button>
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <TablePagination
            component="div"
            count={total}
            page={page}
            onPageChange={(_, p) => setPage(p)}
            rowsPerPage={perPage}
            onRowsPerPageChange={(e) => {
              setPerPage(parseInt(e.target.value, 10));
              setPage(0);
            }}
            rowsPerPageOptions={[25, 50, 100]}
          />
        </TableContainer>
      )}

      <Dialog open={deleteDialogUser !== null} onClose={() => setDeleteDialogUser(null)}>
        <DialogTitle>Delete User?</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete {deleteDialogUser?.name} ({deleteDialogUser?.email})?
            This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogUser(null)}>Cancel</Button>
          <Button onClick={handleDelete} variant="contained" color="error">Delete</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
