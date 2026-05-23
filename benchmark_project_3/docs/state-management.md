# State Management Architecture

## Overview

This application uses Redux Toolkit for global state management. The decision to use Redux over React Context is documented in [ADR-001](./decisions/adr-001-redux-over-context.md).

## Store Structure

```
store/
├── authSlice.ts          - Authentication state (user, tokens, permissions)
├── ordersSlice.ts        - Orders state (list, filters, pagination, cache)
├── notificationsSlice.ts - UI notifications (toasts, badge counts)
└── middleware/
    └── apiMiddleware.ts  - API call interception, retry, auth headers
```

## Key Design Decisions

### Token Refresh Flow

The token refresh mechanism exists in TWO places:
1. **apiMiddleware** — intercepts 401 responses from Redux-dispatched API calls
2. **Axios client interceptor** — handles 401 for direct API calls from hooks

Both use the `isRefreshing` flag (authSlice) to prevent infinite loops. This flag was added after the [2024-04 infinite refresh incident](./incidents/2024-04-infinite-refresh.md).

### Optimistic Updates

Order actions (cancel, refund, resend) use optimistic updates via `useOptimisticUpdate` hook:
1. Dispatch immediate state change to `ordersSlice`
2. Call API in background
3. On failure, dispatch rollback action

**Known fragility**: The rollback dispatches actions assuming a specific slice shape. If `ordersSlice` structure changes, rollbacks silently fail.

### Permission Model

Permissions are flat strings (`resource:action` format) stored in `authSlice.user.permissions`. Two components check permissions independently:
- `ProtectedRoute` — route-level access control
- `OrderActions` — action-level button visibility

Both must be updated if the permission model changes.

### WebSocket & Cache Staleness

The `useWebSocket` hook manages real-time connections. Known issue: on disconnect, the `ordersSlice` cache is NOT cleared. This means users see stale data until they manually refresh. See [2024-07 stale cache incident](./incidents/2024-07-stale-cache.md).

### Feature Flags

Feature flags control both UI visibility AND API endpoint selection. The `advanced-order-filters` flag:
- Shows/hides advanced filter UI in OrderList
- Switches API calls from v1 to v2 endpoints
- Adds/removes routes in route config

Enabling a flag without the corresponding backend deployment causes 404 errors.

## Error Handling

- **Render errors**: Caught by `ErrorBoundary`, reported to Sentry
- **API errors**: Handled by Axios interceptor and apiMiddleware
- **WebSocket errors**: NOT caught by ErrorBoundary (async), logged to console only
- **Optimistic rollback failures**: Silent — no error surfaced to user
