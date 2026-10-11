'use client';

import { useDebouncedValue } from './collection-filters';


import Link from 'next/link';
import { useState, useTransition } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Archive,
  ArrowRight,
  Bell,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  Filter,
  Inbox,
  RefreshCw,
  RotateCcw,
  Search,
  Store,
  Trash2,
  X,
  Sparkles,
  ShoppingBag,
  DollarSign,
  AlertTriangle,
  Info,
  CheckCircle,
} from 'lucide-react';

import { api } from '@/lib/api';
import type {
  NotificationFiltersMeta,
  NotificationItem,
  Page,
} from '@/lib/types';
import { useShop } from './providers';
import { Gate } from './account';
import { Empty, ErrorState, Loading } from './ui';

const PAGE_SIZE = 15;

export function NotificationsPage() {
  const { user, notify } = useShop();
  const client = useQueryClient();

  const [activeTab, setActiveTab] = useState<'all' | 'unread' | 'archived'>('all');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedStore, setSelectedStore] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const debouncedSearch = useDebouncedValue(searchQuery);
  const [page, setPage] = useState<number>(0);
  const [, startTransition] = useTransition();

  // Query metadata (categories with counts, available stores)
  const filtersQuery = useQuery({
    queryKey: ['notifications', 'filters', user?.id],
    queryFn: () => api<NotificationFiltersMeta>('notifications/filters'),
    enabled: !!user,
  });

  // Query notifications list based on active filters
  const notificationsQuery = useQuery({
    queryKey: [
      'notifications',
      'list',
      activeTab,
      selectedCategory,
      selectedStore,
      debouncedSearch,
      page,
      user?.id,
    ],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[7] === user?.id
        && previousQuery?.queryKey[4] === selectedStore
        ? previousData
        : undefined,
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set('limit', String(PAGE_SIZE));
      params.set('offset', String(page * PAGE_SIZE));

      if (activeTab === 'unread') {
        params.set('state', 'unread');
      } else if (activeTab === 'archived') {
        params.set('include_archived', 'true');
      }

      if (selectedCategory && selectedCategory !== 'all') {
        params.set('category', selectedCategory);
      }

      if (selectedStore && selectedStore !== 'all') {
        params.set('store', selectedStore);
      }

      if (debouncedSearch.trim()) {
        params.set('search', debouncedSearch.trim());
      }

      const endpoint = activeTab === 'archived'
        ? `notifications/archived?${params.toString()}`
        : `notifications?${params.toString()}`;

      return api<Page<NotificationItem>>(endpoint);
    },
    enabled: !!user,
  });

  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['notifications'] }),
      client.invalidateQueries({ queryKey: ['notifications', 'counts'] }),
      client.invalidateQueries({ queryKey: ['notifications', 'filters'] }),
    ]);
  };

  const action = useMutation({
    mutationFn: ({ id, path, method = 'POST' }: { id?: number; path: string; method?: string }) =>
      api(id ? `notifications/${id}/${path}` : `notifications/${path}`, method, {}),
    onSuccess: () => {
      void refresh();
    },
    onError: (error) => notify((error as Error).message, true),
  });

  const deleteAction = useMutation({
    mutationFn: (id: number) => api(`notifications/${id}`, 'DELETE', {}),
    onSuccess: () => {
      notify('Notification deleted');
      void refresh();
    },
    onError: (error) => notify((error as Error).message, true),
  });

  const meta = filtersQuery.data;
  const categoriesList = meta?.categories || [
    { id: 'all', label: 'All Categories', count: 0 },
    { id: 'store', label: 'Store', count: 0 },
    { id: 'affiliates', label: 'Affiliates & Referrals', count: 0 },
    { id: 'order', label: 'Orders', count: 0 },
    { id: 'refund', label: 'Refunds', count: 0 },
    { id: 'payout', label: 'Payouts & Wallet', count: 0 },
  ];

  const isBackoffice = Boolean(user?.is_staff || user?.is_superuser || user?.is_business_admin);
  const rawStores = meta?.stores || [];
  const storesList = isBackoffice ? rawStores.filter(s => s.is_official !== false) : rawStores;
  const results = notificationsQuery.data?.results || [];

  const totalCount = notificationsQuery.data?.count || 0;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);
  const unreadCount = meta?.counts?.unread || 0;

  function resetFilters() {
    startTransition(() => {
      setActiveTab('all');
      setSelectedCategory('all');
      setSelectedStore('all');
      setSearchQuery('');
      setPage(0);
    });
  }

  const hasActiveFilters =
    activeTab !== 'all' || selectedCategory !== 'all' || selectedStore !== 'all' || searchQuery.trim().length > 0;

  return (
    <Gate next="/notifications">
      <div className="container section notifications-page">
        {/* Breadcrumb */}
        <div className="breadcrumb">
          <Link href="/">Home</Link>
          <ChevronRight size={12} />
          <Link href="/account">My account</Link>
          <ChevronRight size={12} />
          <span>Notifications</span>
        </div>

        {/* Page Heading */}
        <div className="notifications-header">
          <div>
            <span className="eyebrow green">COMMUNICATION HUB</span>
            <h1>Notifications</h1>
            <p className="muted">
              Follow store activity, order updates, referral rewards, and important alerts.
            </p>
          </div>

          <div className="notifications-header-actions">
            {unreadCount > 0 && activeTab !== 'archived' && (
              <button
                className="button secondary"
                disabled={action.isPending}
                onClick={() => action.mutate({ path: 'mark-all-read' })}
              >
                <CheckCheck size={16} />
                Mark all as read
              </button>
            )}

            <button
              className="icon-button"
              title="Refresh notifications"
              aria-label="Refresh notifications"
              onClick={() => void refresh()}
              disabled={notificationsQuery.isFetching}
            >
              <RefreshCw
                size={16}
                className={notificationsQuery.isFetching ? 'spin' : ''}
              />
            </button>
          </div>
        </div>

        {/* Status Tabs (All, Unread, Archived) */}
        <div className="notifications-status-tabs">
          <button
            className={`status-tab ${activeTab === 'all' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('all');
              setPage(0);
            }}
          >
            <Inbox size={16} />
            Inbox
            {meta?.counts?.total !== undefined && (
              <span className="count-pill">{meta.counts.total - (meta.counts.archived || 0)}</span>
            )}
          </button>

          <button
            className={`status-tab ${activeTab === 'unread' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('unread');
              setPage(0);
            }}
          >
            <Bell size={16} />
            Unread
            {unreadCount > 0 && <span className="count-pill highlight">{unreadCount}</span>}
          </button>

          <button
            className={`status-tab ${activeTab === 'archived' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('archived');
              setPage(0);
            }}
          >
            <Archive size={16} />
            Archived
            {meta?.counts?.archived !== undefined && (
              <span className="count-pill">{meta.counts.archived}</span>
            )}
          </button>
        </div>

        {/* Search & Store Toolbar */}
        <div className="notifications-toolbar">
          <div className="notifications-search-box">
            <Search size={16} />
            <input
              type="text"
              placeholder="Search notifications by keyword, reference, order…"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(0);
              }}
            />
            {searchQuery && (
              <button
                type="button"
                aria-label="Clear search"
                onClick={() => {
                  setSearchQuery('');
                  setPage(0);
                }}
              >
                <X size={15} />
              </button>
            )}
          </div>

          {storesList.length > 0 && (
            <div className="notifications-store-filter">
              <Store size={15} />
              <select
                aria-label="Filter by store"
                value={selectedStore}
                onChange={(e) => {
                  setSelectedStore(e.target.value);
                  setPage(0);
                }}
              >
                <option value="all">All stores ({storesList.length})</option>
                {storesList.map((store) => (
                  <option key={store.id} value={String(store.id)}>
                    {store.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {hasActiveFilters && (
            <button
              className="text-button notifications-reset-btn"
              onClick={resetFilters}
            >
              <RotateCcw size={13} />
              Reset filters
            </button>
          )}
        </div>

        {/* Category Pills */}
        <div className="notifications-categories">
          {categoriesList.map((cat) => {
            const isSelected = selectedCategory === cat.id;
            return (
              <button
                key={cat.id}
                className={`category-pill ${isSelected ? 'active' : ''}`}
                onClick={() => {
                  setSelectedCategory(cat.id);
                  setPage(0);
                }}
              >
                {cat.id === 'store' && <Store size={13} />}
                {cat.id === 'affiliates' && <DollarSign size={13} />}
                {cat.id === 'order' && <ShoppingBag size={13} />}
                {cat.id === 'refund' && <RotateCcw size={13} />}
                {cat.id === 'payout' && <DollarSign size={13} />}
                {cat.id === 'all' && <Filter size={13} />}
                <span>{cat.label}</span>
                {cat.count > 0 && <span className="cat-count">{cat.count}</span>}
              </button>
            );
          })}
        </div>

        {/* List Content */}
        <div className="notifications-main">
          {notificationsQuery.isFetching && !notificationsQuery.isLoading && (
            <p role="status" aria-live="polite">Updating results…</p>
          )}
          {notificationsQuery.isLoading ? (
            <Loading />
          ) : notificationsQuery.error ? (
            <ErrorState error={notificationsQuery.error as Error} retry={() => void refresh()} />
          ) : results.length === 0 ? (
            <div className="notifications-empty-box">
              <Inbox size={40} strokeWidth={1.2} />
              <h3>
                {hasActiveFilters
                  ? 'No notifications match your filters'

                  : 'You have no notifications yet'}
              </h3>
              <p>
                {hasActiveFilters
                  ? 'Try broadening your search keyword or switching category and store filters.'
                  : 'Notifications regarding your orders, stores, and referrals will appear here.'}
              </p>
              {hasActiveFilters && (
                <button className="button secondary" onClick={resetFilters}>
                  Clear all filters
                </button>
              )}
            </div>
          ) : (
            <div className="notifications-card-list">
              {results.map((item) => (
                <NotificationCard
                  key={item.id}
                  item={item}
                  isArchivedView={activeTab === 'archived'}
                  onMarkRead={() =>
                    action.mutate({ id: item.id, path: 'mark-read' })
                  }
                  onMarkUnread={() =>
                    action.mutate({ id: item.id, path: 'mark-unread' })
                  }
                  onArchive={() => action.mutate({ id: item.id, path: 'archive' })}
                  onRestore={() => action.mutate({ id: item.id, path: 'restore' })}
                  onDelete={() => deleteAction.mutate(item.id)}
                  isPending={action.isPending || deleteAction.isPending}
                />
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="notifications-pagination">
              <span className="pagination-info">
                Showing {page * PAGE_SIZE + 1}–
                {Math.min((page + 1) * PAGE_SIZE, totalCount)} of {totalCount} notifications
              </span>

              <div className="pagination-buttons">
                <button
                  className="icon-button"
                  disabled={page <= 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  aria-label="Previous page"
                >
                  <ChevronLeft size={18} />
                </button>
                <span className="page-current">
                  Page {page + 1} of {totalPages}
                </span>
                <button
                  className="icon-button"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                  aria-label="Next page"
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </Gate>
  );
}

function NotificationCard({
  item,
  isArchivedView,
  onMarkRead,
  onMarkUnread,
  onArchive,
  onRestore,
  onDelete,
  isPending,
}: {
  item: NotificationItem;
  isArchivedView: boolean;
  onMarkRead: () => void;
  onMarkUnread: () => void;
  onArchive: () => void;
  onRestore: () => void;
  onDelete: () => void;
  isPending: boolean;
}) {
  const levelIcon =
    item.level === 'success' ? (
      <CheckCircle size={17} className="icon-success" />
    ) : item.level === 'warning' ? (
      <AlertTriangle size={17} className="icon-warning" />
    ) : item.level === 'error' ? (
      <AlertTriangle size={17} className="icon-error" />
    ) : (
      <Info size={17} className="icon-info" />
    );

  const formattedDate = new Date(item.timestamp).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });

  return (
    <article
      className={`notification-card-item ${item.unread ? 'unread' : 'read'} level-${item.level}`}
    >
      <div className="card-indicator" title={`Level: ${item.level}`}>
        {levelIcon}
      </div>

      <div className="card-body">
        <div className="card-header-line">
          <div className="card-badges">
            {item.category && item.category !== 'general' && (
              <span className={`badge-pill category-${item.category}`}>
                {item.category.toUpperCase()}
              </span>
            )}
            {item.store && (
              <span className="badge-pill store">
                <Store size={11} />
                {item.store.name}
              </span>
            )}
            {item.unread && <span className="badge-pill unread-badge">New</span>}
          </div>

          <time className="card-timestamp" dateTime={item.timestamp} title={formattedDate}>
            {timeAgo(item.timestamp)}
          </time>
        </div>

        {/* Title / Verb: completely wrapped, no horizontal slider */}
        <h3 className="card-verb">{item.verb}</h3>

        {/* Description: completely wrapped, variable height per message */}
        {item.description && <p className="card-description">{item.description}</p>}

        <div className="card-footer-meta">
          <span className="card-exact-date">{formattedDate}</span>
        </div>
      </div>

      <div className="card-actions">
        {isArchivedView ? (
          <button
            className="icon-button"
            title="Restore to inbox"
            aria-label="Restore notification"
            disabled={isPending}
            onClick={onRestore}
          >
            <Inbox size={16} />
          </button>
        ) : (
          <>
            <button
              className="icon-button"
              title={item.unread ? 'Mark as read' : 'Mark as unread'}
              aria-label={item.unread ? 'Mark as read' : 'Mark as unread'}
              disabled={isPending}
              onClick={item.unread ? onMarkRead : onMarkUnread}
            >
              <CheckCheck size={16} className={item.unread ? 'action-unread' : ''} />
            </button>
            <button
              className="icon-button"
              title="Archive notification"
              aria-label="Archive notification"
              disabled={isPending}
              onClick={onArchive}
            >
              <Archive size={16} />
            </button>
          </>
        )}
        <button
          className="icon-button action-delete"
          title="Delete notification"
          aria-label="Delete notification"
          disabled={isPending}
          onClick={onDelete}
        >
          <Trash2 size={16} />
        </button>
      </div>
    </article>
  );
}

function timeAgo(value: string): string {
  if (!value || !Number.isFinite(new Date(value).getTime())) return 'Not recorded';
  const seconds = Math.max(1, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return 'Just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}
