import { Middleware, MiddlewareAPI, Dispatch, AnyAction } from '@reduxjs/toolkit';
import { getToken } from '../../utils/tokenStorage';
import { setRefreshing, clearAuth, selectIsRefreshing } from '../authSlice';
import { refreshTokenApi } from '../../api/auth';
import { addNotification } from '../notificationsSlice';

/**
 * apiMiddleware intercepts Redux actions that represent API calls.
 * Handles authentication headers, token refresh on 401, and retry logic.
 * 
 * TOKEN REFRESH FLOW:
 * 1. API call returns 401 (access token expired)
 * 2. Middleware checks authSlice.isRefreshing flag
 * 3. If NOT refreshing: sets flag, calls refresh endpoint, retries original request
 * 4. If IS refreshing: queues the request for retry after refresh completes
 * 
 * INFINITE LOOP PREVENTION (2024-04 incident fix):
 * The isRefreshing flag in authSlice prevents the infinite loop where:
 * - 401 response → trigger refresh → refresh also gets 401 → trigger refresh → ...
 * Without this flag, if the refresh token is also expired, the middleware
 * would endlessly retry the refresh, causing browser tab crashes.
 * 
 * TOKEN STORAGE PRIORITY:
 * The middleware reads tokens using getToken() which checks localStorage first,
 * then sessionStorage. This priority matters because if a user logged in with
 * "remember me" (localStorage) and later without (sessionStorage), both may
 * contain tokens. The middleware always uses the localStorage token first.
 * 
 * @see authSlice.ts - isRefreshing flag source
 * @see tokenStorage.ts - getToken priority (localStorage > sessionStorage)
 * @see useAuth.ts - also handles refresh (hook-level)
 * @see docs/incidents/2024-04-infinite-refresh.md - incident details
 */

/** Actions that represent API calls follow this pattern */
interface ApiAction extends AnyAction {
  meta?: {
    api?: boolean;
    endpoint?: string;
    method?: string;
    body?: any;
    retryCount?: number;
    maxRetries?: number;
  };
}

const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 1000;

/** Queue for requests waiting on token refresh */
let refreshQueue: Array<{ action: ApiAction; resolve: Function }> = [];

export const apiMiddleware: Middleware = (store: MiddlewareAPI) => (next: Dispatch) => async (action: ApiAction) => {
  // Only intercept actions marked as API calls
  if (!action.meta?.api) {
    return next(action);
  }

  const { endpoint, method = 'GET', body, retryCount = 0, maxRetries = MAX_RETRIES } = action.meta;
  const state = store.getState();

  /** Attach auth token from storage — localStorage takes priority */
  const accessToken = getToken('access');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  };

  try {
    const response = await fetch(endpoint!, { method, headers, body: body ? JSON.stringify(body) : undefined });

    if (response.status === 401) {
      const isRefreshing = selectIsRefreshing(state);

      /**
       * CRITICAL: Check isRefreshing to prevent infinite loop.
       * If already refreshing, queue this request instead of triggering another refresh.
       */
      if (isRefreshing) {
        return new Promise((resolve) => { refreshQueue.push({ action, resolve }); });
      }

      store.dispatch(setRefreshing(true));
      try {
        const refreshToken = getToken('refresh');
        if (!refreshToken) throw new Error('No refresh token');
        const result = await refreshTokenApi(refreshToken);
        // Retry queued requests
        refreshQueue.forEach(({ action: queuedAction, resolve }) => {
          resolve(store.dispatch(queuedAction));
        });
        refreshQueue = [];
        // Retry original request
        return store.dispatch({ ...action, meta: { ...action.meta, retryCount: retryCount + 1 } });
      } catch {
        store.dispatch(clearAuth());
        store.dispatch(addNotification({ type: 'error', message: 'Session expired. Please log in again.' }));
        refreshQueue = [];
      } finally {
        store.dispatch(setRefreshing(false));
      }
    }

    if (!response.ok && retryCount < maxRetries) {
      await new Promise((r) => setTimeout(r, RETRY_DELAY_MS * (retryCount + 1)));
      return store.dispatch({ ...action, meta: { ...action.meta, retryCount: retryCount + 1 } });
    }

    return response.json();
  } catch (error: any) {
    if (retryCount < maxRetries) {
      await new Promise((r) => setTimeout(r, RETRY_DELAY_MS * (retryCount + 1)));
      return store.dispatch({ ...action, meta: { ...action.meta, retryCount: retryCount + 1 } });
    }
    store.dispatch(addNotification({ type: 'error', message: `Request failed: ${error.message}` }));
    throw error;
  }
};
