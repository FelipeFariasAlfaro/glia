import apiClient from './client';

/**
 * Authentication API calls. Handles login, token refresh, and logout.
 * 
 * The refresh endpoint is critical for the token refresh flow.
 * Both apiMiddleware and the Axios client interceptor call refreshTokenApi
 * when they encounter a 401 response.
 * 
 * IMPORTANT: The refresh endpoint itself can return 401 if the refresh
 * token is expired. This is what caused the 2024-04 infinite refresh loop.
 * The fix was adding the isRefreshing flag in authSlice to prevent
 * recursive refresh attempts.
 * 
 * @see apiMiddleware.ts - calls refreshTokenApi on 401 responses
 * @see client.ts - also calls refreshTokenApi in response interceptor
 * @see authSlice.ts - isRefreshing flag prevents infinite loops
 * @see docs/incidents/2024-04-infinite-refresh.md - incident details
 */

interface LoginRequest {
  email: string;
  password: string;
  rememberMe: boolean;
}

interface AuthResponse {
  user: {
    id: string;
    name: string;
    email: string;
    role: string;
    permissions: string[];
  };
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

interface RefreshResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

/**
 * Login with email and password.
 * Returns user info, access token, and refresh token.
 * The rememberMe flag is sent to the server for session tracking.
 */
export async function loginApi(params: LoginRequest): Promise<AuthResponse> {
  const response = await apiClient.post('/auth/login', {
    email: params.email,
    password: params.password,
    rememberMe: params.rememberMe,
  });
  return response.data;
}

/**
 * Refresh the access token using a valid refresh token.
 * 
 * WARNING: This endpoint can return 401 if the refresh token is expired.
 * Callers MUST check the isRefreshing flag before calling to prevent
 * infinite loops (401 → refresh → 401 → refresh → ...).
 */
export async function refreshTokenApi(refreshToken: string): Promise<RefreshResponse> {
  // Use a separate axios instance to avoid interceptor loops
  const response = await apiClient.post('/auth/refresh', { refreshToken }, {
    headers: { 'X-Skip-Interceptor': 'true' },
  });
  return response.data;
}

/** Logout and invalidate the refresh token server-side */
export async function logoutApi(): Promise<void> {
  await apiClient.post('/auth/logout');
}

/** Request password reset email */
export async function requestPasswordReset(email: string): Promise<void> {
  await apiClient.post('/auth/forgot-password', { email });
}

/** Verify the current access token is still valid */
export async function verifyToken(): Promise<{ valid: boolean; expiresIn: number }> {
  const response = await apiClient.get('/auth/verify');
  return response.data;
}
