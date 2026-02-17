import axios from 'axios';

let _testUserId: number | null = null;

export function setTestUserIdForApi(id: number | null) {
  _testUserId = id;
}

const apiClient = axios.create({
  baseURL: '/api/v2',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use((config) => {
  if (_testUserId != null) {
    config.headers['X-Test-User-Id'] = String(_testUserId);
  }
  return config;
});

export default apiClient;
