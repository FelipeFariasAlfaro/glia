import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { fetchOrdersApi, fetchOrderByIdApi } from '../api/orders';
import { isFeatureEnabled } from '../config/featureFlags';

/**
 * ordersSlice manages order list state, filters, pagination, and selected order.
 * 
 * CRITICAL COUPLING: useOptimisticUpdate dispatches actions to this slice
 * for immediate UI feedback. The rollback mechanism assumes:
 * - The `items` array exists and contains objects with `id` and `status` fields
 * - The `updateOrderStatus` reducer matches the dispatched action type
 * 
 * If this slice shape changes (e.g., renaming `items` to `orders`), the
 * optimistic rollback in useOptimisticUpdate will silently fail because
 * the reducer won't match or the state path won't exist.
 * 
 * STALE CACHE ISSUE: When WebSocket disconnects, this slice's cache is
 * NOT cleared. The useWebSocket hook does not dispatch any cache-clearing
 * action on disconnect. Users see stale data until they manually refresh.
 * 
 * @see useOptimisticUpdate.ts - dispatches to this slice for rollback
 * @see useWebSocket.ts - does NOT clear cache on disconnect
 * @see docs/incidents/2024-07-stale-cache.md - stale data incident
 */
interface Order {
  id: string;
  customerName: string;
  status: string;
  total: number;
  createdAt: string;
  items?: Array<{ id: string; name: string; quantity: number; price: number }>;
  statusHistory?: Record<string, string>;
}

interface OrdersState {
  items: Order[];
  recentOrders: Order[];
  selectedOrder: Order | null;
  totalCount: number;
  currentPage: number;
  pageSize: number;
  filters: Record<string, any>;
  isLoading: boolean;
  error: string | null;
  lastFetchedAt: number | null;
}

const initialState: OrdersState = {
  items: [],
  recentOrders: [],
  selectedOrder: null,
  totalCount: 0,
  currentPage: 1,
  pageSize: 20,
  filters: {},
  isLoading: false,
  error: null,
  lastFetchedAt: null,
};

/**
 * fetchOrders uses different API endpoints based on feature flags.
 * If 'advanced-order-filters' is enabled, it calls /api/v2/orders.
 * If the v2 endpoint isn't deployed, this results in 404 errors.
 */
export const fetchOrders = createAsyncThunk('orders/fetchOrders', async (params: { page: number; pageSize: number; filters: Record<string, any> }) => {
  const useV2 = isFeatureEnabled('advanced-order-filters');
  return fetchOrdersApi({ ...params, apiVersion: useV2 ? 'v2' : 'v1' });
});

export const fetchOrderById = createAsyncThunk('orders/fetchOrderById', async (orderId: string) => {
  return fetchOrderByIdApi(orderId);
});

export const fetchRecentOrders = createAsyncThunk('orders/fetchRecentOrders', async (params: { limit: number }) => {
  return fetchOrdersApi({ page: 1, pageSize: params.limit, filters: {}, apiVersion: 'v1' });
});

const ordersSlice = createSlice({
  name: 'orders',
  initialState,
  reducers: {
    setPage(state, action: PayloadAction<number>) {
      state.currentPage = action.payload;
    },
    setFilters(state, action: PayloadAction<Record<string, any>>) {
      state.filters = action.payload;
      state.currentPage = 1; // Reset to first page on filter change
    },
    /** Used by useOptimisticUpdate for immediate status changes and rollback */
    updateOrderStatus(state, action: PayloadAction<{ orderId: string; status: string }>) {
      const order = state.items.find((o) => o.id === action.payload.orderId);
      if (order) {
        order.status = action.payload.status;
      }
    },
    clearOrdersCache(state) {
      state.items = [];
      state.lastFetchedAt = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchOrders.pending, (state) => { state.isLoading = true; state.error = null; })
      .addCase(fetchOrders.fulfilled, (state, action) => {
        state.items = action.payload.orders;
        state.totalCount = action.payload.total;
        state.isLoading = false;
        state.lastFetchedAt = Date.now();
      })
      .addCase(fetchOrders.rejected, (state, action) => { state.isLoading = false; state.error = action.error.message || 'Failed to fetch orders'; })
      .addCase(fetchOrderById.fulfilled, (state, action) => { state.selectedOrder = action.payload; })
      .addCase(fetchRecentOrders.fulfilled, (state, action) => { state.recentOrders = action.payload.orders; });
  },
});

export const { setPage, setFilters, updateOrderStatus, clearOrdersCache } = ordersSlice.actions;
export default ordersSlice.reducer;
