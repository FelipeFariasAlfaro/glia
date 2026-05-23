import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from './index';

/**
 * authSlice manages authentication state including tokens, user info,
 * permissions, and the critical isRefreshing flag.
 * 
 * The `isRefreshing` flag was added after the 2024-04 infinite refresh
 * loop incident. Without it, the apiMiddleware would intercept a 401
 * response, call the refresh endpoint, get another 401 (expired refresh
 * token), and loop infinitely. The flag prevents concurrent refresh attempts.
 * 
 * Permissions are stored as a flat string array (e.g., ['orders:cancel',
 * 'orders:refund']). Both ProtectedRoute and OrderActions read from this
 * array independently — if the permission model changes, both need updating.
 * 
 * @see apiMiddleware.ts - checks isRefreshing before attempting refresh
 * @see ProtectedRoute.tsx - reads permissions for route-level access
 * @see OrderActions.tsx - reads permissions for action-level access
 * @see docs/incidents/2024-04-infinite-refresh.md - incident that led to isRefreshing
 */
interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  permissions: string[];
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  /** Prevents infinite refresh loop — set true during token refresh */
  isRefreshing: boolean;
  rememberMe: boolean;
  error: string | null;
}

const initialState: AuthState = {
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isRefreshing: false,
  rememberMe: false,
  error: null,
};

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setCredentials(state, action: PayloadAction<{
      user: User;
      accessToken: string;
      refreshToken: string;
      rememberMe: boolean;
    }>) {
      state.user = action.payload.user;
      state.accessToken = action.payload.accessToken;
      state.refreshToken = action.payload.refreshToken;
      state.isAuthenticated = true;
      state.rememberMe = action.payload.rememberMe;
      state.error = null;
    },
    clearAuth(state) {
      Object.assign(state, initialState);
    },
    /**
     * setRefreshing controls the infinite-loop prevention flag.
     * apiMiddleware checks this before attempting a token refresh.
     */
    setRefreshing(state, action: PayloadAction<boolean>) {
      state.isRefreshing = action.payload;
    },
    setLoginError(state, action: PayloadAction<string>) {
      state.error = action.payload;
    },
    updatePermissions(state, action: PayloadAction<string[]>) {
      if (state.user) {
        state.user.permissions = action.payload;
      }
    },
  },
});

export const { setCredentials, clearAuth, setRefreshing, setLoginError, updatePermissions } = authSlice.actions;

/** Selectors */
export const selectIsAuthenticated = (state: RootState) => state.auth.isAuthenticated;
export const selectUserPermissions = (state: RootState) => state.auth.user?.permissions ?? [];
export const selectIsRefreshing = (state: RootState) => state.auth.isRefreshing;
export const selectCurrentUser = (state: RootState) => state.auth.user;

export default authSlice.reducer;
