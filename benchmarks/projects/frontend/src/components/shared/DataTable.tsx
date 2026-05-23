import React, { useState, useCallback, useMemo } from 'react';

/**
 * DataTable is a reusable table component with sorting, loading states,
 * and row click handling. Used by OrderList and other list views.
 * 
 * Supports custom cell renderers via column definitions.
 * Sorting is handled client-side for the current page of data.
 * 
 * @see OrderList.tsx - primary consumer of this component
 */
interface Column<T = any> {
  key: string;
  label: string;
  sortable?: boolean;
  render?: (value: any, row: T) => React.ReactNode;
  width?: string;
}

interface DataTableProps<T = any> {
  columns: Column<T>[];
  data: T[];
  isLoading?: boolean;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
  className?: string;
}

type SortDirection = 'asc' | 'desc' | null;

export function DataTable<T extends Record<string, any>>({
  columns,
  data,
  isLoading = false,
  onRowClick,
  emptyMessage = 'No data available',
  className = '',
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>(null);

  /** Toggle sort direction or set new sort column */
  const handleSort = useCallback((key: string) => {
    if (sortKey === key) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : prev === 'desc' ? null : 'asc'));
      if (sortDirection === 'desc') setSortKey(null);
    } else {
      setSortKey(key);
      setSortDirection('asc');
    }
  }, [sortKey, sortDirection]);

  /** Sort data client-side based on current sort state */
  const sortedData = useMemo(() => {
    if (!sortKey || !sortDirection) return data;
    return [...data].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      const comparison = typeof aVal === 'string' ? aVal.localeCompare(bVal) : aVal - bVal;
      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }, [data, sortKey, sortDirection]);

  if (isLoading) {
    return <div className="table-loading" aria-busy="true"><div className="spinner" />Loading...</div>;
  }

  return (
    <div className={`data-table-wrapper ${className}`}>
      <table className="data-table" role="grid">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} style={{ width: col.width }} onClick={() => col.sortable && handleSort(col.key)}
                  className={col.sortable ? 'sortable' : ''} aria-sort={sortKey === col.key ? (sortDirection === 'asc' ? 'ascending' : 'descending') : undefined}>
                {col.label}
                {sortKey === col.key && <span className="sort-indicator">{sortDirection === 'asc' ? '▲' : '▼'}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedData.length === 0 ? (
            <tr><td colSpan={columns.length} className="empty-row">{emptyMessage}</td></tr>
          ) : (
            sortedData.map((row, idx) => (
              <tr key={row.id || idx} onClick={() => onRowClick?.(row)} className={onRowClick ? 'clickable' : ''} tabIndex={onRowClick ? 0 : undefined}>
                {columns.map((col) => (
                  <td key={col.key}>{col.render ? col.render(row[col.key], row) : row[col.key]}</td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
