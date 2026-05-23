# Incident Post-Mortem: Stale Order Data After WebSocket Disconnect

**Date**: July 8, 2024  
**Severity**: P2 — Data accuracy issue, no data loss  
**Duration**: 3 hours (until identified), ongoing for affected users until page refresh  
**Affected Users**: Users on unstable network connections

## Summary

Users reported seeing outdated order statuses in the order list and dashboard. Orders that had been cancelled or shipped still showed as "pending" or "processing". The root cause was that WebSocket disconnections did not trigger a cache clear in `ordersSlice`, leaving stale data displayed until the user manually refreshed the page.

## Timeline

- **09:15 UTC** — Customer support reports: "User sees order as pending but it was shipped 2 hours ago"
- **09:30 UTC** — Multiple similar reports from users on mobile/unstable connections
- **10:45 UTC** — Engineering identifies that affected users had WebSocket disconnections
- **11:20 UTC** — Root cause confirmed: `useWebSocket` disconnect handler doesn't clear ordersSlice cache
- **12:15 UTC** — Temporary fix: added manual refresh button with "Data may be stale" warning

## Root Cause

The `useWebSocket` hook handles disconnections by attempting reconnection, but it does NOT dispatch any action to clear or invalidate the `ordersSlice` cache. The flow:

1. User loads order list → data cached in `ordersSlice.items`
2. WebSocket connects → real-time updates flow in
3. WebSocket disconnects (network issue) → `isConnected` becomes `false`
4. Orders are updated server-side (cancelled, shipped, etc.)
5. User still sees the cached data from step 1
6. No visual indicator that data is stale (especially in MetricsWidget)

The `MetricsWidget` component also suffers from this — it shows the last received metrics without any staleness indicator when the WebSocket is disconnected.

## Impact

- Users made decisions based on stale order data
- Support team received complaints about "incorrect" order statuses
- MetricsWidget showed outdated revenue/order counts to managers

## Fix (Temporary)

- Added a "Refresh" button that dispatches `clearOrdersCache()` and re-fetches
- Added a small "Last updated: X minutes ago" indicator

## Fix (Planned but not yet implemented)

- `useWebSocket` should dispatch `clearOrdersCache()` on disconnect
- MetricsWidget should show a visual "stale data" indicator when `isConnected` is false
- Implement automatic re-fetch when WebSocket reconnects
- Add a `lastFetchedAt` staleness check that shows warnings after N minutes

## Related Files

- `src/hooks/useWebSocket.ts` — disconnect handler doesn't clear cache
- `src/store/ordersSlice.ts` — has `clearOrdersCache` action but it's never called on disconnect
- `src/components/dashboard/MetricsWidget.tsx` — no staleness indicator
- `src/components/orders/OrderList.tsx` — shows cached data without warning

## Lessons Learned

1. Real-time data systems need explicit staleness handling for disconnection scenarios
2. The `isConnected` state from useWebSocket was available but not used by consumers to show warnings
3. Cache invalidation on connection state changes should be a default behavior, not opt-in
