'use client';

import { useEffect, useState } from 'react';
import { Pagination } from './ui';

export type FilterOption = { value: string; label: string };
export type CollectionField = {
  key: string;
  label: string;
  options?: FilterOption[];
  type?: 'text' | 'date' | 'number';
};
export type CollectionFilterState = {
  search: string;
  values: Record<string, string>;
  offset: number;
  query: string;
  active: boolean;
  setSearch: (value: string) => void;
  setValue: (key: string, value: string) => void;
  setOffset: (offset: number) => void;
  reset: () => void;
};

export function useDebouncedValue(value: string): string {
  const [debounced, setDebounced] = useState<string>(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), 300);
    return () => clearTimeout(timer);
  }, [value]);
  return debounced;
}

export function useCollectionFilters(): CollectionFilterState {
  const [search, updateSearch] = useState<string>('');
  const [values, setValues] = useState<Record<string, string>>({});
  const [offset, setOffset] = useState<number>(0);
  const debounced = useDebouncedValue(search.trim());
  const params = new URLSearchParams({ limit: '20', offset: String(offset) });
  if (debounced) params.set('search', debounced);
  for (const [key, value] of Object.entries(values)) {
    if (value) params.set(key, value);
  }
  function reset(): void {
    updateSearch('');
    setValues({});
    setOffset(0);
  }
  return {
    search,
    values,
    offset,
    query: params.toString(),
    active: Boolean(search.trim() || Object.values(values).some(Boolean)),
    setSearch: (value: string): void => {
      updateSearch(value);
      setOffset(0);
    },
    setValue: (key: string, value: string): void => {
      setValues(previous => ({ ...previous, [key]: value }));
      setOffset(0);
    },
    setOffset,
    reset,
  };
}

export const financialFields: CollectionField[] = [
  { key: 'start_date', label: 'From date', type: 'date' },
  { key: 'end_date', label: 'To date', type: 'date' },
  { key: 'min_amount', label: 'Minimum amount', type: 'number' },
  { key: 'max_amount', label: 'Maximum amount', type: 'number' },
];

export function CollectionFilters({ filters, fields, label, hideSearch = false, reserveStatusSpace = false }: {
  filters: CollectionFilterState;
  fields: CollectionField[];
  label: string;
  hideSearch?: boolean;
  reserveStatusSpace?: boolean;
}): React.JSX.Element {
  return (
    <div
      className={`collection-filters${reserveStatusSpace ? ' collection-filters-stable-status' : ''}`}
      aria-label={`${label} filters`}
    >
      {!hideSearch && (
        <label>
        <span>Search {label}</span>
        <input
          aria-label={`Search ${label}`}
          placeholder="Search reference, name or description…"
          value={filters.search}
          onChange={event => filters.setSearch(event.target.value)}
        />
        </label>
      )}
      {fields.map(field => (
        <label key={field.key}>
          <span>{field.label}</span>
          {field.options ? (
            <select
              aria-label={`${label}: ${field.label}`}
              value={filters.values[field.key] || ''}
              onChange={event => filters.setValue(field.key, event.target.value)}
            >
              <option value="">All</option>
              {field.options.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              aria-label={`${label}: ${field.label}`}
              type={field.type || 'text'}
              min={field.type === 'number' ? '0' : undefined}
              step={field.type === 'number' ? '0.01' : undefined}
              value={filters.values[field.key] || ''}
              onChange={event => filters.setValue(field.key, event.target.value)}
            />
          )}
        </label>
      ))}
      {reserveStatusSpace ? (
        <div className="collection-filter-status" aria-live="polite">
          {filters.active && (
            <button
              type="button"
              className="button secondary"
              onClick={filters.reset}
            >
              Reset filters
            </button>
          )}
          {filters.active && <span className="muted">Filters active</span>}
        </div>
      ) : (
        <>
          {filters.active && (
            <button
              type="button"
              className="button secondary"
              onClick={filters.reset}
            >
              Reset filters
            </button>
          )}
          {filters.active && <span className="muted">Filters active</span>}
        </>
      )}
    </div>
  );
}

export function CollectionCount({ count, label = 'records' }: {
  count: number;
  label?: string;
}): React.JSX.Element {
  const displayLabel = count === 1 && label === 'records' ? 'record' : label;
  return (
    <p className="muted collection-count" style={{ margin: '0.5rem 0 1rem' }}>
      {count} matching {displayLabel}
    </p>
  );
}

export function CollectionPagination({ filters, count, pageSize = 20 }: {
  filters: CollectionFilterState;
  count: number;
  pageSize?: number;
}): React.JSX.Element | null {
  const totalPages = Math.ceil(count / pageSize);
  if (totalPages <= 1) return null;
  return (
    <div className="collection-pagination" style={{ margin: '1.5rem 0 0.5rem', display: 'flex', justifyContent: 'center' }}>
      <Pagination
        page={Math.floor(filters.offset / pageSize) + 1}
        totalPages={totalPages}
        onChange={(page: number) => filters.setOffset((page - 1) * pageSize)}
      />
    </div>
  );
}
