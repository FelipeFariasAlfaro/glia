import apiClient from './client';
import { isFeatureEnabled } from '../config/featureFlags';

/**
 * Order API calls. Handles CRUD operations for orders.
 * 
 * FEATURE FLAG DEPENDENCY: The 'advanced-order-filters' flag controls
 * which API version is used. When enabled, calls go to /v2/orders which
 * supports additional filter parameters (date range, amount range).
 * 
 * If the flag is enabled but the v2 API is not deployed, all order
 * fetches will return 404 errors. The flag must be synchronized with
 * backend deployment status.
 * 
 * @see featureFlags.ts - controls API version selection
 * @see ordersSlice.ts - also checks feature flag for API version
 * @see OrderList.tsx - UI that depends on these API calls
 */

interface FetchOrdersParams {
  page: number;
  pageSize: number;
  filters: Record<string, any>;
  apiVersion?: 'v1' | 'v2';
}

interface OrdersResponse {
  orders: any[];
  total: number;
  page: number;
  pageSize: number;
}

/**
 * Fetch paginated orders. Uses v1 or v2 endpoint based on feature flag.
 * The v2 endpoint supports advanced filters (dateFrom, dateTo, amountMin, amountMax).
 * Using v2 when it's not deployed results in 404 errors.
 */
export async function fetchOrdersApi(params: FetchOrdersParams): Promise<OrdersResponse> {
  const version = params.apiVersion || (isFeatureEnabled('advanced-order-filters') ? 'v2' : 'v1');
  const basePath = version === 'v2' ? '/v2/orders' : '/v1/orders';

  const queryParams = new URLSearchParams({
    page: String(params.page),
    pageSize: String(params.pageSize),
    ...(params.filters.status && { status: params.filters.status }),
    ...(params.filters.dateFrom && { dateFrom: params.filters.dateFrom }),
    ...(params.filters.dateTo && { dateTo: params.filters.dateTo }),
  });

  const response = await apiClient.get(`${basePath}?${queryParams}`);
  return response.data;
}

/** Fetch a single order by ID */
export async function fetchOrderByIdApi(orderId: string): Promise<any> {
  const response = await apiClient.get(`/v1/orders/${orderId}`);
  return response.data;
}

/** Cancel an order — requires 'orders:cancel' permission */
export async function cancelOrder(orderId: string): Promise<any> {
  const response = await apiClient.post(`/v1/orders/${orderId}/cancel`);
  return response.data;
}

/** Refund an order — requires 'orders:refund' permission */
export async function refundOrder(orderId: string): Promise<any> {
  const response = await apiClient.post(`/v1/orders/${orderId}/refund`);
  return response.data;
}

/** Resend an order — requires 'orders:resend' permission */
export async function resendOrder(orderId: string): Promise<any> {
  const response = await apiClient.post(`/v1/orders/${orderId}/resend`);
  return response.data;
}

/** Search orders by customer name or order ID */
export async function searchOrders(query: string): Promise<OrdersResponse> {
  const response = await apiClient.get(`/v1/orders/search?q=${encodeURIComponent(query)}`);
  return response.data;
}
