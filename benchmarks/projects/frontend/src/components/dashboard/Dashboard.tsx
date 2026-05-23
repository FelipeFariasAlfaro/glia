import React, { useEffect } from 'react';
import { useAppSelector, useAppDispatch } from '../../store';
import { MetricsWidget } from './MetricsWidget';
import { fetchRecentOrders } from '../../store/ordersSlice';
import { selectUserPermissions } from '../../store/authSlice';
import { isFeatureEnabled } from '../../config/featureFlags';
import { ErrorBoundary } from '../shared/ErrorBoundary';

/**
 * Dashboard is the main landing page after login.
 * Displays real-time metrics, recent orders, and notification badges.
 * 
 * Feature flags control which widgets are visible. The 'realtime-metrics'
 * flag enables the MetricsWidget which uses WebSocket for live data.
 * If the WebSocket disconnects, MetricsWidget continues showing stale
 * data without any visual indicator — this is a known UX gap.
 * 
 * @see MetricsWidget - uses useWebSocket for real-time updates
 * @see featureFlags.ts - controls widget visibility
 */
interface DashboardProps {
  userId?: string;
}

export const Dashboard: React.FC<DashboardProps> = ({ userId }) => {
  const dispatch = useAppDispatch();
  const permissions = useAppSelector(selectUserPermissions);
  const recentOrders = useAppSelector((state) => state.orders.recentOrders);
  const unreadNotifications = useAppSelector((state) => state.notifications.unreadCount);
  const userName = useAppSelector((state) => state.auth.user?.name);

  useEffect(() => {
    dispatch(fetchRecentOrders({ limit: 10 }));
  }, [dispatch]);

  /** Check feature flags to determine which widgets to render */
  const showMetrics = isFeatureEnabled('realtime-metrics');
  const showAdvancedFilters = isFeatureEnabled('advanced-order-filters');

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Welcome back, {userName}</h1>
        {unreadNotifications > 0 && (
          <span className="notification-badge" aria-label={`${unreadNotifications} unread notifications`}>
            {unreadNotifications}
          </span>
        )}
      </header>

      {showMetrics && (
        <ErrorBoundary fallback={<div className="widget-error">Metrics unavailable</div>}>
          <MetricsWidget />
        </ErrorBoundary>
      )}

      <section className="recent-orders" aria-label="Recent orders">
        <h2>Recent Orders</h2>
        {recentOrders.length === 0 ? (
          <p className="empty-state">No recent orders</p>
        ) : (
          <ul className="order-list-compact">
            {recentOrders.slice(0, 5).map((order) => (
              <li key={order.id} className={`order-item status-${order.status}`}>
                <span className="order-id">#{order.id}</span>
                <span className="order-status">{order.status}</span>
                <span className="order-total">${order.total.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {permissions.includes('analytics:view') && (
        <section className="analytics-preview">
          <h2>Quick Analytics</h2>
          <p>Revenue and conversion data will appear here.</p>
        </section>
      )}
    </div>
  );
};
