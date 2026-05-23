# Incident Post-Mortem: Infinite Token Refresh Loop

**Date**: April 12, 2024  
**Severity**: P1 — Multiple users affected, browser tabs crashing  
**Duration**: 45 minutes  
**Affected Users**: ~200 concurrent users

## Summary

A production incident caused browser tabs to crash due to an infinite loop in the token refresh mechanism. The `apiMiddleware` would intercept a 401 response, attempt to refresh the token, receive another 401 (because the refresh token was also expired), and retry indefinitely.

## Timeline

- **14:22 UTC** — Refresh token TTL reduced from 7 days to 1 day (backend config change)
- **14:45 UTC** — First reports of browser tabs becoming unresponsive
- **14:52 UTC** — Engineering identified infinite network requests in browser DevTools
- **15:03 UTC** — Root cause identified in `apiMiddleware.ts`
- **15:07 UTC** — Hotfix deployed: added `isRefreshing` flag check

## Root Cause

The `apiMiddleware` intercepted 401 responses and called `refreshTokenApi()`. However, if the refresh token itself was expired, the refresh endpoint also returned 401. The middleware would then intercept THIS 401 and attempt another refresh, creating an infinite loop:

```
API call → 401 → refresh attempt → 401 → refresh attempt → 401 → ...
```

The Axios client (`client.ts`) already had protection against this via its own `isRefreshing` flag, but the Redux middleware did not. API calls routed through Redux (most of the app) were vulnerable.

## Fix

Added `isRefreshing` flag to `authSlice`:
1. Before attempting refresh, check if `isRefreshing` is already `true`
2. If true, queue the request instead of triggering another refresh
3. If false, set flag to `true`, attempt refresh, then set back to `false`
4. If refresh fails, clear auth state and redirect to login

## Prevention

- The `isRefreshing` flag in authSlice is now the single source of truth for refresh state
- Both `apiMiddleware` and `useAuth` hook check this flag before refreshing
- Added monitoring alert for >5 refresh attempts per user per minute
- Added integration test covering expired refresh token scenario

## Lessons Learned

1. The Axios client had this protection but the middleware didn't — inconsistent error handling across layers
2. Backend config changes (TTL reduction) can trigger frontend bugs that weren't previously reachable
3. Need circuit-breaker pattern for auth refresh, not just a boolean flag

## Related Files

- `src/store/middleware/apiMiddleware.ts` — where the loop occurred
- `src/store/authSlice.ts` — `isRefreshing` flag added here
- `src/hooks/useAuth.ts` — also checks `isRefreshing` before refresh
- `src/api/client.ts` — already had protection (separate `isRefreshing` variable)
- `src/api/auth.ts` — `refreshTokenApi` endpoint that returned 401
