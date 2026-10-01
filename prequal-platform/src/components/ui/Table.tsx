import React, { useState, useMemo } from 'react';

export interface TableColumn<T> {
  key: keyof T | string;
  header: string;
  width?: string;
  sortable?: boolean;
  render?: (value: unknown, row: T, index: number) => React.ReactNode;
}

export interface TableProps<T> {
  columns: TableColumn<T>[];
  data: T[];
  keyExtractor: (row: T) => string;
  loading?: boolean;
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
  selectedKeys?: Set<string>;
  onSelectionChange?: (keys: Set<string>) => void;
  pagination?: {
    page: number;
    pageSize: number;
    total: number;
    onPageChange: (page: number) => void;
  };
  sortState?: {
    key: string;
    direction: 'asc' | 'desc';
  };
  onSort?: (key: string, direction: 'asc' | 'desc') => void;
}

function SortIcon({ direction }: { direction: 'asc' | 'desc' | null }) {
  if (!direction) {
    return (
      <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" style={{ opacity: 0.3 }}>
        <path d="M6 0L9 5H3L6 0ZM6 12L3 7H9L6 12Z" />
      </svg>
    );
  }
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
      {direction === 'asc' ? (
        <path d="M6 0L9 5H3L6 0Z" />
      ) : (
        <path d="M6 12L3 7H9L6 12Z" />
      )}
    </svg>
  );
}

