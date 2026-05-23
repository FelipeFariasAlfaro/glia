import React, { useEffect, useCallback } from 'react';
import { useAppSelector, useAppDispatch } from '../../store';
import { fetchOrders, setFilters, setPage } from '../../store/ordersSlice';
import { DataTable } from '../shared/DataTable';
import { isFeatureEnabled } from '../../config/featureFlags';

/**
 * OrderList displays paginated orders with filtering and sorting.
 * Uses the DataTable shared component for rendering.
 * 
 * Filters and pagination state are managed in ordersSlice.
 * The 'advanced-order-filters' feature flag controls whether
 * additional filter options (date range, amount range) are shown.
 * 
 * NOTE: If the 'advanced-order-filters' flag is enabled, the API
 * endpoint changes to /api/v2/orders which supports the extra params.
 * Enabling the flag without the v2 API deployed causes 404 errors.
 * 
 * @see ordersSlice.ts - state management for orders
 * @see featureFlags.ts - controls advanced filters visibility AND API version
 */
interface OrderListProps {
  onOrderSelect?: (orderId: string) => void;
}

export const OrderList: React.FC<OrderListProps> = ({ onOrderSelect }) => {
  const dispatch = useAppDispatch();
  const { items, totalCount, currentPage, pageSize, filters, isLoading } = useAppSelector(
    (state) => state.orders
  );

  useEffect(() => {
    dispatch(fetchOrders({ page: currentPage, pageSize, filters }));
  }, [dispatch, currentPage, pageSize, filters]);

  const handlePageChange = useCallback((page: number) => {
    dispatch(setPage(page));
  }, [dispatch]);

  const handleFilterChange = useCallback((newFilters: Record<string, any>) => {
    dispatch(setFilters(newFilters));
  }, [dispatch]);

  /** Column definitions for the DataTable */
  const columns = [
    { key: 'id', label: 'Order ID', sortable: true },
    { key: 'customerName', label: 'Customer', sortable: true },
    { key: 'status', label: 'Status', sortable: true },
    { key: 'total', label: 'Total', sortable: true, render: (val: number) => `$${val.toFixed(2)}` },
    { key: 'createdAt', label: 'Date', sortable: true, render: (val: string) => new Date(val).toLocaleDateString() },
  ];

  const showAdvancedFilters = isFeatureEnabled('advanced-order-filters');

  return (
    <div className="order-list-container">
      <div className="order-filters">
        <select onChange={(e) => handleFilterChange({ ...filters, status: e.target.value })} value={filters.status || ''} aria-label="Filter by status">
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="processing">Processing</option>
          <option value="shipped">Shipped</option>
          <option value="delivered">Delivered</option>
          <option value="cancelled">Cancelled</option>
        </select>
        {showAdvancedFilters && (
          <>
            <input type="date" onChange={(e) => handleFilterChange({ ...filters, dateFrom: e.target.value })} aria-label="From date" />
            <input type="date" onChange={(e) => handleFilterChange({ ...filters, dateTo: e.target.value })} aria-label="To date" />
          </>
        )}
      </div>
      <DataTable columns={columns} data={items} isLoading={isLoading} onRowClick={(row) => onOrderSelect?.(row.id)} />
      <div className="pagination" role="navigation" aria-label="Order list pagination">
        <button disabled={currentPage <= 1} onClick={() => handlePageChange(currentPage - 1)}>Previous</button>
        <span>Page {currentPage} of {Math.ceil(totalCount / pageSize)}</span>
        <button disabled={currentPage >= Math.ceil(totalCount / pageSize)} onClick={() => handlePageChange(currentPage + 1)}>Next</button>
      </div>
    </div>
  );
};
