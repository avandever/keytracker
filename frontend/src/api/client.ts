import axios from 'axios';
import type { InternalAxiosRequestConfig } from 'axios';

let _testUserId: number | null = null;

export function setTestUserIdForApi(id: number | null) {
  _testUserId = id;
}

// ETag caches for GET requests — keyed by URL (relative path + query string).
// Stores the last ETag and response data received for each URL so that
// subsequent requests can send If-None-Match and skip work when data is unchanged.
const _etagCache = new Map<string, string>();
const _responseCache = new Map<string, unknown>();

function getCacheKey(config: InternalAxiosRequestConfig): string {
  const params = config.params
    ? '?' + new URLSearchParams(config.params).toString()
    : '';
  return (config.url || '') + params;
}

const apiClient = axios.create({
  baseURL: '/api/v2',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
  // Treat 304 as a successful response so the interceptor can handle it
  validateStatus: (status) => (status >= 200 && status < 300) || status === 304,
});

apiClient.interceptors.request.use((config) => {
  if (_testUserId != null) {
    config.headers['X-Test-User-Id'] = String(_testUserId);
  }
  // Attach a cached ETag as If-None-Match for GET requests
  if (config.method === 'get') {
    const key = getCacheKey(config);
    const etag = _etagCache.get(key);
    if (etag && _responseCache.has(key)) {
      config.headers['If-None-Match'] = etag;
    }
  }
  return config;
});

apiClient.interceptors.response.use((response) => {
  if (response.status === 304) {
    // Server says nothing changed — return cached data transparently
    const key = getCacheKey(response.config);
    const cached = _responseCache.get(key);
    if (cached !== undefined) {
      return { ...response, data: cached, status: 200 };
    }
    // No cache entry (shouldn't happen) — fall through with empty body
  } else if (response.status === 200 && response.config.method === 'get') {
    const etag = response.headers['etag'];
    if (etag) {
      const key = getCacheKey(response.config);
      _etagCache.set(key, etag);
      _responseCache.set(key, response.data);
    }
  }
  return response;
});

export default apiClient;
