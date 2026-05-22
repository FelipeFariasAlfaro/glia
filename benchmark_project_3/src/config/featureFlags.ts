/**
 * Feature flag system for controlling feature rollout and A/B testing.
 * 
 * CRITICAL COUPLING: Feature flags affect MULTIPLE parts of the system:
 * 1. Route availability (routes.ts) — which pages users can navigate to
 * 2. API endpoint selection (orders.ts, ordersSlice.ts) — which API version is called
 * 3. UI component visibility (Dashboard.tsx, OrderList.tsx) — which widgets render
 * 
 * Changing a flag without updating ALL affected areas causes inconsistencies:
 * - Enable 'advanced-order-filters' without v2 API deployed → 404 errors
 * - Enable 'realtime-metrics' without WebSocket server → silent failures
 * - Disable a flag that a route depends on → route disappears mid-session
 * 
 * @see routes.ts - route availability depends on flags
 * @see orders.ts - API version depends on 'advanced-order-filters' flag
 * @see ordersSlice.ts - also checks 'advanced-order-filters' for API version
 * @see Dashboard.tsx - widget visibility depends on flags
 * @see OrderList.tsx - advanced filters UI depends on flags
 */

interface FeatureFlag {
  name: string;
  enabled: boolean;
  description: string;
  /** Which parts of the system this flag affects */
  affects: string[];
  /** Minimum API version required when this flag is enabled */
  requiredApiVersion?: string;
}

/**
 * Feature flag definitions. In production, these would be fetched
 * from a remote config service (LaunchDarkly, Split.io, etc.).
 */
const FLAGS: Record<string, FeatureFlag> = {
  'advanced-order-filters': {
    name: 'advanced-order-filters',
    enabled: false,
    description: 'Enable advanced filtering (date range, amount) for orders',
    affects: ['routes.ts', 'orders.ts', 'ordersSlice.ts', 'OrderList.tsx'],
    requiredApiVersion: 'v2',
  },
  'realtime-metrics': {
    name: 'realtime-metrics',
    enabled: true,
    description: 'Enable real-time metrics dashboard widget via WebSocket',
    affects: ['routes.ts', 'Dashboard.tsx', 'MetricsWidget.tsx'],
  },
  'optimistic-updates': {
    name: 'optimistic-updates',
    enabled: true,
    description: 'Enable optimistic UI updates for order actions',
    affects: ['OrderActions.tsx', 'useOptimisticUpdate.ts'],
  },
  'websocket-reconnect': {
    name: 'websocket-reconnect',
    enabled: true,
    description: 'Enable automatic WebSocket reconnection on disconnect',
    affects: ['useWebSocket.ts', 'MetricsWidget.tsx'],
  },
};

/** Runtime overrides from environment or remote config */
let runtimeOverrides: Record<string, boolean> = {};

/**
 * Check if a feature flag is enabled.
 * Checks runtime overrides first, then falls back to static config.
 */
export function isFeatureEnabled(flagName: string): boolean {
  if (flagName in runtimeOverrides) {
    return runtimeOverrides[flagName];
  }
  return FLAGS[flagName]?.enabled ?? false;
}

/** Set a runtime override for a feature flag (used in testing) */
export function setFeatureOverride(flagName: string, enabled: boolean): void {
  runtimeOverrides[flagName] = enabled;
}

/** Clear all runtime overrides */
export function clearFeatureOverrides(): void {
  runtimeOverrides = {};
}

/** Get all flag definitions (for admin panel display) */
export function getAllFlags(): FeatureFlag[] {
  return Object.values(FLAGS);
}

/** Get the required API version for a flag, if any */
export function getRequiredApiVersion(flagName: string): string | undefined {
  return FLAGS[flagName]?.requiredApiVersion;
}

/** Get all systems affected by a specific flag */
export function getAffectedSystems(flagName: string): string[] {
  return FLAGS[flagName]?.affects ?? [];
}
