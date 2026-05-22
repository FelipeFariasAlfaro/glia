import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { getToken, setToken, clearTokens, getStorageType } from '../utils/tokenStorage';
import { refreshTokenApi } from './auth';
import { reportError } from '../utils/errorReporting';

/**
 * Axios HTTP client with request/response interceptors.
 * 
 * REQUEST INTERCEPTOR: Attaches the access token from storage to every request.
 * Uses getToken('access') which checks localStorage first, then sessionStorage.
 * 
 * RESPONSE INTERCEPTOR: Handles 401 errors by attempting token refresh.
 * This is a SECONDARY refresh mechanism — the primary one is in apiMiddleware.
 * Both exist because some API calls go through Redux (apiMiddleware handles)
 * and some are called directly from hooks (this interceptor handles).
 * 
 * IMPORTANT: This interceptor has its own isRefreshing flag to prevent
 * infinite loops, separate from the authSlice.isRefreshing flag.
 * The 2024-04 incident was caused by the apiMiddleware not having this
 * protection — this client already had it but middleware didn't.
 * 
 * @see apiMiddleware.ts - primary refresh mechanism for Redux-based calls
 * @see tokenStorage.ts - token retrieval with storage priority
 * @see docs/incidents/2024-04-infinite-refresh.md - infinite loop incident
 */

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:3001/api';

let isRefreshing = false;
let failedQueue: Array<{ resolve: Function; reject: Function }> = [];

/** Process queued requests after token refresh */
function processQueue(error: any, token: string | null = null): void {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve(token);
  });
  failedQueue = [];
}

/** Create and configure the Axios instance */
const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

/**
 * Request interceptor: attach access token to Authorization header.
 * Token is read from storage — localStorage has priority over sessionStorage.
 */
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getToken('access');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

/**
 * Response interceptor: handle 401 by refreshing token.
 * Queues concurrent requests during refresh to avoid multiple refresh calls.
 */
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`;
          }
          return apiClient(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = getToken('refresh');
        if (!refreshToken) throw new Error('No refresh token available');
        const result = await refreshTokenApi(refreshToken);
        const storageType = getStorageType();
        setToken('access', result.accessToken, storageType);
        processQueue(null, result.accessToken);
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${result.accessToken}`;
        }
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        clearTokens();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    /** Report non-401 errors to Sentry */
    if (error.response?.status && error.response.status >= 500) {
      reportError(new Error(`API Error ${error.response.status}`), {
        url: originalRequest?.url,
        method: originalRequest?.method,
        status: error.response.status,
      });
    }

    return Promise.reject(error);
  }
);

export default apiClient;
