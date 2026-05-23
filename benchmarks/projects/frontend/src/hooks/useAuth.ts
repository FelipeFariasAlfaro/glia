import { useState, useCallback, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../store';
import { setCredentials, clearAuth, setRefreshing } from '../store/authSlice';
import { loginApi, refreshTokenApi, logoutApi } from '../api/auth';
import { getToken, setToken, clearTokens, getStorageType } from '../utils/tokenStorage';

/**
 * useAuth hook manages authentication state, token refresh, and login/logout.
 * 
 * Token refresh logic: When the access token expires, this hook calls
 * refreshTokenApi. The refresh token is read from storage (localStorage
 * or sessionStorage depending on the "remember me" preference).
 * 
 * CRITICAL: The apiMiddleware also handles 401 responses by triggering
 * token refresh. The `isRefreshing` flag in authSlice prevents the
 * infinite refresh loop that occurred in the 2024-04 incident.
 * Without this flag, a 401 on the refresh endpoint itself would trigger
 * another refresh attempt, creating an infinite loop.
 * 
 * @see authSlice.ts - isRefreshing flag prevents infinite loops
 * @see apiMiddleware.ts - also triggers refresh on 401
 * @see tokenStorage.ts - storage strategy based on rememberMe
 * @see docs/incidents/2024-04-infinite-refresh.md - incident details
 */
interface LoginParams {
  email: string;
  password: string;
  rememberMe: boolean;
}

interface AuthResult {
  user: { id: string; name: string; email: string; role: string; permissions: string[] };
  accessToken: string;
  refreshToken: string;
}

export function useAuth() {
  const dispatch = useAppDispatch();
  const { isAuthenticated, isRefreshing, error } = useAppSelector((state) => state.auth);
  const [isLoading, setIsLoading] = useState(false);

  /** Login with credentials, stores tokens based on rememberMe preference */
  const login = useCallback(async (params: LoginParams): Promise<AuthResult> => {
    setIsLoading(true);
    try {
      const result = await loginApi(params);
      setToken('access', result.accessToken, params.rememberMe ? 'local' : 'session');
      setToken('refresh', result.refreshToken, params.rememberMe ? 'local' : 'session');
      return result;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Refresh the access token using the stored refresh token.
   * Sets isRefreshing flag to prevent concurrent refresh attempts
   * and the infinite loop documented in the 2024-04 incident.
   */
  const refresh = useCallback(async (): Promise<boolean> => {
    if (isRefreshing) return false; // Prevent infinite loop
    dispatch(setRefreshing(true));
    try {
      const refreshToken = getToken('refresh');
      if (!refreshToken) {
        dispatch(clearAuth());
        return false;
      }
      const result = await refreshTokenApi(refreshToken);
      const storageType = getStorageType();
      setToken('access', result.accessToken, storageType);
      dispatch(setCredentials({ ...result, rememberMe: storageType === 'local' }));
      return true;
    } catch {
      dispatch(clearAuth());
      clearTokens();
      return false;
    } finally {
      dispatch(setRefreshing(false));
    }
  }, [dispatch, isRefreshing]);

  /** Logout and clear all stored tokens */
  const logout = useCallback(async () => {
    try {
      await logoutApi();
    } finally {
      dispatch(clearAuth());
      clearTokens();
    }
  }, [dispatch]);

  return { login, logout, refresh, isAuthenticated, isLoading, isRefreshing, error };
}
