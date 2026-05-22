import React, { useMemo } from 'react';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useAppSelector } from '../../store';

/**
 * MetricsWidget displays real-time business metrics using WebSocket data.
 * 
 * KNOWN ISSUE: When the WebSocket disconnects, this component continues
 * displaying the last received data without any visual indicator that
 * the data is stale. Users may make decisions based on outdated metrics.
 * 
 * The useWebSocket hook handles reconnection attempts, but during the
 * disconnection window, there is no staleness indicator rendered here.
 * This was documented in the 2024-07 stale cache incident post-mortem.
 * 
 * @see useWebSocket.ts - manages connection lifecycle
 * @see docs/incidents/2024-07-stale-cache.md - related incident
 */
interface MetricData {
  ordersToday: number;
  revenue: number;
  avgProcessingTime: number;
  activeUsers: number;
  conversionRate: number;
}

interface MetricsWidgetProps {
  refreshInterval?: number;
}

export const MetricsWidget: React.FC<MetricsWidgetProps> = ({ refreshInterval = 5000 }) => {
  /**
   * useWebSocket subscribes to the 'metrics' channel.
   * If the connection drops, `isConnected` becomes false but the component
   * does NOT show any visual staleness indicator — this is the known gap.
   */
  const { data, isConnected, lastMessageAt } = useWebSocket<MetricData>('metrics', {
    reconnectAttempts: 5,
    reconnectInterval: 3000,
  });

  const metrics = data ?? {
    ordersToday: 0,
    revenue: 0,
    avgProcessingTime: 0,
    activeUsers: 0,
    conversionRate: 0,
  };

  /** Format currency values for display */
  const formattedRevenue = useMemo(
    () => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(metrics.revenue),
    [metrics.revenue]
  );

  return (
    <div className="metrics-widget" role="region" aria-label="Real-time metrics">
      <div className="metrics-grid">
        <div className="metric-card">
          <span className="metric-label">Orders Today</span>
          <span className="metric-value">{metrics.ordersToday}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Revenue</span>
          <span className="metric-value">{formattedRevenue}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Avg Processing</span>
          <span className="metric-value">{metrics.avgProcessingTime}ms</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Active Users</span>
          <span className="metric-value">{metrics.activeUsers}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Conversion Rate</span>
          <span className="metric-value">{(metrics.conversionRate * 100).toFixed(1)}%</span>
        </div>
      </div>
      {/* NOTE: No visual indicator when isConnected is false — stale data shown silently */}
    </div>
  );
};
