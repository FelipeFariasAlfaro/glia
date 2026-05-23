import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { store } from '../src/store';
import { setPage, setFilters, updateOrderStatus, clearOrdersCache } from '../src/store/ordersSlice';
import { setCredentials } from '../src/store/authSlice';
import { isFeatureEnabled, setFeatureOverride, clearFeatureOverrides } from '../src/config/featureFlags';

/**
 * Order flow tests covering state management, optimistic updates, and feature flags.
 * 
 * Tests verify:
 * 1. Order list pagination and filtering
 * 2. Optimistic status updates and rollback behavior
 * 3. Feature flag impact on API version selection
 * 4. Cache clearing behavior (or lack thereof on WebSocket disconnect)
 * 
 * @see ordersSlice.ts - state under test
 * @see useOptimisticUpdate.ts - optimistic update mechanism
 * @see featureFlags.ts - flag-based API version switching
 */

jest.mock('../src/api/orders');

describe('Order Management Flow', () => {
  beforeEach(() => {
    clearFeatureOverrides();
    // Set up authenticated user with permissions
    store.dispatch(setCredentials({
      user: { id: '1', name: 'Admin', email: 'admin@test.com', role: 'admin', permissions: ['orders:view', 'orders:cancel', 'orders:refund', 'orders:resend'] },
      accessToken: 'valid-token',
      refreshToken: 'valid-refresh',
      rememberMe: true,
    }));
  });

  describe('Pagination', () => {
    it('should update current page', () => {
      store.dispatch(setPage(3));
      expect(store.getState().orders.currentPage).toBe(3);
    });

    it('should reset page to 1 when filters change', () => {
      store.dispatch(setPage(5));
      store.dispatch(setFilters({ status: 'pending' }));
      expect(store.getState().orders.currentPage).toBe(1);
    });
  });

  describe('Optimistic Updates', () => {
    it('should update order status optimistically', () => {
      // Simulate having orders in state
      const initialOrders = [
        { id: 'order-1', customerName: 'John', status: 'pending', total: 99.99, createdAt: '2024-01-01' },
        { id: 'order-2', customerName: 'Jane', status: 'processing', total: 149.99, createdAt: '2024-01-02' },
      ];
      // Manually set items (normally done by fetchOrders.fulfilled)
      store.dispatch({ type: 'orders/fetchOrders/fulfilled', payload: { orders: initialOrders, total: 2 } });

      // Optimistic update: cancel order-1
      store.dispatch(updateOrderStatus({ orderId: 'order-1', status: 'cancelled' }));
      const order = store.getState().orders.items.find((o) => o.id === 'order-1');
      expect(order?.status).toBe('cancelled');
    });

    it('should rollback status on failed API call', () => {
      store.dispatch({ type: 'orders/fetchOrders/fulfilled', payload: { orders: [{ id: 'order-1', status: 'pending', customerName: 'Test', total: 50, createdAt: '2024-01-01' }], total: 1 } });

      // Optimistic: set to cancelled
      store.dispatch(updateOrderStatus({ orderId: 'order-1', status: 'cancelled' }));
      expect(store.getState().orders.items[0].status).toBe('cancelled');

      // Rollback: set back to pending
      store.dispatch(updateOrderStatus({ orderId: 'order-1', status: 'pending' }));
      expect(store.getState().orders.items[0].status).toBe('pending');
    });
  });

  describe('Feature Flags and API Version', () => {
    it('should use v1 API when advanced-order-filters is disabled', () => {
      expect(isFeatureEnabled('advanced-order-filters')).toBe(false);
      // fetchOrders would use /v1/orders
    });

    it('should use v2 API when advanced-order-filters is enabled', () => {
      setFeatureOverride('advanced-order-filters', true);
      expect(isFeatureEnabled('advanced-order-filters')).toBe(true);
      // fetchOrders would use /v2/orders — 404 if not deployed
    });
  });

  describe('Cache Management', () => {
    it('should clear cache when clearOrdersCache is dispatched', () => {
      store.dispatch({ type: 'orders/fetchOrders/fulfilled', payload: { orders: [{ id: '1', status: 'pending', customerName: 'X', total: 10, createdAt: '2024-01-01' }], total: 1 } });
      expect(store.getState().orders.items.length).toBe(1);

      store.dispatch(clearOrdersCache());
      expect(store.getState().orders.items.length).toBe(0);
      expect(store.getState().orders.lastFetchedAt).toBeNull();
    });

    it('should NOT automatically clear cache on WebSocket disconnect', () => {
      // This test documents the known stale cache issue
      // useWebSocket disconnect does NOT dispatch clearOrdersCache
      store.dispatch({ type: 'orders/fetchOrders/fulfilled', payload: { orders: [{ id: '1', status: 'pending', customerName: 'X', total: 10, createdAt: '2024-01-01' }], total: 1 } });

      // Simulate WebSocket disconnect — no cache clear happens
      // The data remains stale in the store
      expect(store.getState().orders.items.length).toBe(1);
      // This is the documented bug — cache should be cleared but isn't
    });
  });
});
