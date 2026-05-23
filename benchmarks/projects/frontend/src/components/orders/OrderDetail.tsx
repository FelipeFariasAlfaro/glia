import React, { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useAppSelector, useAppDispatch } from '../../store';
import { fetchOrderById } from '../../store/ordersSlice';
import { OrderActions } from './OrderActions';
import { ErrorBoundary } from '../shared/ErrorBoundary';

/**
 * OrderDetail displays full order information with a status timeline.
 * Fetches order data by ID from the Redux store or API.
 * 
 * Includes OrderActions component for performing operations on the order.
 * Both this component and OrderActions read from ordersSlice, but
 * OrderActions also performs its own permission checks independently
 * from ProtectedRoute.
 * 
 * @see OrderActions.tsx - action buttons with independent permission checks
 * @see ordersSlice.ts - order data source
 */
interface OrderDetailProps {
  orderId?: string;
}

/** Status timeline step definition */
interface TimelineStep {
  status: string;
  label: string;
  timestamp?: string;
  isActive: boolean;
  isCompleted: boolean;
}

export const OrderDetail: React.FC<OrderDetailProps> = ({ orderId: propOrderId }) => {
  const { id: paramId } = useParams<{ id: string }>();
  const orderId = propOrderId || paramId;
  const dispatch = useAppDispatch();
  const order = useAppSelector((state) =>
    state.orders.items.find((o) => o.id === orderId) || state.orders.selectedOrder
  );
  const isLoading = useAppSelector((state) => state.orders.isLoading);

  useEffect(() => {
    if (orderId) {
      dispatch(fetchOrderById(orderId));
    }
  }, [dispatch, orderId]);

  if (isLoading) return <div className="loading-skeleton" aria-busy="true">Loading order...</div>;
  if (!order) return <div className="not-found">Order not found</div>;

  /** Build timeline steps based on order status history */
  const statusFlow = ['pending', 'processing', 'shipped', 'delivered'];
  const currentIndex = statusFlow.indexOf(order.status);
  const timeline: TimelineStep[] = statusFlow.map((status, idx) => ({
    status,
    label: status.charAt(0).toUpperCase() + status.slice(1),
    timestamp: order.statusHistory?.[status],
    isActive: idx === currentIndex,
    isCompleted: idx < currentIndex,
  }));

  return (
    <div className="order-detail">
      <header className="order-detail-header">
        <h2>Order #{order.id}</h2>
        <span className={`status-badge status-${order.status}`}>{order.status}</span>
      </header>

      <section className="order-timeline" aria-label="Order status timeline">
        <ol className="timeline-steps">
          {timeline.map((step) => (
            <li key={step.status} className={`timeline-step ${step.isActive ? 'active' : ''} ${step.isCompleted ? 'completed' : ''}`}>
              <span className="step-label">{step.label}</span>
              {step.timestamp && <time className="step-time">{new Date(step.timestamp).toLocaleString()}</time>}
            </li>
          ))}
        </ol>
      </section>

      <section className="order-items">
        <h3>Items</h3>
        <ul>{order.items?.map((item: any) => (
          <li key={item.id}>{item.name} × {item.quantity} — ${(item.price * item.quantity).toFixed(2)}</li>
        ))}</ul>
        <p className="order-total"><strong>Total: ${order.total?.toFixed(2)}</strong></p>
      </section>

      <ErrorBoundary fallback={<div>Actions unavailable</div>}>
        <OrderActions orderId={order.id} orderStatus={order.status} />
      </ErrorBoundary>
    </div>
  );
};
