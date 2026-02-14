import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api/v2',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

export default apiClient;
