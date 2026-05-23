/**
 * tokenStorage manages token persistence across browser sessions.
 * 
 * STORAGE STRATEGY:
 * - "Remember Me" checked → tokens stored in localStorage (persists across sessions)
 * - "Remember Me" unchecked → tokens stored in sessionStorage (cleared on tab close)
 * 
 * PRIORITY BEHAVIOR:
 * getToken() checks localStorage FIRST, then sessionStorage.
 * This priority matters because:
 * 1. A user logs in with "remember me" → token in localStorage
 * 2. Same user opens new tab, logs in WITHOUT "remember me" → token in sessionStorage
 * 3. Now BOTH storages have tokens
 * 4. getToken() returns the localStorage token (older, possibly expired)
 * 
 * The apiMiddleware and Axios client both use getToken() and thus inherit
 * this priority behavior. If localStorage has an expired token but
 * sessionStorage has a fresh one, the expired token is used first.
 * 
 * @see apiMiddleware.ts - uses getToken() for auth headers
 * @see client.ts - uses getToken() in request interceptor
 * @see LoginForm.tsx - sets rememberMe preference
 */

type StorageType = 'local' | 'session';
type TokenType = 'access' | 'refresh';

const TOKEN_KEYS: Record<TokenType, string> = {
  access: 'app_access_token',
  refresh: 'app_refresh_token',
};

const STORAGE_TYPE_KEY = 'app_storage_type';

/**
 * Get a token from storage. Checks localStorage first, then sessionStorage.
 * This priority can cause issues if both storages contain tokens.
 */
export function getToken(type: TokenType): string | null {
  const key = TOKEN_KEYS[type];
  // Priority: localStorage first, then sessionStorage
  return localStorage.getItem(key) || sessionStorage.getItem(key);
}

/**
 * Store a token in the specified storage type.
 * Also records which storage type is being used for later reference.
 */
export function setToken(type: TokenType, value: string, storageType: StorageType): void {
  const key = TOKEN_KEYS[type];
  const storage = storageType === 'local' ? localStorage : sessionStorage;
  storage.setItem(key, value);
  localStorage.setItem(STORAGE_TYPE_KEY, storageType);
}

/** Get the current storage type preference */
export function getStorageType(): StorageType {
  return (localStorage.getItem(STORAGE_TYPE_KEY) as StorageType) || 'session';
}

/** Clear tokens from BOTH storage types to ensure complete logout */
export function clearTokens(): void {
  Object.values(TOKEN_KEYS).forEach((key) => {
    localStorage.removeItem(key);
    sessionStorage.removeItem(key);
  });
  localStorage.removeItem(STORAGE_TYPE_KEY);
}

/** Check if any token exists in either storage */
export function hasToken(type: TokenType): boolean {
  return getToken(type) !== null;
}

/**
 * Get token expiration time (decoded from JWT payload).
 * Returns null if token is invalid or not present.
 */
export function getTokenExpiry(type: TokenType): number | null {
  const token = getToken(type);
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

/** Check if a token is expired based on its JWT exp claim */
export function isTokenExpired(type: TokenType): boolean {
  const expiry = getTokenExpiry(type);
  if (!expiry) return true;
  return Date.now() >= expiry;
}