export function Table<T extends Record<string, unknown>>({
  columns,
  data,
  keyExtractor,
  loading = false,
  emptyMessage = 'No data available',
  onRowClick,
  selectedKeys,
  onSelectionChange,
  pagination,
  sortState,
  onSort,
}: TableProps<T>) {
  const [localSort, setLocalSort] = useState<{ key: string; direction: 'asc' | 'desc' } | null>(null);

  const activeSort = sortState || localSort;

  const sortedData = useMemo(() => {
    if (!activeSort) return data;

    return [...data].sort((a, b) => {
      const aVal = a[activeSort.key];
      const bVal = b[activeSort.key];

      if (aVal == null) return 1;
      if (bVal == null) return -1;

      const comparison = String(aVal).localeCompare(String(bVal), undefined, { numeric: true });
      return activeSort.direction === 'asc' ? comparison : -comparison;
    });
  }, [data, activeSort]);

  const handleSort = (key: string) => {
    const newDirection: 'asc' | 'desc' =
      activeSort?.key === key && activeSort.direction === 'asc' ? 'desc' : 'asc';

    if (onSort) {
      onSort(key, newDirection);
    } else {
      setLocalSort({ key, direction: newDirection });
    }
  };

  const handleSelectAll = () => {
    if (!onSelectionChange) return;
    if (selectedKeys?.size === data.length) {
      onSelectionChange(new Set());
    } else {
      onSelectionChange(new Set(data.map(keyExtractor)));
    }
  };

  const handleSelectRow = (key: string) => {
    if (!onSelectionChange || !selectedKeys) return;
    const newKeys = new Set(selectedKeys);
    if (newKeys.has(key)) {
      newKeys.delete(key);
    } else {
      newKeys.add(key);
    }
    onSelectionChange(newKeys);
  };

  const hasCheckbox = onSelectionChange !== undefined;
  const tableLayout = columns.some((col) => col.width) ? 'auto' : 'fixed';

  return (
    <div style={{ width: '100%', overflowX: 'auto' }}>
      <table
        role="table"
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          tableLayout,
        }}
      >
        <thead>
          <tr>
            {hasCheckbox && (
              <th style={{ width: '48px', padding: '12px 16px', borderBottom: '2px solid #e5e7eb' }}>
                <input
                  type="checkbox"
                  checked={selectedKeys?.size === data.length && data.length > 0}
                  onChange={handleSelectAll}
                  aria-label="Select all rows"
                  style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                />
              </th>
            )}
            {columns.map((column) => {
              const sortDirection = activeSort?.key === column.key ? activeSort.direction : null;
              const isSortable = column.sortable !== false;

              return (
                <th
                  key={String(column.key)}
                  style={{
                    padding: '12px 16px',
                    textAlign: 'left',
                    fontSize: '12px',
                    fontWeight: 600,
                    color: '#6b7280',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    borderBottom: '2px solid #e5e7eb',
                    whiteSpace: 'nowrap',
                    width: column.width,
                    cursor: isSortable ? 'pointer' : 'default',
                    userSelect: 'none',
                  }}
                  onClick={isSortable ? () => handleSort(String(column.key)) : undefined}
                  aria-sort={
                    activeSort?.key === column.key
                      ? activeSort.direction === 'asc'
                        ? 'ascending'
                        : 'descending'
                      : undefined
                  }
                >
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                    {column.header}
                    {isSortable && <SortIcon direction={sortDirection} />}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <tr key={`skeleton-${i}`}>
                {hasCheckbox && (
                  <td style={{ padding: '16px' }}>
                    <div
                      style={{
                        width: '16px',
                        height: '16px',
                        backgroundColor: '#e5e7eb',
                        borderRadius: '4px',
                      }}
                    />
                  </td>
                )}
                {columns.map((_, j) => (
                  <td key={`skeleton-${i}-${j}`} style={{ padding: '16px' }}>
                    <div
                      style={{
                        height: '16px',
                        backgroundColor: '#e5e7eb',
                        borderRadius: '4px',
                        width: `${70 + Math.random() * 30}%`,
                      }}
                    />
                  </td>
                ))}
              </tr>
            ))
          ) : sortedData.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length + (hasCheckbox ? 1 : 0)}
                style={{ padding: '48px 16px', textAlign: 'center' }}
              >
                <span style={{ color: '#6b7280', fontSize: '14px' }}>{emptyMessage}</span>
              </td>
            </tr>
          ) : (
            sortedData.map((row, index) => {
              const rowKey = keyExtractor(row);
              const isSelected = selectedKeys?.has(rowKey);
              const isClickable = !!onRowClick;

              return (
                <tr
                  key={rowKey}
                  onClick={isClickable ? () => onRowClick(row) : undefined}
                  style={{
                    cursor: isClickable ? 'pointer' : 'default',
                    backgroundColor: isSelected ? '#f0f9ff' : index % 2 === 0 ? '#ffffff' : '#f9fafb',
                    transition: 'background-color 0.15s',
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) e.currentTarget.style.backgroundColor = '#f3f4f6';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = isSelected ? '#f0f9ff' : index % 2 === 0 ? '#ffffff' : '#f9fafb';
                  }}
                  aria-selected={isSelected}
                >
                  {hasCheckbox && (
                    <td style={{ padding: '16px', width: '48px' }}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => handleSelectRow(rowKey)}
                        onClick={(e) => e.stopPropagation()}
                        aria-label={`Select row ${index + 1}`}
                        style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                      />
                    </td>
                  )}
                  {columns.map((column) => {
                    const value = row[column.key as keyof T];

                    return (
                      <td
                        key={`${rowKey}-${String(column.key)}`}
                        style={{
                          padding: '16px',
                          fontSize: '14px',
                          color: '#374151',
                          borderBottom: '1px solid #f3f4f6',
                        }}
                      >
                        {column.render ? column.render(value, row, index) : String(value ?? '')}
                      </td>
                    );
                  })}
                </tr>
              );
            })
          )}
        </tbody>
      </table>

      {pagination && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px',
            borderTop: '1px solid #e5e7eb',
          }}
        >
          <span style={{ fontSize: '14px', color: '#6b7280' }}>
            Showing {(pagination.page - 1) * pagination.pageSize + 1} to{' '}
            {Math.min(pagination.page * pagination.pageSize, pagination.total)} of {pagination.total} results
          </span>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => pagination.onPageChange(pagination.page - 1)}
              disabled={pagination.page === 1}
              style={{
                padding: '8px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                backgroundColor: '#ffffff',
                color: pagination.page === 1 ? '#9ca3af' : '#374151',
                cursor: pagination.page === 1 ? 'not-allowed' : 'pointer',
                fontSize: '14px',
              }}
              aria-label="Previous page"
            >
              Previous
            </button>
            <button
              onClick={() => pagination.onPageChange(pagination.page + 1)}
              disabled={pagination.page * pagination.pageSize >= pagination.total}
              style={{
                padding: '8px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                backgroundColor: '#ffffff',
                color:
                  pagination.page * pagination.pageSize >= pagination.total ? '#9ca3af' : '#374151',
                cursor: pagination.page * pagination.pageSize >= pagination.total ? 'not-allowed' : 'pointer',
                fontSize: '14px',
              }}
              aria-label="Next page"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}