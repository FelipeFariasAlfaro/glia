import { lazy } from 'react';
import { isFeatureEnabled } from './featureFlags';

/**
 * Route definitions with lazy loading for code splitting.
 * 
 * FEATURE FLAG DEPENDENCY: Some routes are only available when their
 * corresponding feature flag is enabled. The 'advanced-order-filters'
 * flag controls whether the /orders/advanced route is registered.
 * 
 * CRITICAL: Feature flags affect BOTH route availability AND API endpoints.
 * If a flag is enabled for routes but the corresponding API version isn't
 * deployed, users can navigate to the page but all API calls will 404.
 * 
 * Example: 'advanced-order-filters' flag:
 * - Enables /orders/advanced route (this file)
 * - Switches API to /v2/orders (orders.ts, ordersSlice.ts)
 * - If v2 API not deployed → route works but data fetching fails with 404
 * 
 * @see featureFlags.ts - flag definitions
 * @see orders.ts - API version selection based on flags
 * @see ordersSlice.ts - also checks flags for API version
 */

/** Lazy-loaded page components */
const LoginPage = lazy(() => import('../components/auth/LoginForm'));
const DashboardPage = lazy(() => import('../components/dashboard/Dashboard'));
const OrderListPage = lazy(() => import('../components/orders/OrderList'));
const OrderDetailPage = lazy(() => import('../components/orders/OrderDetail'));

/** Route configuration type */
interface RouteConfig {
  path: string;
  component: React.LazyExoticComponent<any>;
  requiresAuth: boolean;
  requiredPermission?: string;
  featureFlag?: string;
  children?: RouteConfig[];
}

/**
 * Build route configuration based on current feature flags.
 * Routes gated by disabled flags are excluded from the config.
 */
export function getRoutes(): RouteConfig[] {
  const routes: RouteConfig[] = [
    {
      path: '/login',
      component: LoginPage,
      requiresAuth: false,
    },
    {
      path: '/dashboard',
      component: DashboardPage,
      requiresAuth: true,
    },
    {
      path: '/orders',
      component: OrderListPage,
      requiresAuth: true,
      requiredPermission: 'orders:view',
    },
    {
      path: '/orders/:id',
      component: OrderDetailPage,
      requiresAuth: true,
      requiredPermission: 'orders:view',
    },
  ];

  /**
   * Conditionally add advanced orders route based on feature flag.
   * This route uses the v2 API — if v2 isn't deployed, the page loads
   * but all data fetching fails with 404 errors.
   */
  if (isFeatureEnabled('advanced-order-filters')) {
    routes.push({
      path: '/orders/advanced',
      component: OrderListPage,
      requiresAuth: true,
      requiredPermission: 'orders:view',
      featureFlag: 'advanced-order-filters',
    });
  }

  /** Real-time metrics route — only available with realtime-metrics flag */
  if (isFeatureEnabled('realtime-metrics')) {
    routes.push({
      path: '/metrics',
      component: DashboardPage,
      requiresAuth: true,
      requiredPermission: 'analytics:view',
      featureFlag: 'realtime-metrics',
    });
  }

  return routes;
}

/** Get the default redirect path after login */
export function getDefaultRoute(): string {
  return '/dashboard';
}

/** Check if a path requires authentication */
export function isProtectedPath(path: string): boolean {
  const routes = getRoutes();
  const route = routes.find((r) => r.path === path);
  return route?.requiresAuth ?? true;
}
