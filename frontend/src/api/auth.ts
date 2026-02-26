import axios from 'axios';
import apiClient from './client';
import type { AuthUser } from '../types';

export async function getAuthMe(): Promise<AuthUser | null> {
  try {
    const response = await apiClient.get<AuthUser>('/auth/me');
    return response.data;
  } catch {
    return null;
  }
}

export async function updateSettings(settings: Record<string, unknown>): Promise<AuthUser> {
  const { data } = await apiClient.put<AuthUser>('/auth/settings', settings);
  return data;
}

// Direct calls to /auth/* (not /api/v2/auth/*)
const authDirect = axios.create({ baseURL: '/auth', withCredentials: true, headers: { 'Content-Type': 'application/json' } });

export async function registerWithPassword(email: string, name: string, password: string, recaptchaToken?: string): Promise<{ redirect: string }> {
  const { data } = await authDirect.post<{ redirect: string }>('/register', { email, name, password, recaptcha_token: recaptchaToken });
  return data;
}

export async function loginWithPassword(email: string, password: string, next?: string): Promise<{ redirect: string }> {
  const { data } = await authDirect.post<{ redirect: string }>('/login', { email, password, next });
  return data;
}

export async function resendVerification(): Promise<void> {
  await authDirect.post('/resend-verification');
}

export async function forgotPassword(email: string): Promise<void> {
  await authDirect.post('/forgot-password', { email });
}

export async function resetPassword(token: string, password: string): Promise<{ redirect: string }> {
  const { data } = await authDirect.post<{ redirect: string }>(`/reset-password/${token}`, { password });
  return data;
}
