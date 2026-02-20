import apiClient from './client';

export interface AdminUser {
  id: number;
  name: string;
  email: string;
  is_member: boolean;
  free_membership: boolean;
  is_patron: boolean;
  is_test_user: boolean;
  is_league_admin: boolean;
}

export interface AdminUsersResponse {
  users: AdminUser[];
  total: number;
  page: number;
  per_page: number;
}

export async function listUsers(page = 1, perPage = 50): Promise<AdminUsersResponse> {
  const { data } = await apiClient.get(`/admin/users?page=${page}&per_page=${perPage}`);
  return data;
}

export async function deleteUser(userId: number): Promise<void> {
  await apiClient.delete(`/admin/users/${userId}`);
}

export async function toggleFreeMembership(userId: number): Promise<{ free_membership: boolean }> {
  const { data } = await apiClient.post(`/admin/users/${userId}/free-membership`);
  return data;
}
