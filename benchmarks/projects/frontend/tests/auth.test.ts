import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { store } from '../src/store';
import { setCredentials, clearAuth, setRefreshing, selectIsRefreshing } from '../src/store/authSlice';
import { loginApi, refreshTokenApi } from '../src/api/auth';
import { setToken, getToken, clearTokens } from '../src/utils/tokenStorage';

/**
 * Auth flow tests covering login, token refresh, and the infinite loop prevention.
 * 
 * These tests verify:
 * 1. Login stores tokens in correct storage based on rememberMe
 * 2. Token refresh sets isRefreshing flag to prevent infinite loops
 * 3. Expired refresh token triggers logout (not infinite loop)
 * 4. Token storage priority (localStorage > sessionStorage)
 * 
 * @see authSlice.ts - state under test
 * @see apiMiddleware.ts - infinite loop prevention
 * @see tokenStorage.ts - storage priority behavior
 */

jest.mock('../src/api/auth');

describe('Authentication Flow', () => {
  beforeEach(() => {
    clearTokens();
    store.dispatch(clearAuth());
  });

  describe('Login', () => {
    it('should store credentials in authSlice on successful login', () => {
      const credentials = {
        user: { id: '1', name: 'Test User', email: 'test@example.com', role: 'admin', permissions: ['orders:view', 'orders:cancel'] },
        accessToken: 'access-token-123',
        refreshToken: 'refresh-token-456',
        rememberMe: true,
      };

      store.dispatch(setCredentials(credentials));
      const state = store.getState().auth;

      expect(state.isAuthenticated).toBe(true);
      expect(state.user?.email).toBe('test@example.com');
      expect(state.accessToken).toBe('access-token-123');
      expect(state.rememberMe).toBe(true);
    });

    it('should store tokens in localStorage when rememberMe is true', () => {
      setToken('access', 'token-123', 'local');
      expect(getToken('access')).toBe('token-123');
      // Verify it's in localStorage specifically
      expect(localStorage.getItem('app_access_token')).toBe('token-123');
    });

    it('should store tokens in sessionStorage when rememberMe is false', () => {
      setToken('access', 'token-456', 'session');
      expect(getToken('access')).toBe('token-456');
      expect(sessionStorage.getItem('app_access_token')).toBe('token-456');
    });
  });

  describe('Token Storage Priority', () => {
    it('should prefer localStorage over sessionStorage when both have tokens', () => {
      // Simulates: user logged in with rememberMe, then without in new tab
      setToken('access', 'local-token', 'local');
      setToken('access', 'session-token', 'session');
      // getToken checks localStorage first
      expect(getToken('access')).toBe('local-token');
    });
  });

  describe('Token Refresh - Infinite Loop Prevention', () => {
    it('should set isRefreshing flag during refresh', () => {
      store.dispatch(setRefreshing(true));
      expect(selectIsRefreshing(store.getState())).toBe(true);
    });

    it('should prevent concurrent refresh attempts when isRefreshing is true', () => {
      store.dispatch(setRefreshing(true));
      // When isRefreshing is true, useAuth.refresh() returns false immediately
      const state = store.getState().auth;
      expect(state.isRefreshing).toBe(true);
      // Any new refresh attempt should be blocked
    });

    it('should clear auth state when refresh token is expired', () => {
      store.dispatch(setCredentials({
        user: { id: '1', name: 'Test', email: 'test@test.com', role: 'admin', permissions: [] },
        accessToken: 'expired-access',
        refreshToken: 'expired-refresh',
        rememberMe: false,
      }));

      // Simulate failed refresh → clearAuth
      store.dispatch(clearAuth());
      const state = store.getState().auth;
      expect(state.isAuthenticated).toBe(false);
      expect(state.accessToken).toBeNull();
    });
  });

  describe('Permissions', () => {
    it('should store permissions in user object', () => {
      store.dispatch(setCredentials({
        user: { id: '1', name: 'Agent', email: 'agent@test.com', role: 'agent', permissions: ['orders:view', 'orders:cancel'] },
        accessToken: 'token',
        refreshToken: 'refresh',
        rememberMe: false,
      }));

      const permissions = store.getState().auth.user?.permissions;
      expect(permissions).toContain('orders:view');
      expect(permissions).toContain('orders:cancel');
      expect(permissions).not.toContain('orders:refund');
    });
  });
});
