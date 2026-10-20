'use client';

import { useNotificationDetail } from './notification-detail';

import type { CollectionField } from './collection-filters';
import { CollectionCount, CollectionFilters, CollectionPagination, financialFields, useCollectionFilters, useDebouncedValue } from './collection-filters';


import { browserTimeZone } from '@/lib/datetime';

import { ActivityDetails, DateStamp, activityDate } from './activity';
import { FormEvent, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Ban,
  ChartNoAxesCombined,
  Check,
  Clock,
  DollarSign,
  ExternalLink,
  Eye,
  FileText,
  Landmark,
  LockKeyhole,
  Mail,
  Package, Printer,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Share2,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  Store,
  Trash2,
  Truck,
  UserRound,
  UserRoundCheck,
  UserRoundX,
  UsersRound,
  UserPlus,
  X,
} from 'lucide-react';
import { api, categories, money } from '@/lib/api';
import type { AdminCoupon, AdminDashboardData, AdminOrder, AdminRefund, AdminTaxJurisdiction, AdminTaxesResponse, AdminUserProfile, Order, Page, StaffUser, StorePayout, StoreEarningsLedger, MerchantStoreSummary } from '@/lib/types';
import { useShop } from './providers';
import { BankAccounts } from './bank-accounts';
import { StripePayoutDestinations } from './stripe-destinations';
import { useDialogFocus, Pagination, Empty, ErrorState, Field, Loading, Status, VerifiedBadge, ResponsiveMediaImage } from './ui';

type ActionDialogRequest = {
  title: string;
  message: string;
  confirmLabel?: string;
  reasonLabel?: string;
  reasonPresets?: string[];
};

function isOrderAllDigital(order: { items_snapshot?: Array<Record<string, unknown>> }): boolean {
  return Boolean(
    order.items_snapshot &&
    order.items_snapshot.length > 0 &&
    order.items_snapshot.every((item) => Boolean(item.is_digital))
  );
}

function getOrderOverrideOptions(status: string, isAllDigital: boolean): string[] {
  if (isAllDigital) {
    if (status === 'pending') return ['pending'];
    if (status === 'confirmed') return ['confirmed'];
    if (status === 'shipped') return ['shipped', 'delivered'];
    if (status === 'delivered') return ['delivered'];
    return [status];
  }
  if (status === 'pending') return ['pending', 'confirmed', 'cancelled'];
  if (status === 'confirmed') return ['confirmed', 'shipped', 'picked up', 'cancelled'];
  if (status === 'shipped') return ['shipped', 'delivered', 'confirmed'];
  if (status === 'delivered') return ['delivered', 'shipped'];
  if (status === 'picked up') return ['picked up', 'confirmed'];
  return [status];
}

function useActionDialog() {
  const [request, setRequest] = useState<ActionDialogRequest | null>(null);
  const resolver = useRef<((value: string | null) => void) | null>(null);

  const ask = (next: ActionDialogRequest) =>
    new Promise<string | null>((resolve) => {
      resolver.current = resolve;
      setRequest(next);
    });

  const close = (value: string | null) => {
    resolver.current?.(value);
    resolver.current = null;
    setRequest(null);
  };

  return {
    ask,
    dialog: (
      <ActionDialog
        key={request?.title || 'closed'}
        request={request}
        onClose={close}
      />
    ),
  };
}

function ActionDialog({
  request,
  onClose,
}: {
  request: ActionDialogRequest | null;
  onClose: (value: string | null) => void;
}) {
  const [reason, setReason] = useState('');
  const dialogRef = useDialogFocus(Boolean(request), () => onClose(null));

  if (!request) return null;
  const requiresReason = Boolean(request.reasonLabel);

  return (
    <div
      className="admin-dialog-backdrop"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && onClose(null)}
    >
      <section
        ref={dialogRef}
        className="admin-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="action-dialog-title"
      >
        <div className="admin-dialog-head">
          <div>
            <span className="eyebrow green">CONFIRM ACTION</span>
            <h2 id="action-dialog-title">{request.title}</h2>
          </div>
          <button
            className="icon-button"
            aria-label="Close"
            onClick={() => onClose(null)}
          >
            <X size={19} />
          </button>
        </div>
        <p>{request.message}</p>
        {requiresReason && (
          <Field label={request.reasonLabel!}>
            {request.reasonPresets && request.reasonPresets.length > 0 && (
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                {request.reasonPresets.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    className="button secondary compact"
                    style={{
                      fontSize: '11px',
                      padding: '4px 10px',
                      minHeight: '28px',
                      borderRadius: '14px',
                      background: reason === preset ? 'var(--green-light)' : 'var(--paper)',
                      borderColor: reason === preset ? 'var(--green)' : 'var(--line)',
                      color: reason === preset ? 'var(--green)' : 'var(--ink)',
                    }}
                    onClick={() => setReason(preset)}
                  >
                    {preset}
                  </button>
                ))}
              </div>
            )}
            <textarea
              autoFocus
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              rows={4}
              required
            />
          </Field>
        )}
        <div className="form-actions">
          <button
            className="button secondary"
            onClick={() => onClose(null)}
          >
            Cancel
          </button>
          <button
            className="button"
            disabled={requiresReason && !reason.trim()}
            onClick={() => onClose(requiresReason ? reason.trim() : '')}
          >
            {request.confirmLabel || 'Confirm'}
          </button>
        </div>
      </section>
    </div>
  );
}

function payoutAccountField(key: string, value: unknown): [string, string] {
  const text = String(value);
  if (/last_?4$/i.test(key)) {
    return [key.replace(/_?last_?4$/i, '').replaceAll('_', ' '), `********${text.slice(-2)}`];
  }
  if (/account_number|routing_number|iban/i.test(key)) {
    const compact = text.replace(/\s/g, '');
    return [key.replaceAll('_', ' '), compact ? `********${compact.slice(-4)}` : ''];
  }
  return [key.replaceAll('_', ' '), text];
}

function payoutDetail(payout: StorePayout): DashboardDetail {
  const rows: [string, string][] = [
    ['Reference', payout.reference],
    ['Store', payout.store_name || (payout.store ? `Store #${payout.store}` : 'Merchant wallet')],
    ['Amount', money(payout.amount)],
    ['Status', payout.status],
    ['Method', payout.payout_method.replaceAll('_', ' ')],
    ['Requested', activityDate(payout.created)],
  ];
  if (payout.processed_at) rows.push(['Processed', activityDate(payout.processed_at)]);
  if (payout.notes) rows.push(['Notes', payout.notes]);
  for (const [key, value] of Object.entries(payout.account_details || {})) {
    if (value !== null && value !== undefined && String(value).trim()) {
      rows.push(payoutAccountField(key, value));
    }
  }
  return { title: `Payout ${payout.reference}`, category: 'Payout', rows };
}

export function AdminDashboardPage() {
  const { user, sessionLoading, notify } = useShop();
  const isAdmin = Boolean(user && (user.is_superuser || user.is_business_admin));
  const [days, setDays] = useState('30');
  const actionDialog = useActionDialog();
  const [detail, setDetail] = useState<DashboardDetail | null>(null);
  const dashboard = useQuery({
    queryKey: ['admin', 'dashboard', days, user?.id],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey.at(-1) === user?.id ? previousData : undefined,
    queryFn: () => api<AdminDashboardData>(`admin/staff/dashboard?days=${days}&time_zone=${encodeURIComponent(browserTimeZone())}`),
    enabled: !!(user?.is_staff || (user?.is_superuser || user?.is_business_admin)),
  });
  const coupons = useQuery({
    queryKey: ['admin', 'coupons'],
    queryFn: () => api<Page<AdminCoupon>>('admin/staff/coupons?limit=5'),
    enabled: !!(user?.is_staff || user?.is_superuser || user?.is_business_admin),
  });
  const refunds = useQuery({
    queryKey: ['admin', 'refunds'],
    queryFn: () => api<Page<AdminRefund>>('admin/staff/refunds?limit=5'),
    enabled: !!(user?.is_staff || user?.is_superuser || user?.is_business_admin),
  });
  const payouts = useQuery({
    queryKey: ['admin', 'payouts', 'overview', user?.id],
    queryFn: () => api<Page<StorePayout>>('admin/staff/payouts?limit=5'),
    enabled: Boolean(user?.is_staff || user?.is_superuser || user?.is_business_admin),
  });
  const client = useQueryClient();

  async function refreshOperations() {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['admin', 'dashboard'] }),
      client.invalidateQueries({ queryKey: ['admin', 'coupons'] }),
      client.invalidateQueries({ queryKey: ['admin', 'refunds'] }),
      client.invalidateQueries({ queryKey: ['admin', 'orders'] }),
      client.invalidateQueries({ queryKey: ['admin', 'payouts'] }),
    ]);
  }

  async function setCoupon(coupon: AdminCoupon, action: 'toggle' | 'delete') {
    const isUsed = Boolean(coupon.num_used > 0 || (coupon.redemptions && coupon.redemptions.length > 0));
    try {
      if (action === 'delete') {
        if (isUsed) {
          await actionDialog.ask({
            title: 'Coupon Cannot Be Deleted',
            message: `Coupon "${coupon.code}" has recorded customer redemptions (${coupon.num_used} used in orders). To preserve historical order records and financial audit trails, used coupons cannot be deleted from the database. Keeping the coupon deactivated ensures it can never be used again.`,
            confirmLabel: 'Understood',
          });
          return;
        }
        if (await actionDialog.ask({ title: 'Delete coupon', message: `Permanently delete unused coupon ${coupon.code}?`, confirmLabel: 'Delete' }) === null) return;
        await api(`admin/staff/coupons/${coupon.id}`, 'DELETE');
        notify(`Coupon ${coupon.code} deleted`);
      } else {
        await api(`admin/staff/coupons/${coupon.id}`, 'PATCH', { active: !coupon.active });
        notify(`Coupon ${coupon.code} ${coupon.active ? 'deactivated' : 'reactivated'}`);
      }
      await refreshOperations();
    } catch (error) { notify((error as Error).message, true); }
  }

  async function processRefund(refund: AdminRefund, action: 'approve' | 'decline') {
    const reason = await actionDialog.ask({ title: `${action === 'approve' ? 'Approve' : 'Decline'} refund #${refund.id}`, message: 'A reason is required for every refund decision.', confirmLabel: action === 'approve' ? 'Approve refund' : 'Decline refund', reasonLabel: 'Reason' });
    if (reason === null) return;
    try {
      const result = await api<{ detail: string }>(`admin/staff/refunds/${refund.id}/process`, 'POST', { action, reason });
      notify(result.detail);
      await refreshOperations();
    } catch (error) { notify((error as Error).message, true); }
  }

  function showOrderDetails(order: AdminDashboardData['recent_orders'][number]): void {
    setDetail({
      title: `Order #${order.orderId}`,
      rows: [
        ['Buyer', order.buyer_email || 'Guest'],
        ['Status', order.status],
        ['Total', money(order.total)],
        ['Created', activityDate(order.created)],
        ['Updated', activityDate(order.updated)],
        ['Status changed', activityDate(order.status_updated_at)],
        ['Cancelled', activityDate(order.cancelled_at)],
        ['Refunded', activityDate(order.refunded_at)],
        ['Tracking', order.tracking_number || 'Not assigned'],
      ],
    });
  }

  function showRefundDetails(refund: AdminRefund): void {
    setDetail({
      title: `Refund #${refund.id}`,
      rows: [
        ['Order', `#${refund.order}`],
        ['Customer', refund.email],
        ['Method', refund.refund_type.replaceAll('_', ' ')],
        ['Status', refund.status],
        ...(refund.processed_by_email ? [['Processed by', refund.processed_by_email] as [string, string]] : []),
        ['Reason', refund.reason],
        ...(refund.provider_reference
          ? ([['Provider Reference', refund.provider_reference]] as [string, string][])
          : []),
        ...(refund.failure_reason
          ? ([['Failure Details', refund.failure_reason]] as [string, string][])
          : []),
        ['Created', activityDate(refund.created)],
      ],
    });
  }

  function showCouponDetails(coupon: AdminCoupon): void {
    setDetail({
      title: `Coupon ${coupon.code}`,
      rows: [
        ['Status', coupon.active ? 'Active' : 'Inactive'],
        ['Discount', `${coupon.discount}%`],
        ['Created by', coupon.created_by || 'Not recorded'],
        ['Valid from', activityDate(coupon.valid_from)],
        ['Valid to', activityDate(coupon.valid_to)],
        ['Usage', `${coupon.num_used} of ${coupon.num_available}`],
        ...(coupon.redemptions?.length
          ? ([['Redemptions', `${coupon.redemptions.length} orders redeemed`]] as [string, string][])
          : []),
      ],
    });
  }

  async function showRefundOrderDetails(refund: AdminRefund): Promise<void> {
    const recentOrder = data?.recent_orders.find(order => order.id === refund.order);
    if (recentOrder) {
      showOrderDetails(recentOrder);
      return;
    }

    try {
      const order = await api<Order>(`orders/${refund.order}`);
      setDetail({
        title: `Order #${order.reference}`,
        rows: [
          ['Status', order.status],
          ['Payment method', order.payment_type.replaceAll('_', ' ')],
          ['Subtotal', money(order.subtotal)],
          ['Total', money(order.total)],
          ['Paid', money(order.paid_total)],
          ['Refunded', money(order.refunded_total)],
          ['Carrier', order.carrier || 'Not assigned'],
          ['Tracking number', order.tracking_number || 'Not assigned'],
          ['Items', `${order.items.length} items`],
          ['Created', activityDate(order.created)],
        ],
      });
    } catch (error) {
      notify((error as Error).message, true);
    }
  }

  async function overrideOrder(order: AdminDashboardData['recent_orders'][number], nextStatus: string) {
    if (nextStatus === order.status) return;
    const reason = await actionDialog.ask({ title: 'Update order status', message: `Change order #${order.orderId} from ${order.status} to ${nextStatus}?`, confirmLabel: 'Update status', reasonLabel: 'Reason' });
    if (reason === null) return;
    try {
      await api(`admin/staff/orders/${order.id}/status`, 'POST', { status: nextStatus, reason });
      notify(`Order #${order.orderId} changed to ${nextStatus}`);
      await refreshOperations();
    } catch (error) { notify((error as Error).message, true); }
  }

  if (sessionLoading) return <Loading />;
  if (!user) return <Empty title="Admin sign-in required" text="Sign in with a staff or administrator account to access platform insights." href="/login?next=/admin" label="Sign in" icon={<LockKeyhole size={36} />} />;
  if (!user.is_staff && !(user.is_superuser || user.is_business_admin)) return <Empty title="Staff access only" text="Your account does not have permission to view administrative dashboards." href="/account" label="Back to your account" icon={<ShieldAlert size={36} />} />;

  const data = dashboard.data;
  const statusCounts = data?.orders.by_status || [];
  const maxStatusCount = Math.max(1, ...statusCounts.map(s => s.count));

  return (
    <div className="container admin-dashboard-page section">
      <div className="admin-staff-heading">
        <div>
          <span className="eyebrow green">PLATFORM INTELLIGENCE</span>
          <h1>Admin & Staff Overview</h1>
          <p>Real-time platform commerce insights, store activity, and order fulfillment.</p>
        </div>
      </div>

      <div className="dashboard-period">
        <h2>Platform metrics at a glance</h2>
        <select aria-label="Dashboard period" value={days} onChange={event => setDays(event.target.value)}>
          <option value="7">Last 7 days</option>
          <option value="30">Last 30 days</option>
          <option value="90">Last 90 days</option>
          <option value="365">Last 365 days</option>
        </select>
      </div>

      {dashboard.isFetching && !dashboard.isLoading && <Loading compact overlay />}

      {dashboard.isLoading ? (
        <Loading />
      ) : dashboard.error ? (
        <ErrorState error={dashboard.error} retry={() => dashboard.refetch()} />
      ) : data && (
        <>
          <div className="stats-grid">
            {isAdmin && data.orders.gross_total != null && (
              <div className="stat-item stat-0">
                <div>
                  <span>Gross Platform Revenue</span>
                  <DollarSign size={19} />
                </div>
                <strong>{money(data.orders.gross_total)}</strong>
                <small>Paid orders over the last {days} days</small>
              </div>
            )}

            <div className="stat-item stat-1">
              <div>
                <span>Total Orders Placed</span>
                <Package size={19} />
              </div>
              <strong>{data.orders.total}</strong>
              <small>{data.orders.ordered} successfully paid orders</small>
            </div>

            <div className="stat-item stat-2">
              <div>
                <span>Registered Users</span>
                <UserRound size={19} />
              </div>
              <strong>{data.users.total}</strong>
              <small>+{data.users.new} new users in selected period</small>
            </div>

            <div className="stat-item stat-3">
              <div>
                <span>Active Merchant Stores</span>
                <Store size={19} />
              </div>
              <strong>{data.stores.active}</strong>
              <small>{data.stores.total} stores total · {data.stores.blocked} suspended</small>
            </div>

            {isAdmin && data.financials?.escrow_total != null && (
              <div className="stat-item stat-0">
                <div>
                  <span>Total Amount in Escrow</span>
                  <LockKeyhole size={19} />
                </div>
                <strong>{money(data.financials.escrow_total)}</strong>
                <small>Merchant funds awaiting release</small>
              </div>
            )}

            {isAdmin && data.financials?.commission_earned != null && (
              <div className="stat-item stat-1">
                <div>
                  <span>Total Commission Earned</span>
                  <DollarSign size={19} />
                </div>
                <strong>{money(data.financials.commission_earned)}</strong>
                <small>Platform fees recorded in the ledger</small>
              </div>
            )}

            <div className="stat-item stat-2">
              <div>
                <span>Pending Actions</span>
                <RotateCcw size={19} />
              </div>
              <strong>{data.pending_actions.withdrawals + data.pending_actions.refunds}</strong>
              <small>{data.pending_actions.withdrawals} withdrawals · {data.pending_actions.refunds} refunds/disputes</small>
            </div>

            <Link href="/admin/payouts?status=pending" className="stat-item stat-0">
              <div><span>Pending Payouts</span><Landmark size={19} /></div>
              <strong>{data.pending_actions.withdrawals}</strong>
              <small>Review merchant withdrawal requests</small>
            </Link>

            <div className="stat-item stat-3">
              <div>
                <span>Store Growth</span>
                <Store size={19} />
              </div>
              <strong>{data.stores.active}</strong>
              <small>{data.stores.new_last_30_days} new stores in the last 30 days</small>
            </div>
          </div>

          <section className="analytics-panel" style={{ marginTop: '2rem' }}>
            <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2>Affiliate & referral promotions</h2>
                <p>Customer acquisition invites, enrolled marketers, and wallet rewards.</p>
              </div>
              <Link href="/admin/affiliates" className="button secondary">
                View affiliates & referrals &rarr;
              </Link>
            </div>
            <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', marginTop: '1rem' }}>
              <div className="stat-item stat-0">
                <div>
                  <span>Total Referrals</span>
                  <UserRound size={19} />
                </div>
                <strong>{data.referrals?.total ?? 0}</strong>
                <small>Referred customer signups</small>
              </div>
              <div className="stat-item stat-1">
                <div>
                  <span>Rewarded Signups</span>
                  <Check size={19} />
                </div>
                <strong>{data.referrals?.rewarded ?? 0}</strong>
                <small>{data.referrals?.pending ?? 0} signups pending</small>
              </div>
              {isAdmin && data.referrals?.rewarded_amount != null && (
                <div className="stat-item stat-2">
                  <div>
                    <span>Promotional Credit Awarded</span>
                    <DollarSign size={19} />
                  </div>
                  <strong>{money(data.referrals.rewarded_amount)}</strong>
                  <small>Store credit in wallets</small>
                </div>
              )}
              <div className="stat-item stat-3">
                <div>
                  <span>Enrolled Affiliates</span>
                  <Share2 size={19} />
                </div>
                <strong>{data.marketers?.total ?? 0}</strong>
                <small>Active program marketers</small>
              </div>
            </div>
          </section>


          <div className="dashboard-columns" style={{ marginTop: '2rem' }}>
            <section className="analytics-panel">
              <div className="section-heading">
                <div>
                  <h2>Order status distribution</h2>
                  <p>Fulfillment pipeline breakdown over the selected timeframe</p>
                </div>
                <span className="chart-legend"><i />Orders</span>
              </div>

              {!statusCounts.length ? (
                <p className="muted" style={{ padding: '1rem 0' }}>No orders placed in this period.</p>
              ) : (
                <div className="bar-chart" role="img" aria-label="Order status chart">
                  <div className="chart-y">
                    <span>{maxStatusCount}</span>
                    <span>{Math.round(maxStatusCount / 2)}</span>
                    <span>0</span>
                  </div>
                  <div className="chart-bars">
                    {statusCounts.map(item => (
                      <div className="chart-column" key={item.status} title={`${item.status}: ${item.count} orders`}>
                        <span style={{ height: `${(item.count / maxStatusCount) * 100}%`, minHeight: item.count ? 6 : 1 }} />
                        <small style={{ fontSize: '0.75rem', textTransform: 'capitalize' }}>{item.status}</small>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>

            <section className="stock-panel">
              <div className="section-heading">
                <h2>Moderation & catalog health</h2>
              </div>
              <div className="stock-row" style={{ alignItems: 'center' }}>
                <span className="admin-stat-icon red"><RotateCcw size={19} /></span>
                <div>
                  <strong>Refund Requests</strong>
                  <small>{data.refunds.pending} pending review · {data.refunds.accepted} approved</small>
                </div>
              </div>

              <div className="stock-row" style={{ alignItems: 'center' }}>
                <span className="admin-stat-icon blue"><ShoppingBag size={19} /></span>
                <div>
                  <strong>Catalog Products</strong>
                  <small>{data.products.published} published · {data.products.out_of_stock} out of stock</small>
                </div>
              </div>

              <div className="stock-row" style={{ alignItems: 'center' }}>
                <span className="admin-stat-icon purple"><ChartNoAxesCombined size={19} /></span>
                <div>
                  <strong>Active Promotions</strong>
                  <small>{data.coupons.active} live coupons · {data.marketers.total} affiliates</small>
                </div>
              </div>
            </section>
          </div>

          <section className="analytics-panel" style={{ marginTop: '2rem' }}>
            <div className="section-heading">
              <div>
                <h2>Merchant payouts</h2>
                <p>{data.pending_actions.withdrawals} requests awaiting backoffice review</p>
              </div>
              <Link href="/admin/payouts" className="button secondary">View all payouts <ArrowRight size={16} /></Link>
            </div>
            {payouts.isLoading ? <Loading compact /> : payouts.error ? (
              <ErrorState error={payouts.error} retry={() => payouts.refetch()} />
            ) : !payouts.data?.results.length ? (
              <p className="muted">No merchant payout requests yet.</p>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead><tr><th>Reference</th><th>Store</th><th>Amount</th><th>Status</th><th>Requested</th></tr></thead>
                  <tbody>
                    {payouts.data.results.map(payout => (
                      <tr key={payout.id}>
                        <td>
                          <button
                            type="button"
                            className="text-link"
                            aria-label={`View payout ${payout.reference} details`}
                            onClick={() => setDetail(payoutDetail(payout))}
                          >
                            {payout.reference}
                          </button>
                        </td>
                        <td>{payout.store_name || 'Merchant wallet'}</td>
                        <td>{money(payout.amount)}</td>
                        <td><Status value={payout.status} /></td>
                        <td><DateStamp value={payout.created} dateOnly /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="merchant-section" style={{ marginTop: '2.5rem' }}>
            <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2>Top performing stores (All-time summary)</h2>
                <span className="muted">{data.scopes?.top_stores || 'Top 10 stores ranked by order volume'}</span>
              </div>
              <Link href="/admin/stores" className="button secondary">View all stores →</Link>
            </div>
            {!data.top_stores.length ? (
              <p className="muted">No store sales data yet.</p>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Store</th>
                      <th>Username</th>
                      <th>Status</th>
                      <th>Products</th>
                      <th>Orders Completed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_stores.slice(0, 5).map(store => (
                      <tr key={store.id}>
                        <td>
                          <Link className="text-link" href={`/admin/stores/${store.id}`}>
                            {store.name}
                          </Link>
                        </td>
                        <td>@{store.username}</td>
                        <td><Status value={store.status} /></td>
                        <td>{store.products} products</td>
                        <td><strong>{store.orders} orders</strong></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="merchant-section" style={{ marginTop: '2.5rem' }}>
            <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2>Recent platform orders (All-time summary)</h2>
                <span className="muted">Showing 5 recent orders</span>
              </div>
              <Link href="/admin/orders" className="button secondary">View all orders &rarr;</Link>
            </div>
            {!data.recent_orders.length ? (
              <p className="muted">No matching orders found.</p>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Order reference</th>
                      <th>Buyer</th>
                      <th>Status</th>
                      <th>Shipping / Tracking</th>
                      <th>Total</th>
                      <th>Created</th>
                      <th>Updated</th>
                      <th>Emergency action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_orders.slice(0, 5).map(order => (
                      <tr key={order.orderId}>
                        <td>
                          <button
                            type="button"
                            className="text-link"
                            aria-label={`View details for order ${order.orderId}`}
                            onClick={() => showOrderDetails(order)}
                          >
                            #{order.orderId}
                          </button>
                        </td>
                        <td>{order.buyer_email}</td>
                        <td><Status value={order.status} /></td>
                        <td>
                          {order.tracking_number ? (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.85rem' }}>
                              <Truck size={14} color="var(--green)" />
                              {order.carrier || 'USPS'}: {order.tracking_number}
                            </span>
                          ) : (
                            <span className="muted">Pending shipment</span>
                          )}
                        </td>
                        <td><strong>{money(order.total)}</strong></td>
                        <td><DateStamp value={order.created} /></td>
                        <td><DateStamp value={order.updated} /></td>
                        <td>
                          {(() => {
                            const isDigital = isOrderAllDigital(order);
                            return (
                              <select
                                aria-label={`Override status for order ${order.orderId}`}
                                value={order.status}
                                disabled={order.status === 'refunded' || order.status === 'cancelled' || (isDigital && order.status === 'delivered')}
                                title={isDigital && order.status === 'delivered' ? 'Digital orders are delivered electronically' : undefined}
                                onChange={event => void overrideOrder(order, event.target.value)}
                              >
                                {getOrderOverrideOptions(order.status, isDigital).map(value => (
                                  <option value={value} key={value}>{value}</option>
                                ))}
                              </select>
                            );
                          })()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <div className="dashboard-columns dashboard-operations" style={{ marginTop: '2rem' }}>
            <section className="analytics-panel">
              <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h2>Refund operations</h2>
                  <p>Latest requests. Open all refunds for search, filters, and full history.</p>
                </div>
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                  {refunds.data?.count !== undefined && <small className="muted">{refunds.data.count} total</small>}
                  <Link href="/admin/refunds" className="button secondary">
                    View all refunds &rarr;
                  </Link>
                </div>
              </div>
              {refunds.isFetching && !refunds.isLoading && <Loading compact overlay />}
              {refunds.isLoading ? (
                <Loading />
              ) : refunds.error ? (
                <ErrorState error={refunds.error} retry={() => refunds.refetch()} />
              ) : !refunds.data?.results.length ? (
                <p className="muted">No refund requests.</p>
              ) : (
                <div className="table-scroll dashboard-refund-table">
                  <table>
                    <caption className="sr-only">Latest refund requests</caption>
                    <thead>
                      <tr>
                        <th scope="col">Refund</th>
                        <th scope="col">Order</th>
                        <th scope="col">Customer</th>
                        <th scope="col">Amount</th>
                        <th scope="col">Method</th>
                        <th scope="col">Status</th>
                        <th scope="col">Processed by</th>
                        <th scope="col">Reason</th>
                        <th scope="col">Created</th>
                        <th scope="col">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {refunds.data.results.map(refund => (
                        <tr key={refund.id}>
                          <td>
                            <button
                              type="button"
                              className="text-link"
                              aria-label={`View details for refund ${refund.id}`}
                              onClick={() => showRefundDetails(refund)}
                            >
                              #{refund.id}
                            </button>
                          </td>
                          <td>
                            <button
                              type="button"
                              className="text-link"
                              aria-label={`View order ${refund.order} details`}
                              onClick={() => void showRefundOrderDetails(refund)}
                            >
                              #{refund.order}
                            </button>
                          </td>
                          <td>{refund.email}</td>
                          <td>{money(refund.refund_amount)}</td>
                          <td>{refund.refund_type.replaceAll('_', ' ')}</td>
                          <td><Status value={refund.status} /></td>
                          <td>{refund.processed_by_email || '—'}</td>
                          <td className="refund-reason">{refund.reason}</td>
                          <td><DateStamp value={refund.created} /></td>
                          <td>
                            {(refund.status === 'pending' || refund.status === 'failed') ? (
                              <div className="form-actions">
                                <button
                                  type="button"
                                  className="button compact"
                                  onClick={() => void processRefund(refund, 'approve')}
                                >
                                  {refund.status === 'failed' ? 'Retry approve' : 'Approve'}
                                </button>
                                <button
                                  type="button"
                                  className="button secondary compact"
                                  onClick={() => void processRefund(refund, 'decline')}
                                >
                                  Decline
                                </button>
                              </div>
                            ) : (
                              <button
                                type="button"
                                className="button secondary compact"
                                onClick={() => showRefundDetails(refund)}
                              >
                                Details
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
            <section className="analytics-panel">
              <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div><h2>Coupon operations</h2><p>Deactivate immediately, or delete coupons with no redemption history.</p></div>
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                  {coupons.data?.count !== undefined && <small className="muted">{coupons.data.count} total</small>}
                  <Link href="/admin/coupons" className="button secondary">View all coupons &rarr;</Link>
                </div>
              </div>
              {coupons.isFetching && !coupons.isLoading && <Loading compact overlay />}
              {coupons.isLoading ? (
                <Loading />
              ) : coupons.error ? (
                <ErrorState error={coupons.error} retry={() => coupons.refetch()} />
              ) : !coupons.data?.results.length ? (
                <p className="muted">No coupons configured.</p>
              ) : (
                <div className="table-scroll dashboard-coupon-table">
                  <table>
                    <caption className="sr-only">Latest coupons</caption>
                    <thead>
                      <tr>
                        <th scope="col">Code</th>
                        <th scope="col">Discount</th>
                        <th scope="col">Usage</th>
                        <th scope="col">Status</th>
                        <th scope="col">Valid from</th>
                        <th scope="col">Valid to</th>
                        <th scope="col">Created by</th>
                        <th scope="col">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {coupons.data.results.map(coupon => (
                        <tr key={coupon.id}>
                          <td>
                            <button
                              type="button"
                              className="text-link"
                              aria-label={`View details for coupon ${coupon.code}`}
                              onClick={() => showCouponDetails(coupon)}
                            >
                              {coupon.code}
                            </button>
                          </td>
                          <td>{coupon.discount}% off</td>
                          <td>{coupon.num_used} / {coupon.num_available}</td>
                          <td><Status value={coupon.active ? 'active' : 'inactive'} /></td>
                          <td><DateStamp value={coupon.valid_from} dateOnly /></td>
                          <td><DateStamp value={coupon.valid_to} dateOnly /></td>
                          <td>{coupon.created_by || 'Not recorded'}</td>
                          <td>
                            <div className="form-actions">
                              <button
                                type="button"
                                className="button secondary compact"
                                onClick={() => void setCoupon(coupon, 'toggle')}
                              >
                                {coupon.active ? 'Deactivate' : 'Reactivate'}
                              </button>
                              <button
                                type="button"
                                className="icon-button"
                                aria-label={coupon.num_used > 0
                                  ? `Used coupon ${coupon.code} cannot be deleted (click to see reason)`
                                  : `Delete unused coupon ${coupon.code}`}
                                title={coupon.num_used > 0
                                  ? 'Used coupons cannot be deleted to preserve order records. Click for details.'
                                  : 'Delete unused coupon'}
                                onClick={() => void setCoupon(coupon, 'delete')}
                              >
                                <Trash2 size={16} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>


          <DashboardDetailDialog detail={detail} onClose={() => setDetail(null)} />
          {actionDialog.dialog}
          {user.is_superuser && <section className="analytics-panel" style={{ marginTop: '2rem' }}>
            <div className="section-heading">
              <div>
                <h2>System Telemetry & Monitoring (Grafana)</h2>
                <p>Live server health, database connection pools, response latencies, and container logs.</p>
              </div>
              <span className="status active" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                <Activity size={13} /> Technical admin only
              </span>
            </div>
            <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', marginTop: '1rem' }}>
              <a
                href={`${process.env.NEXT_PUBLIC_GRAFANA_URL || 'http://127.0.0.1:3002'}/d/commerce-overview/commerce-api-overview`}
                target="_blank"
                rel="noreferrer"
                className="stat-item stat-0"
                style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600 }}>API Overview Dashboard</span>
                  <ArrowUpRight size={17} />
                </div>
                <strong style={{ fontSize: '1.2rem', marginTop: '0.5rem', display: 'block' }}>HTTP & DB Traffic</strong>
                <small>Request rates, p95/p99 latency, error rates, and query durations</small>
              </a>

              <a
                href={`${process.env.NEXT_PUBLIC_GRAFANA_URL || 'http://127.0.0.1:3002'}/d/commerce-infrastructure/commerce-infrastructure`}
                target="_blank"
                rel="noreferrer"
                className="stat-item stat-1"
                style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600 }}>Infrastructure & DB</span>
                  <ArrowUpRight size={17} />
                </div>
                <strong style={{ fontSize: '1.2rem', marginTop: '0.5rem', display: 'block' }}>Postgres & Redis</strong>
                <small>Connection pools, memory usage, CPU load, and Elasticsearch</small>
              </a>

              <a
                href={`${process.env.NEXT_PUBLIC_GRAFANA_URL || 'http://127.0.0.1:3002'}/explore`}
                target="_blank"
                rel="noreferrer"
                className="stat-item stat-2"
                style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600 }}>Loki Central Logs</span>
                  <ArrowUpRight size={17} />
                </div>
                <strong style={{ fontSize: '1.2rem', marginTop: '0.5rem', display: 'block' }}>Log Explorer</strong>
                <small>Search live structured JSON logs and container stderr in real time</small>
              </a>
            </div>
          </section>}
        </>
      )}
    </div>
  );
}

export function AdminUsersPage() {
  const { user, sessionLoading, notify } = useShop();
  const filters = useCollectionFilters();
  const actionDialog = useActionDialog();
  const client = useQueryClient();

  const users = useQuery({
    queryKey: ['admin', 'users', filters.query, user?.id],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey.at(-1) === user?.id ? previousData : undefined,
    queryFn: () => api<Page<StaffUser>>(`admin/staff/users?${filters.query}`),
    enabled: Boolean(user?.is_staff || user?.is_superuser || user?.is_business_admin),
  });

  async function toggleStatus(target: StaffUser) {
    const nextActive = !target.is_active;
    const actionLabel = nextActive ? 'Reactivate' : 'Block / Deactivate';
    const confirmed = await actionDialog.ask({
      title: `${actionLabel} user`,
      message: `${actionLabel} account for ${target.email}?`,
      confirmLabel: actionLabel,
    });
    if (confirmed === null) return;

    try {
      await api(`admin/staff/users/${target.id}`, 'PATCH', { is_active: nextActive });
      notify(`User ${target.email} is now ${nextActive ? 'active' : 'blocked'}.`);
      await client.invalidateQueries({ queryKey: ['admin', 'users'] });
    } catch (err) {
      notify((err as Error).message, true);
    }
  }

  if (sessionLoading) return <Loading />;
  if (!user || (!user.is_staff && !user.is_superuser && !user.is_business_admin)) {
    return <Empty title="Backoffice access required" text="Only staff and administrators can view platform users." href="/admin" label="Back to dashboard" />;
  }

  const results = users.data?.results || [];

  return (
    <div className="container admin-staff-page section">
      <div className="admin-staff-heading">
        <div>
          <span className="eyebrow green">PLATFORM DIRECTORY</span>
          <h1>Customer & User Directory</h1>
          <p>Search accounts, inspect spending and order histories, and manage access.</p>
        </div>
        <Link className="button secondary" href="/admin">Platform Dashboard</Link>
      </div>

      <CollectionFilters filters={filters} label="users" reserveStatusSpace fields={[
        { key: 'role', label: 'Role', options: [{ value: 'customer', label: 'Customer' }, ...(user.is_superuser || user.is_business_admin ? [{ value: 'staff', label: 'Staff' }, { value: 'admin', label: 'Admin' }] : [])] },
        { key: 'is_active', label: 'Account state', options: [{ value: 'true', label: 'Active' }, { value: 'false', label: 'Blocked' }] },
      ]} />
      {typeof users.data?.count === 'number' && (
        <CollectionCount count={users.data.count} />
      )}
      {users.isFetching && !users.isLoading && <Loading compact overlay />}

      {users.isLoading ? (
        <Loading />
      ) : users.error ? (
        <ErrorState error={users.error} retry={() => users.refetch()} />
      ) : !results.length ? (
        <Empty title="No users found" text={filters.active ? "No accounts match your filters." : "No accounts registered yet."} />
      ) : (
        <>
          <div className="admin-staff-table table-scroll">
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Phone</th>
                  <th>Role</th>
                  <th>Joined</th><th>Last active</th><th>Last login</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {results.map(member => (
                  <tr key={member.id}>
                    <td>
                      <Link
                        className="admin-staff-person admin-staff-person-link"
                        href={`/admin/users/${member.id}`}
                        aria-label={`View profile of ${`${member.first_name} ${member.last_name}`.trim() || member.email}`}
                      >
                        {member.avatar_url ? (
                          <ResponsiveMediaImage
                            src={member.avatar_url}
                            alt={member.first_name || member.email}
                            fallback={<span>{member.first_name?.[0] || member.email[0]}</span>}
                            style={{ width: 36, height: 36, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }}
                            sizes="36px"
                            width={72}
                            height={72}
                          />
                        ) : (
                          <span>{member.first_name?.[0] || member.email[0]}</span>
                        )}
                        <div>
                          <strong>{`${member.first_name} ${member.last_name}`.trim() || 'Unnamed user'}</strong>
                          <small>{member.email}</small>
                        </div>
                      </Link>
                    </td>
                    <td>{member.phone1 || '—'}</td>
                    <td><span className="status">{member.role.replace('_', ' ')}</span></td>
                    <td><DateStamp value={member.date_joined} dateOnly /></td><td><DateStamp value={member.last_active_at} /></td><td><DateStamp value={member.last_login} /></td>
                    <td><Status value={member.is_active ? 'active' : 'blocked'} /></td>
                    <td>
                      <div className="form-actions" style={{ display: 'flex', gap: '0.35rem' }}>
                        {(user.is_superuser || user.is_business_admin || (!member.is_staff && !member.is_superuser && !member.is_business_admin)) && (
                          <button
                            className="button secondary"
                            style={{
                              padding: '0.3rem 0.65rem',
                              fontSize: '0.8rem',
                              color: member.is_active ? 'var(--red, #e11d48)' : 'var(--green, #10b981)',
                            }}
                            onClick={() => toggleStatus(member)}
                          >
                            {member.is_active ? 'Block' : 'Activate'}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <CollectionPagination filters={filters} count={users.data?.count || 0} />
        </>
      )}

      {actionDialog.dialog}
    </div>
  );
}

export function AdminUserDetailPage({ id }: { id: string }) {
  const { user, sessionLoading, notify } = useShop();
  const client = useQueryClient();
  const actionDialog = useActionDialog();
  const ledgerFilters = useCollectionFilters();
  const [orderSearch, setOrderSearch] = useState('');
  const [orderStatus, setOrderStatus] = useState('');

  const [orderCarrier, setOrderCarrier] = useState<string>('');
  const [orderPayment, setOrderPayment] = useState<string>('');
  const [orderOrdering, setOrderOrdering] = useState<string>('-created');
  const [orderOffset, setOrderOffset] = useState<number>(0);
  const [debouncedOrderSearch, setDebouncedOrderSearch] = useState<string>('');

  useEffect(() => {
    const timeout = setTimeout(() => {
      setDebouncedOrderSearch(orderSearch.trim());
      setOrderOffset(0);
    }, 300);
    return () => clearTimeout(timeout);
  }, [orderSearch]);

  const orderFiltersActive: boolean = Boolean(orderSearch || orderStatus || orderCarrier || orderPayment || orderOrdering !== '-created');

  function resetOrderFilters(): void {
    setOrderSearch('');
    setDebouncedOrderSearch('');
    setOrderStatus('');
    setOrderCarrier('');
    setOrderPayment('');
    setOrderOrdering('-created');
    setOrderOffset(0);
  }

  const query = new URLSearchParams({

    order_search: debouncedOrderSearch,
    order_carrier: orderCarrier,
    order_payment: orderPayment,
    order_ordering: orderOrdering,
    order_offset: String(orderOffset),
    order_status: orderStatus,
  });

  for (const [key, value] of new URLSearchParams(ledgerFilters.query)) {
    query.set(`ledger_${key}`, value);
  }

  const profile = useQuery({
    queryKey: ['admin', 'user', id, ledgerFilters.query, debouncedOrderSearch, orderStatus, orderCarrier, orderPayment, orderOrdering, orderOffset, user?.id],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[2] === id
        && previousQuery.queryKey.at(-1) === user?.id
        ? previousData
        : undefined,
    queryFn: () => api<AdminUserProfile>(`admin/staff/users/${id}?${query}`),
    enabled: Boolean(user?.is_staff || user?.is_superuser || user?.is_business_admin),
  });

  async function toggleUserStatus(target: StaffUser) {
    const nextActive = !target.is_active;
    const actionLabel = nextActive ? 'Reactivate' : 'Block / Deactivate';
    const confirmed = await actionDialog.ask({
      title: `${actionLabel} user`,
      message: `${actionLabel} account for ${target.email}?`,
      confirmLabel: actionLabel,
    });
    if (confirmed === null) return;

    try {
      await api(`admin/staff/users/${target.id}`, 'PATCH', { is_active: nextActive });
      notify(`User ${target.email} is now ${nextActive ? 'active' : 'blocked'}.`);
      await client.invalidateQueries({ queryKey: ['admin', 'user', id] });
    } catch (err) {
      notify((err as Error).message, true);
    }
  }

  if (sessionLoading || profile.isLoading) return <Loading />;
  if (!user || (!user.is_staff && !user.is_superuser && !user.is_business_admin)) {
    return <Empty title="Backoffice access required" text="Only staff and administrators can view user profiles." href="/admin" label="Back to dashboard" />;
  }
  if (profile.error) return <ErrorState error={profile.error} retry={() => profile.refetch()} />;

  const data = profile.data!;


  return (
    <div className="container admin-staff-page admin-user-detail section">
      <Link className="text-link" href="/admin/users">
        <ArrowLeft size={16} />
        All users
      </Link>

      {profile.isFetching && !profile.isLoading && <Loading compact overlay />}

      <section className="admin-profile-card">
        <div className="admin-profile-identity">
          {data.user.avatar_url ? (
            <ResponsiveMediaImage
              src={data.user.avatar_url}
              alt={data.user.first_name || data.user.email}
              fallback={(
                <div className="admin-user-profile-avatar-fallback">
                  {data.user.first_name?.[0]?.toUpperCase() || data.user.email[0]?.toUpperCase()}
                </div>
              )}
              className="admin-user-profile-avatar"
              sizes="120px"
              width={240}
              height={240}
            />
          ) : (
            <div className="admin-user-profile-avatar-fallback">
              {data.user.first_name?.[0]?.toUpperCase() || data.user.email[0]?.toUpperCase()}
            </div>
          )}
          <div>
            <span className="eyebrow green">USER PROFILE</span>
            <h1>{`${data.user.first_name} ${data.user.last_name}`.trim() || data.user.email}</h1>
            <p>{data.user.email} · {data.user.role.replace('_', ' ')} · Joined <DateStamp value={data.user.date_joined} dateOnly /></p>
          </div>
        </div>
        <div className="admin-profile-actions">
          <Status value={data.user.is_active ? 'active' : 'blocked'} />
          {(user.is_superuser || user.is_business_admin || (!data.user.is_staff && !data.user.is_superuser && !data.user.is_business_admin)) && (
            <button
              className="button secondary"
              style={{ color: data.user.is_active ? 'var(--red, #e11d48)' : 'var(--green, #10b981)' }}
              onClick={() => toggleUserStatus(data.user)}
            >
              {data.user.is_active ? 'Block account' : 'Activate account'}
            </button>
          )}
        </div>
        <div className="admin-profile-details">
          <ActivityDetails {...data.user} />
          <div className="admin-profile-contact">
            <span>Contact number</span>
            <strong>{data.user.phone1 || 'Not provided'}</strong>
            {data.user.phone2 && <small>Alternate: {data.user.phone2}</small>}
          </div>
        </div>
      </section>

      <div className="stats-grid admin-profile-stats">
        <div className="stat-item stat-0">
          <span>Wallet balance</span>
          <strong>{money(data.wallet.balance)}</strong>
          <small>Available store credit</small>
        </div>
        <div className="stat-item stat-1">
          <span>Total orders placed</span>
          <strong>{data.total_orders}</strong>
          <small>Recorded checkout orders</small>
        </div>
        <div className="stat-item stat-2">
          <span>Estimated lifetime spend</span>
          <strong>{money(data.lifetime_spent)}</strong>
          <small>Excluding cancelled orders</small>
        </div>
      </div>

      {(data.referral || data.affiliate) && (
        <section className="analytics-panel" style={{ marginTop: '1.5rem', marginBottom: '1.5rem' }}>
          <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h2>Affiliate & referral attribution</h2>
              <p>Program membership and invitation history for this account.</p>
            </div>
            <Link href="/admin/affiliates" className="button secondary">
              All referrals &rarr;
            </Link>
          </div>
          <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
            {data.referral && (
              <div className="stat-item stat-0" style={{ textAlign: 'left' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Referred By</span>
                  <Share2 size={16} />
                </div>
                <strong style={{ display: 'block', margin: '0.25rem 0' }}>{data.referral.referrer_name}</strong>
                <small>
                  <Link href={`/admin/users/${data.referral.referrer_user_id}`}>
                    {data.referral.referrer_email}
                  </Link> · Code: <strong>{data.referral.referrer_code}</strong>
                </small>
                <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <Status value={data.referral.status} />
                  <small className="muted">{money(data.referral.reward_amount)} credit</small>
                  <small className="muted">· <DateStamp value={data.referral.created} dateOnly /></small>
                </div>
              </div>
            )}
            {data.affiliate && (
              <div className="stat-item stat-1" style={{ textAlign: 'left' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Enrolled Affiliate Marketer</span>
                  <UserRound size={16} />
                </div>
                <strong style={{ display: 'block', margin: '0.25rem 0' }}>{data.affiliate.name} (Code: {data.affiliate.referral_code})</strong>
                <small>
                  {data.affiliate.referral_count} referred users ({data.affiliate.rewarded_count} rewarded)
                </small>
                <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600, color: 'var(--green)' }}>
                    {money(data.affiliate.credit_earned)} earned
                  </span>
                  <small className="muted">· Joined <DateStamp value={data.affiliate.created} dateOnly /></small>
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      <div className="user-profile-columns">
        <div className="analytics-panel">
          <div className="section-heading">
            <h2>Wallet ledger</h2>
          </div>
          <CollectionFilters filters={ledgerFilters} label="profile wallet ledger" fields={[
            { key: 'type', label: 'Type', options: [{ value: 'credit', label: 'Credit' }, { value: 'debit', label: 'Debit' }] },
            { key: 'source', label: 'Source' },
            ...financialFields,
          ]} />
          {typeof data.wallet.count === 'number' && (
            <CollectionCount count={data.wallet.count} />
          )}
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Created</th>
                  <th>Type</th>
                  <th>Source</th>
                  <th>Description</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {!data.wallet.transactions.length ? (
                  <tr><td colSpan={5} style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--muted)' }}>{ledgerFilters.active ? 'No transactions match your filters.' : 'No transactions yet.'}</td></tr>
                ) : (
                  data.wallet.transactions.map(tx => (
                    <tr key={tx.id}>
                      <td><DateStamp value={tx.created} dateOnly /></td>
                      <td><Status value={tx.type} /></td>
                      <td>{tx.source}</td>
                      <td>{tx.description}</td>
                      <td style={{ fontWeight: 600, color: tx.type === 'credit' ? 'var(--green)' : 'var(--ink)' }}>
                        {tx.type === 'credit' ? `+${money(tx.amount)}` : `-${money(tx.amount)}`}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <CollectionPagination filters={ledgerFilters} count={data.wallet.count} />
        </div>

        <div className="analytics-panel">
          <h2>Activity timeline</h2>
          {!data.activity.length ? (
            <p className="muted" style={{ padding: '1rem 0' }}>No recent activity records.</p>
          ) : (
            data.activity.map(item => (
              <div className="stock-row" key={item.id}>
                <div>
                  <strong>{item.verb.replaceAll('_', ' ')}</strong>
                  {item.description && <small style={{ display: 'block' }}>{item.description}</small>}
                </div>
                <small><DateStamp value={item.created} dateOnly /></small>
              </div>
            ))
          )}
        </div>
      </div>

      <section className="merchant-section admin-profile-orders">
        <div className="section-heading">
          <h2>Order history</h2>
          <div className="form-actions admin-profile-filters">
            <input
              aria-label="Search profile orders"
              placeholder="Search reference, coupon, courier, tracking…"
              value={orderSearch}
              onChange={e => setOrderSearch(e.target.value)}
            />
            <select
              aria-label="Filter orders by status"
              value={orderStatus}
              onChange={e => {
                setOrderStatus(e.target.value);
                setOrderOffset(0);
              }}
            >
              <option value="">All statuses</option>
              {['pending', 'confirmed', 'shipped', 'delivered', 'picked up', 'cancelled', 'refunded'].map(status => (
                <option key={status} value={status}>{status}</option>
              ))}
            </select>
            <select
              aria-label="Filter orders by courier"
              value={orderCarrier}
              onChange={e => {
                setOrderCarrier(e.target.value);
                setOrderOffset(0);
              }}
            >
              <option value="">All couriers</option>
              {['USPS', 'UPS', 'FEDEX', 'DHL', 'DIGITAL'].map(carrier => (
                <option key={carrier} value={carrier}>{carrier === 'DIGITAL' ? 'Digital / Instant' : carrier}</option>
              ))}
            </select>
            <select
              aria-label="Filter orders by payment method"
              value={orderPayment}
              onChange={e => {
                setOrderPayment(e.target.value);
                setOrderOffset(0);
              }}
            >
              <option value="">All payment methods</option>
              <option value="card">Card</option>
              <option value="wallet">ProAce Wallet</option>
              <option value="cash_on_delivery">Cash on Delivery</option>
              <option value="stripe_wallet">Stripe Wallet</option>
            </select>
            <select
              aria-label="Sort orders"
              value={orderOrdering}
              onChange={e => {
                setOrderOrdering(e.target.value);
                setOrderOffset(0);
              }}
            >
              <option value="-created">Newest first</option>
              <option value="created">Oldest first</option>
              <option value="-total">Total: High to low</option>
              <option value="total">Total: Low to high</option>
            </select>
            {orderFiltersActive && (
              <button
                type="button"
                className="button secondary"
                onClick={resetOrderFilters}
              >
                Reset filters
              </button>
            )}
          </div>
        </div>
        <p className="muted">{data.order_count} matching orders{orderFiltersActive ? ' · Filters active' : ''}</p>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Order</th>
                <th>Created</th>
                <th>Updated</th>
                <th>Status</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {!data.orders.length ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--muted)' }}>
                    {orderFiltersActive
                      ? 'No orders match your filters. Clear filters to see all orders.'
                      : 'This user has not placed any orders.'}
                  </td>
                </tr>
              ) : (
                data.orders.map(order => (
                  <tr key={order.id}>
                    <td><strong>{order.reference}</strong></td>
                    <td><DateStamp value={order.created} /></td>
                    <td><DateStamp value={order.updated} /></td>
                    <td><Status value={order.status} /></td>
                    <td><strong>{money(order.total)}</strong></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {data.order_count > 15 && (
          <div className="form-actions">
            <button
              type="button"
              className="button secondary"
              disabled={orderOffset === 0 || profile.isFetching}
              onClick={() => setOrderOffset(Math.max(0, orderOffset - 15))}
            >
              Previous
            </button>
            <span>Page {Math.floor(orderOffset / 15) + 1} of {Math.ceil(data.order_count / 15)}</span>
            <button
              type="button"
              className="button secondary"
              disabled={orderOffset + 15 >= data.order_count || profile.isFetching}
              onClick={() => setOrderOffset(orderOffset + 15)}
            >
              Next
            </button>
          </div>
        )}
      </section>

      {actionDialog.dialog}
    </div>
  );
}

export function AdminPayoutsPage() {
  const { user, sessionLoading, notify } = useShop();
  const filters = useCollectionFilters();
  const [detail, setDetail] = useState<DashboardDetail | null>(null);
  const actionDialog = useActionDialog();
  const [selectedPayout, setSelectedPayout] = useState<StorePayout | null>(null);
  const [processing, setProcessing] = useState<boolean>(false);
  const client = useQueryClient();
  const clearNotificationDetail = useNotificationDetail<StorePayout>('payout', 'admin/staff/payouts', payout => {
    setSelectedPayout(payout);
    setDetail(payoutDetail(payout));
  });

  const payouts = useQuery({
    queryKey: ['admin', 'payouts', filters.query, user?.id],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey.at(-1) === user?.id ? previousData : undefined,
    queryFn: () => api<Page<StorePayout>>(`admin/staff/payouts?${filters.query}`),
    enabled: Boolean(user?.is_staff || user?.is_superuser || user?.is_business_admin),
  });

  async function handleProcess(payout: StorePayout, action: 'approve' | 'reject') {
    const reason = await actionDialog.ask({
      title: `${action === 'approve' ? 'Approve' : 'Reject'} Payout #${payout.reference}`,
      message: action === 'approve'
        ? `${payout.payout_method === 'stripe_connect' ? 'Send a Stripe Connect transfer' : 'Confirm the bank transfer has already been sent'} of ${money(payout.amount)} for ${payout.store_name || 'the merchant wallet'}?`
        : `Provide a reason for declining this payout request.`,
      confirmLabel: action === 'approve' ? (payout.payout_method === 'stripe_connect' ? 'Approve & transfer' : 'Mark bank transfer completed') : 'Reject payout',
      reasonLabel: action === 'reject' ? 'Reason for rejection' : undefined,
    });
    if (reason === null) return;

    setProcessing(true);
    try {
      await api(`admin/staff/payouts/${payout.id}/process`, 'POST', {
        action,
        ...(action === 'reject' ? { reason } : {}),
      });
      notify(`Payout #${payout.reference} ${action === 'approve' ? 'approved' : 'rejected'}.`);
      await client.invalidateQueries({ queryKey: ['admin', 'payouts'] });
      await client.invalidateQueries({ queryKey: ['admin', 'dashboard'] });
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setProcessing(false);
    }
  }

  if (sessionLoading) return <Loading />;
  if (!user || (!user.is_staff && !user.is_superuser && !user.is_business_admin)) {
    return <Empty title="Backoffice access required" text="Only staff and administrators can review merchant payouts." href="/admin" label="Back to dashboard" />;
  }

  const items = payouts.data?.results || [];

  return (
    <div className="container admin-staff-page section">
      <div className="admin-staff-heading">
        <div>
          <span className="eyebrow green">MERCHANT SETTLEMENTS</span>
          <h1>Merchant Payout Approvals</h1>
          <p>Staff and administrators process withdrawals. Stripe Connect transfers run on approval; bank transfers must be sent externally before marking them completed.</p>
        </div>
        <Link className="button secondary" href="/admin">Platform Dashboard</Link>
      </div>

      <CollectionFilters
        filters={filters}
        label="payouts"
        fields={[{ key: 'status', label: 'Status', options: [{ value: 'pending', label: 'Pending' }, { value: 'completed', label: 'Completed' }, { value: 'rejected', label: 'Rejected' }] }, { key: 'payout_method', label: 'Method', options: [{ value: 'bank_transfer', label: 'Bank transfer' }, { value: 'stripe_connect', label: 'Stripe Connect' }] }, ...financialFields]}
      />
      {typeof payouts.data?.count === 'number' && (
        <CollectionCount count={payouts.data.count} />
      )}

      {payouts.isFetching && !payouts.isLoading && <Loading compact overlay />}

      {payouts.isLoading ? (
        <Loading />
      ) : payouts.error ? (
        <ErrorState error={payouts.error} retry={() => payouts.refetch()} />
      ) : !items.length ? (
        <Empty
          title="No payouts found"
          text={filters.active ? 'No payouts match your filters.' : 'No merchant payout requests yet.'}
          label={filters.active ? 'Reset filters' : 'Refresh payouts'}
          onAction={filters.active ? filters.reset : () => { void payouts.refetch(); }}
        />
      ) : (
        <>
          <div className="admin-staff-table table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Reference</th>
                  <th>Store</th>
                  <th>Amount</th>
                  <th>Method</th>
                  <th>Bank</th>
                  <th>Bank account</th>
                  <th>Routing</th>
                  <th>Requested</th>
                  <th>Processed</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map(payout => (
                  <tr key={payout.id}>
                    <td>
                      <button
                        type="button"
                        className="text-link"
                        aria-label={`View payout ${payout.reference} details`}
                        onClick={() => {
                          setSelectedPayout(payout);
                          setDetail(payoutDetail(payout));
                        }}
                      >
                        {payout.reference}
                      </button>
                    </td>
                    <td>{payout.store_name || (payout.store ? `Store #${payout.store}` : 'Merchant Wallet')}</td>
                    <td><strong>{money(payout.amount)}</strong></td>
                    <td><span className="status">{payout.payout_method.replace('_', ' ')}</span></td>
                    <td>{String(payout.account_details?.bank_name || '—')}</td>
                    <td>{payoutAccountField('account_number', payout.account_details?.account_number || payout.account_details?.account_last4 || '').at(1) || '—'}</td>
                    <td>{payoutAccountField('routing_number', payout.account_details?.routing_number || payout.account_details?.routing_last4 || '').at(1) || '—'}</td>
                    <td><DateStamp value={payout.created} dateOnly /></td>
                    <td><DateStamp value={payout.processed_at} dateOnly /></td>
                    <td><Status value={payout.status} /></td>
                    <td>
                      {payout.status === 'pending' && (
                        Boolean(user && (user.is_staff || user.is_superuser || user.is_business_admin)) ? (
                          <div className="form-actions admin-payout-actions">
                            <button
                              className="button compact"
                              disabled={processing}
                              onClick={() => void handleProcess(payout, 'approve')}
                            >
                              {payout.payout_method === 'stripe_connect' ? 'Pay out' : 'Mark paid'}
                            </button>
                            <button
                              className="button secondary compact danger"
                              disabled={processing}
                              onClick={() => void handleProcess(payout, 'reject')}
                            >
                              Decline
                            </button>
                          </div>
                        ) : (
                          <small className="muted">Admin review required</small>
                        )
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <CollectionPagination filters={filters} count={payouts.data?.count || 0} />
        </>
      )}

      <DashboardDetailDialog
        detail={detail}
        onClose={() => {
          setDetail(null);
          clearNotificationDetail();
        }}
        actions={selectedPayout?.status === 'pending' ? (
          <>
            <button type="button" className="button" disabled={processing} onClick={() => {
              setDetail(null);
              void handleProcess(selectedPayout, 'approve');
            }}>
              {selectedPayout.payout_method === 'stripe_connect' ? 'Pay out' : 'Mark paid'}
            </button>
            <button type="button" className="button secondary" disabled={processing} onClick={() => {
              setDetail(null);
              void handleProcess(selectedPayout, 'reject');
            }}>
              Decline
            </button>
          </>
        ) : undefined}
      />
      {actionDialog.dialog}
    </div>
  );
}


export function AdminStaffPage() {
  const { user, sessionLoading, notify } = useShop();
  const client = useQueryClient();
  const filters = useCollectionFilters();
  const search = filters.search;
  const [adding, setAdding] = useState(false);
  const [selectedStaff, setSelectedStaff] = useState<StaffUser | null>(null);
  const staff = useQuery({
    queryKey: ['admin', 'staff', filters.query, user?.id],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey.at(-1) === user?.id ? previousData : undefined,
    queryFn: () => api<Page<StaffUser>>(`admin/staff?${filters.query}`),
    enabled: !!(user?.is_superuser || user?.is_business_admin),
  });
  const statusAction = useMutation({
    mutationFn: ({ id, action }: { id: number; action: 'block' | 'unblock' }) => api<StaffUser>(`admin/staff/${id}/${action}`, 'POST', {}),
    onSuccess: async (_, variables) => {
      await client.invalidateQueries({ queryKey: ['admin', 'staff'] });
      notify(`Staff member ${variables.action === 'block' ? 'blocked' : 'unblocked'}`);
    },
    onError: error => notify((error as Error).message, true),
  });
  const resendVerification = useMutation({
    mutationFn: (id: number) => api(`admin/staff/${id}/resend-verification`, 'POST', {}),
    onSuccess: () => notify('A fresh verification email has been queued'),
    onError: error => notify((error as Error).message, true),
  });

  if (sessionLoading) return <Loading />;
  if (!user) return <Empty title="Admin sign-in required" text="Sign in with an administrator account to manage staff." href="/login?next=/admin/staff" label="Sign in" icon={<LockKeyhole size={36} />} />;
  if (!(user.is_superuser || user.is_business_admin)) return <Empty title="Administrator access only" text="Your account does not have permission to add, block, or unblock staff." href="/account" label="Back to your account" icon={<ShieldAlert size={36} />} />;

  const rows = staff.data?.results || [];
  return (
    <div className="container admin-staff-page section">
      <div className="admin-staff-heading">
        <div>
          <span className="eyebrow green">ADMINISTRATION</span>
          <h1>Staff management</h1>
          <p>Add trusted team members and control their access.</p>
        </div>
        <button className="button" onClick={() => setAdding(true)}>
          <Plus size={17} />
          Add staff
        </button>
      </div>
      <CollectionFilters filters={filters} label="staff" fields={[
        { key: 'is_active', label: 'Account state', options: [{ value: 'true', label: 'Active' }, { value: 'false', label: 'Blocked' }] },
        { key: 'staff_email_verified', label: 'Email verification', options: [{ value: 'true', label: 'Verified' }, { value: 'false', label: 'Unverified' }] },
      ]} />
      {typeof staff.data?.count === 'number' && (
        <CollectionCount count={staff.data.count} />
      )}
      {staff.isFetching && !staff.isLoading && <Loading compact overlay />}
      {staff.isLoading ? (
        <Loading />
      ) : staff.error ? (
        <ErrorState error={staff.error} retry={() => staff.refetch()} />
      ) : rows.length ? (
        <>
          <div className="admin-staff-table table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Staff member</th>
                  <th>Joined</th><th>Last active</th><th>Last login</th>
                  <th>Status</th>
                  <th>Access</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(member => (
                  <tr key={member.id}>
                    <td>
                      <Link
                        className="admin-staff-person admin-staff-person-link"
                        href={`/admin/users/${member.id}`}
                        aria-label={`View profile of ${`${member.first_name} ${member.last_name}`.trim() || member.email}`}
                      >
                        {member.avatar_url ? (
                          <ResponsiveMediaImage
                            src={member.avatar_url}
                            alt={member.first_name || member.email}
                            fallback={<span>{member.first_name?.[0] || member.email[0]}</span>}
                            style={{ width: 32, height: 32, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }}
                            sizes="32px"
                            width={64}
                            height={64}
                          />
                        ) : (
                          <span>{member.first_name?.[0] || member.email[0]}</span>
                        )}
                        <div>
                          <strong>{`${member.first_name} ${member.last_name}`.trim() || 'Staff member'}</strong>
                          <small>{member.email}</small>
                        </div>
                      </Link>
                    </td>
                    <td><DateStamp value={member.date_joined} dateOnly /></td><td><DateStamp value={member.last_active_at} /></td><td><DateStamp value={member.last_login} /></td>
                    <td><Status value={member.is_active ? 'active' : 'blocked'} /></td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                        <button
                          type="button"
                          className="button secondary"
                          aria-label={`View details for ${member.first_name || member.email}`}
                          onClick={() => setSelectedStaff(member)}
                        >
                          Details
                        </button>
                        <button
                          className={`button secondary ${member.is_active ? 'danger' : ''}`}
                          disabled={statusAction.isPending}
                          onClick={() => statusAction.mutate({ id: member.id, action: member.is_active ? 'block' : 'unblock' })}
                        >
                          {member.is_active ? <UserRoundX size={16} /> : <UserRoundCheck size={16} />}
                          {member.is_active ? 'Block' : 'Unblock'}
                        </button>
                        {!member.staff_email_verified && <button className="button secondary" disabled={resendVerification.isPending} onClick={() => resendVerification.mutate(member.id)}>Resend verification</button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <CollectionPagination filters={filters} count={staff.data?.count || 0} />
        </>
      ) : (
        <div className="admin-staff-empty">
          <UsersRound size={36} />
          <h2>{filters.active ? 'No staff found' : 'No staff accounts yet'}</h2>
          <p>{filters.active ? 'Try a different name or email address.' : 'Add your first staff member to give them access.'}</p>
          {!filters.active && <button className="button" onClick={() => setAdding(true)}>Add staff</button>}
        </div>
      )}
      {adding && (
        <StaffDialog
          onClose={() => setAdding(false)}
          onCreated={async () => {
            setAdding(false);
            await client.invalidateQueries({ queryKey: ['admin', 'staff'] });
            notify('Staff account created');
          }}
        />
      )}
      <StaffDetailDialog staff={selectedStaff} onClose={() => setSelectedStaff(null)} />
    </div>
  );
}

type DashboardDetail = { title: string; category?: string; rows: [string, string][] };

function DashboardDetailDialog({ detail, onClose, actions }: { detail: DashboardDetail | null; onClose: () => void; actions?: React.ReactNode }): React.JSX.Element | null {
  const dialogRef = useDialogFocus(Boolean(detail), onClose);
  if (!detail) return null;
  const category: string = detail.category || (detail.title.startsWith('Coupon ') ? 'Coupon' : detail.title.startsWith('Refund #') ? 'Refund' : detail.title.startsWith('Order #') ? 'Order' : 'Store');
  const status: string | undefined = detail.rows.find(([label]) => label === 'Status')?.[1];
  const fields: [string, string][] = detail.rows.filter(([label]) => label !== 'Status');
  return (
    <div className="dialog-backdrop admin-detail-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={dialogRef} className="admin-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="admin-detail-title">
        <header className="admin-detail-header">
          <div className="admin-detail-heading">
            <span className="admin-detail-icon" aria-hidden="true"><FileText size={22} /></span>
            <div><span className="eyebrow green">{category} details</span><h2 id="admin-detail-title">{detail.title}</h2></div>
          </div>
          <button type="button" className="icon-button no-print" aria-label="Close details" onClick={onClose}><X size={20} /></button>
        </header>
        <div className="admin-detail-body">
          {status && <div className="admin-detail-status"><span>Current status</span><Status value={status.toLowerCase()} /></div>}
          <dl className="admin-detail-grid">
            {fields.map(([label, value]) => (
              <div className={`admin-detail-field${['Reason', 'Failure Details', 'Provider Reference'].includes(label) ? ' admin-detail-field-wide' : ''}`} key={label}>
                <dt>{label}</dt><dd>{value || 'Not provided'}</dd>
              </div>
            ))}
          </dl>
        </div>
        <footer className="admin-detail-footer no-print">
          {actions}
          <button type="button" className="button secondary" onClick={() => window.print()}><Printer size={16} />Print details</button>
          <button type="button" className="button" onClick={onClose}>Done</button>
        </footer>
      </section>
    </div>
  );
}

function StaffDetailDialog({ staff, onClose }: { staff: StaffUser | null; onClose: () => void }): React.JSX.Element {
  const detail: DashboardDetail | null = staff ? {
    title: `${staff.first_name} ${staff.last_name}`.trim() || staff.email,
    category: 'Staff account',
    rows: [
      ['Email', staff.email], ['First name', staff.first_name], ['Last name', staff.last_name],
      ['Gender', staff.gender], ['Role', staff.role], ['Status', staff.is_active ? 'Active' : 'Blocked'],
      ...(!staff.is_active && staff.staff_blocked_at ? [['Blocked on', activityDate(staff.staff_blocked_at)] as [string, string]] : []),
      ['Joined', activityDate(staff.date_joined)],
      ['Last active', activityDate(staff.last_active_at)], ['Last login', activityDate(staff.last_login)], ['Profile updated', activityDate(staff.updated)],
    ],
  } : null;
  return <DashboardDetailDialog detail={detail} onClose={onClose} />;
}

function StaffDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => Promise<void> }) {
  const dialogRef = useDialogFocus(true, onClose);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try {
      await api('admin/staff', 'POST', Object.fromEntries(form.entries()));
      await onCreated();
    } catch (caught) { setError((caught as Error).message); setBusy(false); }
  }
  return (
    <div className="admin-dialog-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={dialogRef} className="admin-dialog" role="dialog" aria-modal="true" aria-labelledby="add-staff-title">
        <div className="admin-dialog-head">
          <div>
            <span className="eyebrow green">NEW TEAM MEMBER</span>
            <h2 id="add-staff-title">Add staff</h2>
          </div>
          <button className="icon-button" aria-label="Close" onClick={onClose}>
            <X size={19} />
          </button>
        </div>
        <form className="form-stack" onSubmit={submit}>
          <div className="form-row">
            <Field label="First name"><input name="first_name" required maxLength={30} autoComplete="given-name" /></Field>
            <Field label="Last name"><input name="last_name" required maxLength={30} autoComplete="family-name" /></Field>
          </div>
          <Field label="Email address"><input name="email" type="email" required autoComplete="email" /></Field>
          <div className="form-row">
            <Field label="Phone number"><input name="phone1" type="tel" required placeholder="+234 801 234 5678" autoComplete="tel" /></Field>
            <Field label="Gender">
              <select name="gender" required defaultValue="">
                <option value="" disabled>Select</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
              </select>
            </Field>
          </div>
          <Field label="Temporary password"><input value="••••••••" readOnly aria-label="Password generated privately by the server" /><small>After email verification, credentials are sent directly to the staff member.</small></Field>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="form-actions">
            <button type="button" className="button secondary" onClick={onClose}>Cancel</button>
            <button className="button" disabled={busy}>{busy ? 'Creating…' : 'Create staff account'}</button>
          </div>
        </form>
      </section>
    </div>
  );
}

export function AdminStoresPage() {
  const { user, notify } = useShop();
  const canManageStoreStatus = Boolean(user?.is_superuser || user?.is_business_admin);
  const client = useQueryClient();
  const [offset, setOffset] = useState(0);
  const extraFilters = useCollectionFilters();
  useEffect(() => { setOffset(0); }, [extraFilters.query]);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search);
  const [statusFilter, setStatusFilter] = useState('');
  const [ordering, setOrdering] = useState('-created');
  const actionDialog = useActionDialog();

  const stores = useQuery({
    queryKey: ['admin', 'stores', offset, debouncedSearch, statusFilter, ordering, extraFilters.query, user?.id],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey.at(-1) === user?.id ? previousData : undefined,
    queryFn: () => api<Page<import('@/lib/types').Store>>(`admin/staff/stores?${extraFilters.query}&limit=20&offset=${offset}&ordering=${ordering}${debouncedSearch ? `&search=${encodeURIComponent(debouncedSearch)}` : ''}${statusFilter ? `&status=${statusFilter}` : ''}`),
    enabled: !!user && (user.is_staff || user.is_superuser || user.is_business_admin),
  });

  const [error, setError] = useState('');

  async function action(path: string, method: 'POST' | 'PUT' | 'DELETE', data = {}) {
    setError('');
    try {
      await api(path, method, data);
      await client.invalidateQueries({ queryKey: ['stores'] });
      await client.invalidateQueries({ queryKey: ['admin', 'stores'] });
      notify('Store updated');
    } catch (caught) {
      setError((caught as Error).message);
    }
  }

  if (!user?.is_staff && !user?.is_superuser && !user?.is_business_admin) {
    return (
      <Empty
        title="Administrator access required"
          text="Sign in with a staff or administrator account to review stores."
        href="/admin"
        label="Back to dashboard"
      />
    );
  }

  return (
    <div className="container section">
      <div className="merchant-heading">
        <div>
          <h1>Store governance</h1>
          <p>Approve sellers, review verification tiers, and manage stores with global backoffice staff access.</p>
        </div>
        <div className="form-actions">
          {(user.is_superuser || user.is_business_admin) && <Link className="button" href="/merchant/new-store">
            <Plus size={16} /> Create official store
          </Link>}
        </div>
      </div>

      <div className="merchant-toolbar">
        <div className="search-box">
          <Search size={17} />
          <input
            aria-label="Search stores"
            placeholder="Search store, username, or owner…"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
          />
        </div>
        <select
          aria-label="Filter stores by status"
          value={statusFilter}
          onChange={(event) => {
            setStatusFilter(event.target.value);
            setOffset(0);
          }}
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="pending">Pending</option>
          <option value="blocked">Blocked</option>
        </select>
        <select
          aria-label="Order stores"
          value={ordering}
          onChange={(event) => {
            setOrdering(event.target.value);
            setOffset(0);
          }}
        >
          <option value="-created">Newest first</option>
          <option value="created">Oldest first</option>
          <option value="name">Name A–Z</option>
          <option value="-name">Name Z–A</option>
          <option value="status">Status</option>
        </select>
      </div>

      {error && <p role="alert" className="form-error">{error}</p>}
      {stores.error && <ErrorState error={stores.error} retry={() => stores.refetch()} />}

      <CollectionFilters filters={extraFilters} label="additional filters" hideSearch fields={[{ key: 'is_official', label: 'Store type', options: [{ value: 'true', label: 'Official' }, { value: 'false', label: 'Merchant' }] }, ...financialFields.slice(0, 2)]} />
      <button type="button" className="button secondary" onClick={() => {
        extraFilters.reset();
        setSearch('');
        setStatusFilter(''); setOrdering('-created'); setOffset(0);
      }}>Reset all filters</button>
      {stores.isFetching && !stores.isLoading && <Loading compact overlay />}

      {stores.isLoading ? (
        <Loading />
      ) : !stores.data?.results.length ? (
        <Empty
          title="No operational stores found"
          text={search || statusFilter || extraFilters.active ? "No stores match your filters. Reset filters to see all stores." : "There are no stores registered yet."}
          href={(user.is_superuser || user.is_business_admin) ? "/merchant/new-store" : undefined}
          label={(user.is_superuser || user.is_business_admin) ? "Create official store" : undefined}
        />
      ) : (
        <>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Store</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Updated</th>
                  <th>Last active</th>
                  <th>Staff access</th>
                  <th><span className="sr-only">Actions</span>Actions</th>
                </tr>
              </thead>
              <tbody>
                {stores.data.results.map(store => {
                  return (
                    <tr key={store.id}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div
                            style={{
                              width: 34,
                              height: 34,
                              borderRadius: 6,
                              background: 'var(--soft)',
                              border: '1px solid var(--line)',
                              display: 'grid',
                              placeItems: 'center',
                              flexShrink: 0,
                            }}
                          >
                            <Store size={16} />
                          </div>
                          <div>
                            <Link href={`/admin/stores/${store.id}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontWeight: 700 }}>
                              {store.name}
                              <VerifiedBadge
                                tier={store.is_official ? 'official' : 'starter'}
                                tierData={store.seller_tier}
                                size={13}
                              />
                            </Link>
                            <small style={{ display: 'block', color: 'var(--muted)' }}>
                              @{store.username}
                            </small>
                          </div>
                        </div>
                      </td>
                      <td>
                        {store.is_official ? (
                          <span className="account-badge admin">Official Store</span>
                        ) : (
                          <span className="account-badge customer">Independent Seller</span>
                        )}
                      </td>
                      <td>
                        <Status value={store.status} />
                        {store.blocked_reason && (
                          <small style={{ display: 'block', color: 'var(--red)', marginTop: 2 }}>
                            {store.blocked_reason}
                          </small>
                        )}
                      </td>
                      <td><DateStamp value={store.created} /></td>
                      <td><DateStamp value={store.updated} /></td>
                      <td><DateStamp value={store.last_active_at} /></td>
                      <td>
                        {store.is_official ? (
                          <span
                            style={{
                              fontSize: 11,
                              background: 'var(--soft)',
                              padding: '2px 6px',
                              borderRadius: 4,
                              border: '1px solid var(--line)',
                              color: 'var(--green)',
                              fontWeight: 500,
                            }}
                          >
                            All staff (Global access)
                          </span>
                        ) : (
                          <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                            Centralized backoffice only
                          </span>
                        )}
                      </td>
                      <td>
                        <div className="form-actions" style={{ justifyContent: 'flex-end', flexWrap: 'nowrap', gap: 6 }}>
                          <Link className="button secondary" href={`/shop?store=${store.id}&preview=1`}><Eye size={14} /> Preview</Link>
                          {store.is_official ? (
                            (user.is_superuser || user.is_business_admin) && (
                              <button
                                className="button secondary danger"
                                onClick={async () => {
                                  if (await actionDialog.ask({ title: 'Delete official store', message: `Delete ${store.name} and its catalog?`, confirmLabel: 'Delete store' }) !== null)
                                    void action(`stores/${store.id}/delete`, 'DELETE');
                                }}
                              >
                                <Trash2 size={14} /> Delete
                              </button>
                            )
                          ) : (
                            store.status === 'blocked' ? (
                              canManageStoreStatus && (
                                <button
                                  className="button secondary"
                                  onClick={() => void action(`admin/staff/stores/${store.id}/unblock`, 'POST')}
                                >
                                  <Check size={14} /> Reactivate
                                </button>
                              )
                            ) : store.status === 'pending' ? (
                              canManageStoreStatus && (
                                <button
                                  className="button secondary"
                                  onClick={() => void action(`admin/stores/${store.id}/approve`, 'POST')}
                                >
                                  <Check size={14} /> Approve
                                </button>
                              )
                            ) : (
                              canManageStoreStatus && (
                                <button
                                  className="button secondary danger"
                                  onClick={async () => {
                                    const reason = await actionDialog.ask({
                                      title: `Suspend ${store.name}`,
                                      message: `Are you sure you want to suspend @${store.username}? Products will be hidden from shoppers.`,
                                      confirmLabel: 'Suspend store',
                                      reasonLabel: 'Reason for suspension',
                                    });
                                    if (reason !== null) {
                                      void action(`admin/staff/stores/${store.id}/block`, 'POST', {
                                        reason: reason || 'Suspended by staff',
                                      });
                                    }
                                  }}
                                >
                                  <Ban size={14} /> Suspend
                                </button>
                              )
                            )
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <Pagination
            page={Math.floor(offset / 20) + 1}
            totalPages={Math.ceil((stores.data?.count || 0) / 20)}
            onChange={page => setOffset((page - 1) * 20)}
          />
        </>
      )}

      {actionDialog.dialog}
    </div>
  );
}

function AdminStorePayments({ storeId }: { storeId: string }): React.JSX.Element {
  const { user } = useShop();
  const [tab, setTab] = useState<'payouts' | 'ledger'>('payouts');
  const [detail, setDetail] = useState<DashboardDetail | null>(null);
  const payoutFilters = useCollectionFilters();
  const ledgerFilters = useCollectionFilters();
  const filters = tab === 'payouts' ? payoutFilters : ledgerFilters;
  const base = `admin/staff/stores/${storeId}`;
  const summary = useQuery({
    queryKey: ['admin', 'store-financials', storeId, user?.id],
    queryFn: () => api<MerchantStoreSummary>(`${base}/financials`),
    enabled: Boolean(user),
  });
  const payouts = useQuery({
    queryKey: ['admin', 'store-payouts', storeId, payoutFilters.query, user?.id],
    queryFn: () => api<Page<StorePayout>>(`admin/staff/payouts?store_id=${storeId}&${payoutFilters.query}`),
    enabled: Boolean(user && tab === 'payouts'),
  });
  const ledger = useQuery({
    queryKey: ['admin', 'store-ledger', storeId, ledgerFilters.query, user?.id],
    queryFn: () => api<Page<StoreEarningsLedger>>(`${base}/ledger?${ledgerFilters.query}`),
    enabled: Boolean(user && tab === 'ledger'),
  });
  const clearPayout = useNotificationDetail<StorePayout>(
    'payout', `admin/staff/payouts?store_id=${storeId}`, payout => setDetail(payoutDetail(payout)),
  );
  const clearLedger = useNotificationDetail<StoreEarningsLedger>('ledger', `${base}/ledger`, showLedger);

  function closeDetail(): void {
    setDetail(null);
    clearPayout();
    clearLedger();
  }

  function showLedger(entry: StoreEarningsLedger): void {
    const rows: [string, string][] = [
      ['Reference', entry.reference],
      ['Entry type', entry.entry_type],
      ['Description', entry.description],
      ['Status', entry.status],
      ['Gross amount', money(entry.gross_amount)],
      ['Platform fee', money(entry.fee_amount)],
      ['Net amount', money(entry.net_amount)],
      ['Created', activityDate(entry.created)],
    ];
    if (entry.order) rows.push(['Order', `#${entry.order}`]);
    if (entry.available_at) rows.push(['Available on', activityDate(entry.available_at)]);
    if (entry.cleared_at) rows.push(['Cleared on', activityDate(entry.cleared_at)]);
    setDetail({ title: `Ledger entry ${entry.reference || `#${entry.id}`}`, category: 'Store payment', rows });
  }

  const statusOptions: string[] = tab === 'payouts'
    ? ['pending', 'completed', 'rejected']
    : ['pending', 'available', 'completed', 'reversed'];
  const fields: CollectionField[] = [
    {
      key: 'status', label: 'Status',
      options: statusOptions.map(value => ({ value, label: value })),
    },
    tab === 'payouts' ? {
      key: 'payout_method', label: 'Payment method',
      options: [
        { value: 'bank_transfer', label: 'Bank transfer' },
        { value: 'stripe_connect', label: 'Stripe Connect' },
      ],
    } : {
      key: 'entry_type', label: 'Entry type',
      options: ['sale', 'fee', 'payout', 'refund', 'adjustment'].map(value => ({ value, label: value })),
    },
    ...financialFields,
  ];
  const result = tab === 'payouts' ? payouts : ledger;
  const count = result.data?.count ?? 0;
  const summaryFields: [string, string][] = summary.data ? [
    ['Gross sales', summary.data.gross_sales],
    ['Platform fees', summary.data.platform_fee_deducted],
    ['Net sales', summary.data.net_sales],
    ['In review', summary.data.in_review],
    ['Cleared total', summary.data.cleared_total],
    ['Available balance', summary.data.available_balance],
    ['Pending payouts', summary.data.payouts_pending],
    ['Completed payouts', summary.data.payouts_completed],
  ] : [];

  return (
    <section className="section" aria-label="Store payments">
      <div className="merchant-heading">
        <div>
          <h2>Store payments</h2>
          <p>Store earnings, platform fees, escrow, and payout requests.</p>
          <p className="muted">Balances cover this store’s full history. Filters apply to the tables below.</p>
        </div>
      </div>
      {summary.isLoading ? <Loading compact /> : summary.error ? (
        <ErrorState error={summary.error} retry={() => void summary.refetch()} />
      ) : (
        <div className="stats-grid">
          {summaryFields.map(([label, amount]) => (
            <div className="stat-item" key={label}>
              <div>
                <span>{label}</span>
                <DollarSign size={18} />
              </div>
              <strong>{money(amount)}</strong>
            </div>
          ))}
        </div>
      )}
      <div className="tabs" aria-label="Store payment history">
        <button
          type="button"
          className={tab === 'payouts' ? 'active' : ''}
          aria-pressed={tab === 'payouts'}
          onClick={() => setTab('payouts')}
        >
          Payout requests
        </button>
        <button
          type="button"
          className={tab === 'ledger' ? 'active' : ''}
          aria-pressed={tab === 'ledger'}
          onClick={() => setTab('ledger')}
        >
          Earnings ledger
        </button>
      </div>
      <CollectionFilters
        filters={filters}
        label={tab === 'payouts' ? 'store payouts' : 'store earnings'}
        fields={fields}
      />
      <CollectionCount count={count} />
      {result.isFetching && !result.isLoading && <Loading compact overlay />}
      {result.isLoading ? <Loading /> : result.error ? (
        <ErrorState error={result.error} retry={() => void result.refetch()} />
      ) : count === 0 ? (
        <Empty
          title={filters.active ? 'No payments match your filters' : tab === 'payouts' ? 'No store payout requests yet' : 'No store earnings yet'}
          text={filters.active ? 'Reset filters to see all records for this store.' : 'Payment records assigned to this store will appear here.'}
          onAction={filters.reset}
          label="Reset filters"
        />
      ) : (
        <>
          <div className="table-scroll">
            {tab === 'payouts' ? (
              <table>
                <thead>
                  <tr>
                    <th>Reference</th>
                    <th>Amount</th>
                    <th>Method</th>
                    <th>Status</th>
                    <th>Requested</th>
                    <th>Processed</th>
                  </tr>
                </thead>
                <tbody>
                  {payouts.data?.results.map(payout => (
                    <tr key={payout.id}>
                      <td>
                        <button
                          type="button"
                          className="text-link"
                          onClick={() => setDetail(payoutDetail(payout))}
                        >
                          {payout.reference}
                        </button>
                      </td>
                      <td>{money(payout.amount)}</td>
                      <td>{payout.payout_method.replaceAll('_', ' ')}</td>
                      <td><Status value={payout.status} /></td>
                      <td><DateStamp value={payout.created} /></td>
                      <td>{payout.processed_at ? <DateStamp value={payout.processed_at} /> : 'Not processed'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Reference</th>
                    <th>Type</th>
                    <th>Description</th>
                    <th>Gross</th>
                    <th>Fee</th>
                    <th>Net</th>
                    <th>Status</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.data?.results.map(entry => (
                    <tr key={entry.id}>
                      <td>
                        <button
                          type="button"
                          className="text-link"
                          onClick={() => showLedger(entry)}
                        >
                          {entry.reference || `#${entry.id}`}
                        </button>
                      </td>
                      <td>{entry.entry_type}</td>
                      <td>{entry.description}</td>
                      <td>{money(entry.gross_amount)}</td>
                      <td>{money(entry.fee_amount)}</td>
                      <td>{money(entry.net_amount)}</td>
                      <td><Status value={entry.status} /></td>
                      <td><DateStamp value={entry.created} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <CollectionPagination filters={filters} count={count} />
        </>
      )}
      <DashboardDetailDialog detail={detail} onClose={closeDetail} />
    </section>
  );
}

export function AdminStoreDetailPage({ id }: { id: string }) {
  const { user, notify } = useShop();
  const client = useQueryClient();
  const actionDialog = useActionDialog();
  const [storeActionError, setStoreActionError] = useState('');
  const canManageStoreStatus = Boolean(user?.is_superuser || user?.is_business_admin);
  const store = useQuery({ queryKey: ['admin', 'store', id], queryFn: () => api<import('@/lib/types').Store & { owner_email?: string; owner_name?: string }>(`admin/staff/stores/${id}`), enabled: !!user });

  const extraFilters = useCollectionFilters();
  useEffect(() => { setOffset(0); }, [extraFilters.query]);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search);
  const [typeFilter, setTypeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [assetFilter, setAssetFilter] = useState('all');
  const [ordering, setOrdering] = useState('-created');
  const [offset, setOffset] = useState(0);

  const params = new URLSearchParams(extraFilters.query);
  params.set('offset', String(offset));
  params.set('limit', '20');
  if (debouncedSearch) params.set('search', debouncedSearch);
  if (typeFilter === 'digital') params.set('is_digital', 'true');
  if (typeFilter === 'physical') {
    params.set('is_digital', 'false');
    params.set('product_type', 'standard');
  }
  if (typeFilter === 'affiliate') params.set('product_type', 'affiliate_clickbank');
  if (statusFilter === 'published') params.set('visibility', 'true');
  if (statusFilter === 'draft') params.set('visibility', 'false');
  if (statusFilter === 'blocked') params.set('is_blocked', 'true');
  if (assetFilter === 'has_asset') params.set('has_asset', 'true');
  if (assetFilter === 'no_asset') params.set('has_asset', 'false');
  if (ordering) params.set('ordering', ordering);

  const products = useQuery({
    queryKey: ['admin', 'store', id, 'products', params.toString(), user?.id],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[2] === id
        && previousQuery.queryKey.at(-1) === user?.id
        ? previousData
        : undefined,
    queryFn: () => api<Page<import('@/lib/types').StoreAuditProduct> | import('@/lib/types').StoreAuditProduct[]>(`admin/staff/stores/${id}/products?${params.toString()}`),
    enabled: !!user,
  });

  if (!user?.is_staff && !user?.is_superuser && !user?.is_business_admin) return <Empty title="Staff access required" text="This store record is available to backoffice users." />;
  if (store.isLoading) return <Loading fullPage />;
  if (store.error || !store.data) return <ErrorState error={store.error || new Error('Store not found')} retry={() => store.refetch()} />;
  const data = store.data;

  async function updateStoreStatus(action: 'block' | 'unblock', reason?: string): Promise<void> {
    setStoreActionError('');
    try {
      await api(`admin/staff/stores/${id}/${action}`, 'POST', reason ? { reason } : {});
      await Promise.all([
        client.invalidateQueries({ queryKey: ['admin', 'store', id] }),
        client.invalidateQueries({ queryKey: ['admin', 'stores'] }),
        client.invalidateQueries({ queryKey: ['stores'] }),
      ]);
      notify(action === 'block' ? 'Store suspended' : 'Store reactivated');
    } catch (caught) {
      setStoreActionError((caught as Error).message);
    }
  }

  async function moderateProduct(product: import('@/lib/types').StoreAuditProduct, action: 'block' | 'restore', reason: string): Promise<void> {
    try {
      await api(`admin/staff/products/${product.id}/moderation`, 'POST', { action, reason });
      await Promise.all([
        client.invalidateQueries({ queryKey: ['admin', 'store', id, 'products'] }),
        client.invalidateQueries({ queryKey: ['products'] }),
        client.invalidateQueries({ queryKey: ['catalog'] }),
      ]);
      notify(action === 'block' ? `Product "${product.title}" has been blocked` : `Product "${product.title}" has been restored`);
    } catch (caught) {
      notify((caught as Error).message, true);
    }
  }

  const productList: import('@/lib/types').StoreAuditProduct[] = Array.isArray(products.data)
    ? products.data
    : (products.data?.results || []);
  const totalCount = Array.isArray(products.data)
    ? products.data.length
    : (products.data?.count || 0);

  return (
    <div className="container section">
      <Link className="text-link" href="/admin/stores">← All stores</Link>
      <div className="merchant-heading">
        <div>
          <h1>{data.name}</h1>
          <p>@{data.username} · {data.owner_email || 'No owner email'} · <Status value={data.status} /></p>
        </div>
        <div className="form-actions">
          {!data.is_official && canManageStoreStatus && (data.status === 'blocked' ? (
            <button className="button secondary" type="button" onClick={() => void updateStoreStatus('unblock')}>
              <Check size={16} /> Reactivate store
            </button>
          ) : (
            <button
              className="button secondary danger"
              type="button"
              onClick={async () => {
                const reason = await actionDialog.ask({
                  title: `Suspend ${data.name}`,
                  message: `Are you sure you want to suspend @${data.username}? Products will be hidden from shoppers.`,
                  confirmLabel: 'Suspend store',
                  reasonLabel: 'Reason for suspension',
                });
                if (reason !== null) {
                  void updateStoreStatus('block', reason || 'Suspended by staff');
                }
              }}
            >
              <Ban size={16} /> Suspend store
            </button>
          ))}
          <Link className="button" href={`/shop?store=${data.id}&preview=1`}>
            <Eye size={16} /> Read-only storefront preview
          </Link>
        </div>
      </div>

      {storeActionError && <p role="alert" className="form-error">{storeActionError}</p>}

      <section className="analytics-panel">
        <h2>Core store settings</h2>
        <div className="form-stack">
          <div className="form-row">
            <Field label="Store name"><input value={data.name} readOnly aria-readonly="true" /></Field>
            <Field label="Store username"><input value={data.username} readOnly aria-readonly="true" /></Field>
          </div>
          <p className="muted">Store identity is controlled by the owner and is read-only for platform staff.</p>
        </div>
      </section>

      <section className="merchant-section" style={{ marginTop: '2rem' }}>
        <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2>Catalog audit</h2>
            <p>Review storefront inventory and verify digital assets without entering the seller dashboard.</p>
          </div>
          <span className="muted">{totalCount} {totalCount === 1 ? 'product' : 'products'} found</span>
        </div>

        <div className="merchant-toolbar" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center', margin: '1rem 0' }}>
          <div className="search-box">
            <Search size={17} />
            <input
              aria-label="Search catalog products"
              placeholder="Search by title or category…"
              value={search}
              onChange={e => { setSearch(e.target.value); setOffset(0); }}
            />
          </div>
          <select
            aria-label="Filter by type"
            value={typeFilter}
            onChange={e => { setTypeFilter(e.target.value); setOffset(0); }}
          >
            <option value="all">All product types</option>
            <option value="digital">Digital only</option>
            <option value="physical">Physical only</option>
            <option value="affiliate">ClickBank affiliate offer</option>
          </select>
          <select
            aria-label="Filter by visibility"
            value={statusFilter}
            onChange={e => { setStatusFilter(e.target.value); setOffset(0); }}
          >
            <option value="all">All statuses</option>
            <option value="published">Published</option>
            <option value="draft">Draft</option>
            <option value="blocked">Blocked</option>
          </select>
          <select
            aria-label="Filter by digital asset"
            value={assetFilter}
            onChange={e => { setAssetFilter(e.target.value); setOffset(0); }}
          >
            <option value="all">All assets</option>
            <option value="has_asset">Asset attached</option>
            <option value="no_asset">No asset</option>
          </select>
          <select
            aria-label="Order products"
            value={ordering}
            onChange={e => { setOrdering(e.target.value); setOffset(0); }}
          >
            <option value="-created">Newest first</option>
            <option value="created">Oldest first</option>
            <option value="title">Title A–Z</option>
            <option value="-title">Title Z–A</option>
            <option value="price">Price: low to high</option>
            <option value="-price">Price: high to low</option>
          </select>
        </div>

        <CollectionFilters filters={extraFilters} label="additional filters" hideSearch fields={[{ key: 'category', label: 'Category', options: categories.map(category => ({ value: category.key, label: category.name })) }]} />
      <button type="button" className="button secondary" onClick={() => {
        extraFilters.reset();
        setSearch('');
        setTypeFilter('all'); setStatusFilter('all'); setAssetFilter('all'); setOrdering('-created'); setOffset(0);
      }}>Reset all filters</button>
      {products.isFetching && !products.isLoading && <Loading />}

        {products.isLoading ? (
          <Loading />
        ) : products.error ? (
          <ErrorState error={products.error} retry={() => products.refetch()} />
        ) : !productList.length ? (
          <p className="muted" style={{ padding: '1rem 0' }}>{search || typeFilter !== 'all' || statusFilter !== 'all' || assetFilter !== 'all' || extraFilters.active ? 'No products match the selected filters.' : 'This store has no products yet.'}</p>
        ) : (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Type</th>
                    <th>Category</th>
                    <th>Inventory</th>
                    <th>Units sold</th>
                    <th>Status</th>
                    <th>Audit asset</th>
                    <th>Moderation</th>
                  </tr>
                </thead>
                <tbody>
                  {productList.map(product => (
                    <tr key={product.id}>
                      <td>
                        <Link className="text-link" href={`/products/${product.id}?preview=1`}>
                          <strong>{product.title}</strong>
                        </Link>
                      </td>
                      <td>
                        {product.product_type === 'affiliate_clickbank' ? (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'rgba(234, 88, 12, 0.1)', color: '#ea580c', padding: '2px 6px', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>
                            Partner Offer
                          </span>
                        ) : product.is_digital ? (
                          'Digital'
                        ) : (
                          'Physical'
                        )}
                      </td>
                      <td>{product.category}</td>
                      <td>
                        {product.product_type === 'affiliate_clickbank'
                          ? 'Partner fulfilled'
                          : product.is_digital
                            ? 'Unlimited'
                            : (product.available ?? '—')}
                      </td>
                      <td>
                        {product.product_type === 'affiliate_clickbank' ? (
                          <span className="muted" title="Sales are completed and tracked by the external partner.">
                            Not tracked
                          </span>
                        ) : (
                          product.sales.toLocaleString()
                        )}
                      </td>
                      <td>
                        {product.is_blocked ? (
                          <div>
                            <Status value="blocked" />
                            {product.blocked_reason && (
                              <small
                                className="muted"
                                style={{ display: 'block', fontSize: '10px', marginTop: '3px', maxWidth: '140px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                title={`Blocked reason: ${product.blocked_reason}${product.blocked_by_email ? ` (${product.blocked_by_email})` : ''}`}
                              >
                                {product.blocked_reason}
                              </small>
                            )}
                          </div>
                        ) : (
                          product.visibility ? 'Published' : 'Draft'
                        )}
                      </td>
                      <td>
                        {product.product_type === 'affiliate_clickbank' ? (
                          product.affiliate_hoplink ? (
                            <a
                              className="button secondary"
                              href={product.affiliate_hoplink}
                              target="_blank"
                              rel="noreferrer noopener"
                              style={{ fontSize: '11px', padding: '4px 8px' }}
                            >
                              HopLink <ArrowUpRight size={12} />
                            </a>
                          ) : (
                            <span className="muted">No link</span>
                          )
                        ) : product.is_digital && product.has_digital_asset ? (
                          <a
                            className="button secondary"
                            href={`/api/admin/staff/products/${product.id}/digital-asset`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Preview / download
                          </a>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td>
                        {product.is_blocked ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                            <button
                              type="button"
                              className="button secondary compact"
                              style={{ fontSize: '11px', padding: '4px 8px' }}
                              onClick={async () => {
                                const reason = await actionDialog.ask({
                                  title: `Restore ${product.title}`,
                                  message: `Restore this product to the marketplace? It will become visible and purchasable again if published.`,
                                  confirmLabel: 'Restore listing',
                                  reasonLabel: 'Reason for restoration',
                                });
                                if (reason !== null && reason.trim()) {
                                  void moderateProduct(product, 'restore', reason.trim());
                                }
                              }}
                            >
                              <Check size={13} /> Restore
                            </button>
                            {product.moderation_events && product.moderation_events.length > 0 && (
                              <span
                                className="muted"
                                style={{ fontSize: '10px', cursor: 'help' }}
                                title={product.moderation_events.map(e => `${new Date(e.created).toLocaleString()}: ${e.action.toUpperCase()} by ${e.actor_email} (${e.reason})`).join('\n')}
                              >
                                Audit: {product.moderation_events.length} event{product.moderation_events.length === 1 ? '' : 's'}
                              </span>
                            )}
                          </div>
                        ) : (
                          <button
                            type="button"
                            className="button secondary danger compact"
                            style={{ fontSize: '11px', padding: '4px 8px' }}
                            onClick={async () => {
                              const reason = await actionDialog.ask({
                                title: `Block ${product.title}`,
                                message: `Block this product from the marketplace? Shoppers will be unable to find, view, or purchase it, including items already in carts. Existing orders and fulfillment will remain intact.`,
                                confirmLabel: 'Block product',
                                reasonLabel: 'Required reason for blocking',
                                reasonPresets: [
                                  'Suspected scam',
                                  'Prohibited item',
                                  'Misleading description',
                                  'Policy violation',
                                ],
                              });
                              if (reason !== null && reason.trim()) {
                                void moderateProduct(product, 'block', reason.trim());
                              }
                            }}
                          >
                            <Ban size={13} /> Block
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <Pagination
              page={Math.floor(offset / 20) + 1}
              totalPages={Math.ceil(totalCount / 20)}
              onChange={page => setOffset((page - 1) * 20)}
            />
          </>
        )}
      </section>
      <AdminOrdersPage key={id} storeId={id} />
      <AdminStoreTeam key={`team-${id}`} storeId={id} store={data} />
      <AdminStorePayments key={`payments-${id}`} storeId={id} />
      {actionDialog.dialog}
    </div>
  );
}

function AdminStoreTeam({
  storeId,
  store,
}: {
  storeId: string;
  store: import('@/lib/types').Store & { owner_email?: string; owner_name?: string; owner_avatar_url?: string };
}) {
  const { notify } = useShop();
  const client = useQueryClient();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'store_admin' | 'catalog_manager' | 'fulfillment_specialist'>('catalog_manager');
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [resendingId, setResendingId] = useState<number | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<import('@/lib/types').StoreTeamMember | null>(null);
  const [deleting, setDeleting] = useState(false);

  const inviteDialogRef = useDialogFocus<HTMLDivElement>(inviteOpen, () => setInviteOpen(false));
  const deleteDialogRef = useDialogFocus<HTMLDivElement>(Boolean(deleteTarget), () => setDeleteTarget(null));

  const filters = useCollectionFilters();
  const team = useQuery({
    queryKey: ['admin', 'store-team', storeId, filters.query],
    queryFn: () => api<Page<import('@/lib/types').StoreTeamMember>>(`stores/${storeId}/team?paginated=1&${filters.query}`),
  });

  async function handleInvite(e: FormEvent) {
    e.preventDefault();
    setInviteError(null);
    setInviting(true);
    try {
      await api<import('@/lib/types').StoreTeamMember>(`stores/${storeId}/team`, 'POST', {
        email: inviteEmail.trim(),
        role: inviteRole,
      });
      await client.invalidateQueries({ queryKey: ['admin', 'store-team', storeId] });
      notify(`Invited ${inviteEmail} to store team.`);
      setInviteEmail('');
      setInviteRole('catalog_manager');
      setInviteOpen(false);
    } catch (err: unknown) {
      let message = err instanceof Error ? err.message : 'Failed to add team member.';
      message = message.replace(/^(?:email|detail|error|non_field_errors):\s*/i, '');
      setInviteError(message);
    } finally {
      setInviting(false);
    }
  }

  async function handleResendInvite(member: import('@/lib/types').StoreTeamMember) {
    setResendingId(member.id);
    try {
      await api<{ detail: string }>(`stores/${storeId}/team/${member.id}/resend`, 'POST');
      notify(`Invitation email resent to ${member.email}.`);
    } catch (err: unknown) {
      let message = err instanceof Error ? err.message : 'Failed to resend invitation.';
      message = message.replace(/^(?:email|detail|error|non_field_errors):\s*/i, '');
      notify(message, true);
    } finally {
      setResendingId(null);
    }
  }

  async function handleRoleChange(
    memberId: number,
    newRole: 'store_admin' | 'catalog_manager' | 'fulfillment_specialist'
  ) {
    try {
      await api<import('@/lib/types').StoreTeamMember>(`stores/${storeId}/team/${memberId}`, 'PATCH', { role: newRole });
      await client.invalidateQueries({ queryKey: ['admin', 'store-team', storeId] });
      notify('Team member role updated.');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update role.';
      notify(message, true);
    }
  }

  async function handleRemoveMember() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api(`stores/${storeId}/team/${deleteTarget.id}`, 'DELETE');
      await client.invalidateQueries({ queryKey: ['admin', 'store-team', storeId] });
      notify(`Removed ${deleteTarget.email} from store team.`);
      setDeleteTarget(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to remove team member.';
      notify(message, true);
    } finally {
      setDeleting(false);
    }
  }

  function getRoleBadge(roleValue: string) {
    if (roleValue === 'owner') {
      return (
        <span
          className="badge"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '3px 9px',
            borderRadius: 999,
            fontSize: '0.78rem',
            fontWeight: 600,
            background: 'rgba(245, 158, 11, 0.15)',
            color: '#d97706',
            border: '1px solid rgba(245, 158, 11, 0.35)',
          }}
        >
          <Shield size={12} />
          Store Owner
        </span>
      );
    }
    if (roleValue === 'store_admin') {
      return (
        <span
          className="badge"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '3px 9px',
            borderRadius: 999,
            fontSize: '0.78rem',
            fontWeight: 600,
            background: 'rgba(99, 102, 241, 0.15)',
            color: '#6366f1',
            border: '1px solid rgba(99, 102, 241, 0.35)',
          }}
        >
          <ShieldCheck size={12} />
          Store Admin
        </span>
      );
    }
    if (roleValue === 'catalog_manager') {
      return (
        <span
          className="badge"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '3px 9px',
            borderRadius: 999,
            fontSize: '0.78rem',
            fontWeight: 600,
            background: 'rgba(14, 165, 233, 0.15)',
            color: '#0284c7',
            border: '1px solid rgba(14, 165, 233, 0.35)',
          }}
        >
          <Package size={12} />
          Catalog Manager
        </span>
      );
    }
    return (
      <span
        className="badge"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '3px 9px',
          borderRadius: 999,
          fontSize: '0.78rem',
          fontWeight: 600,
          background: 'rgba(16, 185, 129, 0.15)',
          color: '#059669',
          border: '1px solid rgba(16, 185, 129, 0.35)',
        }}
      >
        <Truck size={12} />
        Fulfillment Specialist
      </span>
    );
  }

  const memberList = team.data?.results || [];

  return (
    <section className="merchant-section" style={{ marginTop: '2.5rem' }}>
      <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2>Store Team & Delegated Access</h2>
          <p>Audit and manage backoffice staff, managers, and fulfillment specialists granted access to this store.</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span className="muted" style={{ marginRight: 6 }}>{memberList.length + 1} total members</span>
          <Link
            href={`/merchant?store=${storeId}&tab=team`}
            className="button secondary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.82rem', padding: '6px 12px' }}
            title="Open merchant workspace team tab"
          >
            <ExternalLink size={14} />
            <span>Merchant View</span>
          </Link>
          <button
            type="button"
            className="button primary"
            onClick={() => {
              setInviteError(null);
              setInviteOpen(true);
            }}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.82rem', padding: '6px 12px' }}
          >
            <UserPlus size={15} />
            <span>Invite Member</span>
          </button>
        </div>
      </div>

      <CollectionFilters
        filters={filters}
        label="team members"
        fields={[
          {
            key: 'role',
            label: 'Role',
            options: [
              { value: 'store_admin', label: 'Store administrator' },
              { value: 'catalog_manager', label: 'Catalog manager' },
              { value: 'fulfillment_specialist', label: 'Fulfillment specialist' },
            ],
          },
          { key: 'start_date', label: 'Joined from', type: 'date' },
          { key: 'end_date', label: 'Joined until', type: 'date' },
        ]}
      />

      {team.isLoading ? (
        <Loading />
      ) : team.error ? (
        <ErrorState error={team.error} retry={() => team.refetch()} />
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden', marginTop: '1rem' }}>
          <div className="table-scroll">
            <table className="table" style={{ margin: 0 }}>
              <thead>
                <tr>
                  <th>User / Member</th>
                  <th>Assigned Role</th>
                  <th>Added</th>
                  <th>Invited By</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      {store.owner_avatar_url ? (
                        <ResponsiveMediaImage
                          src={store.owner_avatar_url}
                          alt={store.owner_name || 'Primary Store Owner'}
                          style={{ width: 34, height: 34, borderRadius: '50%', objectFit: 'cover' }}
                          sizes="34px"
                          width={68}
                          height={68}
                        />
                      ) : (
                        <div
                          style={{
                            width: 34,
                            height: 34,
                            borderRadius: '50%',
                            background: 'rgba(245, 158, 11, 0.15)',
                            color: '#d97706',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontWeight: 700,
                            fontSize: '0.82rem',
                            border: '1px solid rgba(245, 158, 11, 0.3)',
                          }}
                        >
                          <Shield size={16} />
                        </div>
                      )}
                      <div>
                        <strong>{store.owner_name || 'Primary Store Owner'}</strong>
                        <div style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
                          {store.owner_email || 'Store Owner'}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td>{getRoleBadge('owner')}</td>
                  <td>—</td>
                  <td>Account Owner</td>
                  <td style={{ textAlign: 'right', color: 'var(--muted)', fontSize: '0.82rem' }}>—</td>
                </tr>

                {memberList.map((member) => {
                  const isPending = member.status === 'pending';
                  return (
                    <tr key={member.id}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          {member.avatar_url ? (
                            <ResponsiveMediaImage
                              src={member.avatar_url}
                              alt={member.first_name || member.email}
                              style={{ width: 34, height: 34, borderRadius: '50%', objectFit: 'cover' }}
                              sizes="34px"
                              width={68}
                              height={68}
                            />
                          ) : (
                            <div
                              style={{
                                width: 34,
                                height: 34,
                                borderRadius: '50%',
                                background: isPending ? 'rgba(245, 158, 11, 0.15)' : 'var(--soft)',
                                color: isPending ? 'var(--amber, #d97706)' : 'var(--ink)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontWeight: 700,
                                fontSize: '0.82rem',
                                border: isPending ? '1px solid rgba(245, 158, 11, 0.35)' : '1px solid var(--line)',
                              }}
                            >
                              {isPending ? (
                                <Mail size={15} />
                              ) : (
                                (member.first_name?.[0] || member.email[0]).toUpperCase()
                              )}
                            </div>
                          )}
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                              <strong>
                                {member.first_name || member.last_name
                                  ? `${member.first_name || ''} ${member.last_name || ''}`.trim()
                                  : member.email.split('@')[0]}
                              </strong>
                              {isPending && (
                                <span
                                  className="badge"
                                  style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 3,
                                    padding: '1px 6px',
                                    borderRadius: 999,
                                    fontSize: '0.68rem',
                                    fontWeight: 600,
                                    background: 'rgba(245, 158, 11, 0.15)',
                                    color: 'var(--amber, #d97706)',
                                    border: '1px solid rgba(245, 158, 11, 0.35)',
                                  }}
                                >
                                  <Clock size={10} />
                                  Pending
                                </span>
                              )}
                            </div>
                            <div style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
                              {member.email}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td>{getRoleBadge(member.role)}</td>
                      <td style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>
                        {activityDate(member.created)}
                      </td>
                      <td style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>
                        {member.invited_by_email || 'Store Owner'}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, justifyContent: 'flex-end' }}>
                          {isPending && (
                            <button
                              type="button"
                              className="button secondary"
                              style={{ padding: '4px 8px', fontSize: '0.78rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                              disabled={resendingId === member.id}
                              onClick={() => handleResendInvite(member)}
                              title="Resend invitation email"
                            >
                              <RefreshCw size={12} className={resendingId === member.id ? 'spin' : ''} />
                              <span>Resend</span>
                            </button>
                          )}
                          {!isPending && (
                            <select
                              value={member.role}
                              onChange={(e) => handleRoleChange(member.id, e.target.value as 'store_admin' | 'catalog_manager' | 'fulfillment_specialist')}
                              style={{
                                padding: '4px 8px',
                                fontSize: '0.78rem',
                                borderRadius: 6,
                                background: 'var(--surface)',
                                color: 'var(--ink)',
                                border: '1px solid var(--line)',
                              }}
                              aria-label={`Change role for ${member.email}`}
                            >
                              <option value="store_admin">Store Admin</option>
                              <option value="catalog_manager">Catalog Manager</option>
                              <option value="fulfillment_specialist">Fulfillment Specialist</option>
                            </select>
                          )}
                          <button
                            type="button"
                            className="button secondary"
                            style={{
                              padding: '4px 8px',
                              fontSize: '0.78rem',
                              color: 'var(--red, #ef4444)',
                              borderColor: 'rgba(239, 68, 68, 0.3)',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 4,
                            }}
                            onClick={() => setDeleteTarget(member)}
                            title={isPending ? 'Cancel Invitation' : 'Remove Member'}
                          >
                            <Trash2 size={13} />
                            <span>{isPending ? 'Revoke' : 'Remove'}</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}

                {memberList.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center', padding: '1.5rem 1rem', color: 'var(--muted)' }}>
                      {filters.active ? 'No team members match the search filters.' : 'No delegated staff accounts assigned to this store.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <CollectionPagination filters={filters} count={team.data?.count || 0} />

      {inviteOpen && (
        <div className="dialog-backdrop" role="dialog" aria-modal="true" aria-labelledby="admin-team-invite-title">
          <div className="dialog card" ref={inviteDialogRef} style={{ maxWidth: 480 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 id="admin-team-invite-title" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                <UserPlus size={18} />
                <span>Invite Store Team Member</span>
              </h3>
              <button
                type="button"
                onClick={() => setInviteOpen(false)}
                className="button icon"
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--muted)' }}
                aria-label="Close dialog"
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: '0.86rem', color: 'var(--muted)', marginTop: 0, marginBottom: '1.25rem' }}>
              Invite staff members or collaborators to this store. They will receive an email invitation to join with designated permissions.
            </p>

            {inviteError && (
              <div
                style={{
                  padding: '8px 12px',
                  borderRadius: 6,
                  background: 'rgba(239, 68, 68, 0.12)',
                  color: 'var(--red, #ef4444)',
                  fontSize: '0.84rem',
                  marginBottom: '1rem',
                  border: '1px solid rgba(239, 68, 68, 0.25)',
                }}
              >
                {inviteError}
              </div>
            )}

            <form onSubmit={handleInvite}>
              <div style={{ marginBottom: '1rem' }}>
                <label htmlFor="admin-team-invite-email" style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: 4 }}>
                  Email address
                </label>
                <input
                  id="admin-team-invite-email"
                  type="email"
                  required
                  placeholder="staff@proace.local"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  disabled={inviting}
                  style={{ width: '100%' }}
                />
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label htmlFor="admin-team-invite-role" style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: 4 }}>
                  Assigned Role
                </label>
                <select
                  id="admin-team-invite-role"
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as 'store_admin' | 'catalog_manager' | 'fulfillment_specialist')}
                  disabled={inviting}
                  style={{ width: '100%' }}
                >
                  <option value="catalog_manager">Catalog Manager (products, variants, inventory)</option>
                  <option value="fulfillment_specialist">Fulfillment Specialist (orders, labels, tracking)</option>
                  <option value="store_admin">Store Administrator (full operations & team management)</option>
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => setInviteOpen(false)}
                  disabled={inviting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="button primary"
                  disabled={inviting || !inviteEmail.trim()}
                >
                  {inviting ? 'Sending Invite...' : 'Send Invitation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {deleteTarget && (
        <div className="dialog-backdrop" role="dialog" aria-modal="true" aria-labelledby="admin-team-delete-title">
          <div className="dialog card" ref={deleteDialogRef} style={{ maxWidth: 440 }}>
            <h3 id="admin-team-delete-title" style={{ marginTop: 0, marginBottom: '0.75rem' }}>
              {deleteTarget.status === 'pending' ? 'Revoke Invitation' : 'Remove Team Member'}
            </h3>
            <p style={{ fontSize: '0.88rem', color: 'var(--muted)', marginTop: 0, marginBottom: '1.25rem' }}>
              {deleteTarget.status === 'pending'
                ? `Are you sure you want to revoke the pending invitation for ${deleteTarget.email}? They will no longer be able to use the link to join.`
                : `Are you sure you want to remove ${deleteTarget.email} from this store? They will immediately lose all workspace access.`}
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                type="button"
                className="button secondary"
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button primary"
                style={{ background: 'var(--red, #ef4444)', borderColor: 'var(--red, #ef4444)', color: '#fff' }}
                onClick={handleRemoveMember}
                disabled={deleting}
              >
                {deleting ? 'Removing...' : deleteTarget.status === 'pending' ? 'Revoke Invite' : 'Remove Access'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export function AdminOrdersPage({ storeId }: { storeId?: string } = {}) {
  const { user, notify } = useShop();
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search);
  const [statusFilter, setStatusFilter] = useState('');
  const [courierFilter, setCourierFilter] = useState('');
  const [paymentFilter, setPaymentFilter] = useState('');
  const [ordering, setOrdering] = useState('-created');
  const [detail, setDetail] = useState<{ title: string; rows: [string, string][] } | null>(null);
  const actionDialog = useActionDialog();

  function showNotificationRecord(order: AdminOrder): void {
    setDetail({
      title: `Order #${order.orderId}`,
      rows: [
        ['Buyer', order.buyer_email || 'Guest'],
        ['Status', order.status],
        ['Payment Method', order.payment_type?.replaceAll('_', ' ') || 'card'],
        ['Subtotal', money(order.subtotal || order.total)],
        ['Total', money(order.total)],
        ['Created', activityDate(order.created)],
        ['Updated', activityDate(order.updated)],
        ['Status changed', activityDate(order.status_updated_at)],
        ['Cancelled', activityDate(order.cancelled_at)],
        ['Refunded', activityDate(order.refunded_at)],
        ['Carrier', order.carrier || 'USPS'],
        ['Tracking Number', order.tracking_number || 'Not assigned'],
        ...(order.shipped_at ? [['Shipped At', activityDate(order.shipped_at)] as [string, string]] : []),
        ...(order.delivered_at ? [['Delivered At', activityDate(order.delivered_at)] as [string, string]] : []),
        ...(order.items_snapshot?.length ? [['Items Count', `${order.items_snapshot.length} items recorded`] as [string, string]] : []),
      ],
    });
  }

  const clearNotificationDetail = useNotificationDetail<AdminOrder>('order', `admin/staff/orders${storeId ? `?store_id=${storeId}` : ''}`, showNotificationRecord);

  const queryParams = new URLSearchParams({
    limit: '15',
    offset: String((page - 1) * 15),
    ordering,
  });
  if (storeId) queryParams.set('store_id', storeId);
  if (debouncedSearch.trim()) queryParams.set('search', debouncedSearch.trim());
  if (statusFilter) queryParams.set('status', statusFilter);
  if (courierFilter) queryParams.set('carrier', courierFilter);
  if (paymentFilter) queryParams.set('payment_type', paymentFilter);

  const orders = useQuery({
    queryKey: ['admin', 'all_orders', page, debouncedSearch, statusFilter, courierFilter, paymentFilter, ordering, storeId, user?.id],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey.at(-1) === user?.id
        && previousQuery?.queryKey.at(-2) === storeId ? previousData : undefined,
    queryFn: () => api<Page<AdminOrder>>(`admin/staff/orders?${queryParams.toString()}`),
    enabled: !!user && (user.is_staff || user.is_superuser || user.is_business_admin),
  });

  async function overrideOrder(order: AdminOrder, nextStatus: string) {
    if (nextStatus === order.status) return;
    const reason = await actionDialog.ask({ title: 'Update order status', message: `Change order #${order.orderId} from ${order.status} to ${nextStatus}?`, confirmLabel: 'Update status', reasonLabel: 'Reason' });
    if (reason === null) return;
    try {
      await api(`admin/staff/orders/${order.id}/status`, 'POST', { status: nextStatus, reason });
      notify(`Order #${order.orderId} changed to ${nextStatus}`);
      await client.invalidateQueries({ queryKey: ['admin', 'all_orders'] });
      await client.invalidateQueries({ queryKey: ['admin', 'dashboard'] });
    } catch (error) {
      notify((error as Error).message, true);
    }
  }

  if (!user?.is_staff && !user?.is_superuser && !user?.is_business_admin) {
    return (
      <Empty
        title="Administrator access required"
        text="Sign in with a staff or administrator account to manage customer orders."
        href="/admin"
        label="Back to dashboard"
      />
    );
  }

  return (
    <section className={storeId ? "section admin-store-orders" : "container section"} aria-label={storeId ? "Store orders" : "Customer orders"}>
      <div className="merchant-heading">
        <div>
          {storeId ? <h2>Store orders</h2> : <h1>Customer orders</h1>}
          <p>{storeId ? "Orders containing items from this store. Totals and status actions apply to the full customer order." : "Comprehensive order history, customer lookup, carrier tracking, and emergency status overrides."}</p>
        </div>
        {orders.data?.count !== undefined && (
          <div>
            <span className="badge" style={{ fontSize: '0.9rem', padding: '0.4rem 0.8rem' }}>
              {orders.data.count} total orders
            </span>
          </div>
        )}
      </div>

      <div className="merchant-toolbar" style={{ flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1.5rem' }}>
        <div className="search-box" style={{ flex: '1 1 280px' }}>
          <Search size={17} />
          <input
            aria-label="Search orders"
            placeholder="Search order ID, buyer email, coupon, courier, tracking…"
            value={search}
            onChange={event => { setSearch(event.target.value); setPage(1); }}
          />
        </div>
        <select
          aria-label="Filter orders by status"
          value={statusFilter}
          onChange={event => { setStatusFilter(event.target.value); setPage(1); }}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="confirmed">Confirmed</option>
          <option value="shipped">Shipped</option>
          <option value="delivered">Delivered</option>
          <option value="picked up">Picked up</option>
          <option value="cancelled">Cancelled</option>
          <option value="refunded">Refunded</option>
        </select>
        <select
          aria-label="Filter orders by courier"
          value={courierFilter}
          onChange={event => { setCourierFilter(event.target.value); setPage(1); }}
        >
          <option value="">All couriers</option>
          <option value="USPS">USPS</option>
          <option value="UPS">UPS</option>
          <option value="FEDEX">FedEx</option>
          <option value="DHL">DHL Express</option>
          <option value="DIGITAL">Digital / Instant</option>
        </select>
        <select
          aria-label="Filter orders by payment method"
          value={paymentFilter}
          onChange={event => { setPaymentFilter(event.target.value); setPage(1); }}
        >
          <option value="">All payment methods</option>
          <option value="card">Card</option>
          <option value="wallet">ProAce Wallet</option>
          <option value="cash_on_delivery">Cash on Delivery</option>
          <option value="stripe_wallet">Stripe Wallet</option>
        </select>
        <select
          aria-label="Sort orders"
          value={ordering}
          onChange={event => { setOrdering(event.target.value); setPage(1); }}
        >
          <option value="-created">Newest first</option>
          <option value="created">Oldest first</option>
          <option value="-total">Total: High to low</option>
          <option value="total">Total: Low to high</option>
        </select>
        {(search || statusFilter || courierFilter || paymentFilter || ordering !== '-created') && (
          <button
            type="button"
            className="button secondary"
            onClick={() => { setSearch(''); setStatusFilter(''); setCourierFilter(''); setPaymentFilter(''); setOrdering('-created'); setPage(1); }}
          >
            Reset
          </button>
        )}
      </div>

      {orders.isFetching && !orders.isLoading && <Loading compact overlay />}

      {orders.isLoading ? (
        <Loading />
      ) : orders.error ? (
        <ErrorState error={orders.error} retry={() => orders.refetch()} />
      ) : !orders.data?.results.length ? (
        <Empty
          title="No orders found"
          text={search || statusFilter || courierFilter || paymentFilter ? "No orders matched your search or filters." : (storeId ? "This store has no orders yet." : "No customer orders have been placed yet.")}
          onAction={() => {
            setSearch('');
            setStatusFilter('');
            setCourierFilter('');
            setPaymentFilter('');
            setOrdering('-created');
            setPage(1);
            void orders.refetch();
          }}
          label={search || statusFilter || courierFilter || paymentFilter ? "Reset filters" : "Refresh orders"}
        />
      ) : (
        <>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Buyer</th>
                  <th>Status</th>
                  <th>Payment</th>
                  <th>Shipping / Tracking</th>
                  <th>Total</th>
                  <th>Created</th>
                  <th>Updated</th>
                  <th>Emergency action</th>
                </tr>
              </thead>
              <tbody>
                {orders.data.results.map(order => (
                  <tr key={order.orderId}>
                    <td>
                      <button
                        type="button"
                        className="text-link"
                        aria-label={`View details for order ${order.orderId}`}
                        onClick={() => showNotificationRecord(order)}
                      >
                        #{order.orderId}
                      </button>
                    </td>
                    <td>{order.buyer_email || <span className="muted">Guest</span>}</td>
                    <td><Status value={order.status} /></td>
                    <td><span style={{ textTransform: 'capitalize' }}>{order.payment_type?.replaceAll('_', ' ') || 'card'}</span></td>
                    <td>
                      {order.tracking_number ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.85rem' }}>
                          <Truck size={14} color="var(--green)" />
                          {order.carrier || 'USPS'}: {order.tracking_number}
                        </span>
                      ) : (
                        <span className="muted">Pending shipment</span>
                      )}
                    </td>
                    <td><strong>{money(order.total)}</strong></td>
                    <td><DateStamp value={order.created} /></td>
                    <td><DateStamp value={order.updated} /></td>
                    <td>
                      {(() => {
                        const isDigital = isOrderAllDigital(order);
                        return (
                          <select
                            aria-label={`Override status for order ${order.orderId}`}
                            value={order.status}
                            disabled={order.status === 'refunded' || order.status === 'cancelled' || (isDigital && order.status === 'delivered')}
                            title={isDigital && order.status === 'delivered' ? 'Digital orders are delivered electronically' : undefined}
                            onChange={event => void overrideOrder(order, event.target.value)}
                          >
                            {getOrderOverrideOptions(order.status, isDigital).map(value => (
                              <option value={value} key={value}>{value}</option>
                            ))}
                          </select>
                        );
                      })()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} totalPages={Math.ceil(orders.data.count / 15)} onChange={setPage} />
        </>
      )}

      <DashboardDetailDialog detail={detail} onClose={() => {
          setDetail(null);
          clearNotificationDetail();
        }} />
      {actionDialog.dialog}
    </section>
  );
}

export function AdminCouponsPage() {
  const { user, notify } = useShop();
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const extraFilters = useCollectionFilters();
  useEffect(() => { setPage(1); }, [extraFilters.query]);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search);
  const [activeFilter, setActiveFilter] = useState('');
  const [ordering, setOrdering] = useState('-created');
  const [detail, setDetail] = useState<{ title: string; rows: [string, string][] } | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [code, setCode] = useState('');
  const [discount, setDiscount] = useState('10');
  const [numAvailable, setNumAvailable] = useState('100');
  const [validDays, setValidDays] = useState('30');
  const [creating, setCreating] = useState(false);
  const actionDialog = useActionDialog();

  const queryParams = new URLSearchParams({
    ...Object.fromEntries(new URLSearchParams(extraFilters.query)),
    limit: '15',
    offset: String((page - 1) * 15),
    ordering,
  });
  if (debouncedSearch.trim()) queryParams.set('search', debouncedSearch.trim());
  if (activeFilter) queryParams.set('active', activeFilter);

  const coupons = useQuery({
    queryKey: ['admin', 'all_coupons', page, debouncedSearch, activeFilter, ordering, extraFilters.query, user?.id],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey.at(-1) === user?.id ? previousData : undefined,
    queryFn: () => api<Page<AdminCoupon>>(`admin/staff/coupons?${queryParams.toString()}`),
    enabled: !!user && (user.is_staff || user.is_superuser || user.is_business_admin),
  });

  async function setCoupon(coupon: AdminCoupon, action: 'toggle' | 'delete') {
    const isUsed = Boolean(coupon.num_used > 0 || (coupon.redemptions && coupon.redemptions.length > 0));
    try {
      if (action === 'delete') {
        if (isUsed) {
          await actionDialog.ask({
            title: 'Coupon Cannot Be Deleted',
            message: `Coupon "${coupon.code}" has recorded customer redemptions (${coupon.num_used} used in orders). To preserve historical order records and financial audit trails, used coupons cannot be deleted from the database. Keeping the coupon deactivated ensures it can never be used again.`,
            confirmLabel: 'Understood',
          });
          return;
        }
        if (await actionDialog.ask({ title: 'Delete coupon', message: `Permanently delete unused coupon ${coupon.code}?`, confirmLabel: 'Delete' }) === null) return;
        await api(`admin/staff/coupons/${coupon.id}`, 'DELETE');
        notify(`Coupon ${coupon.code} deleted`);
      } else {
        await api(`admin/staff/coupons/${coupon.id}`, 'PATCH', { active: !coupon.active });
        notify(`Coupon ${coupon.code} ${coupon.active ? 'deactivated' : 'reactivated'}`);
      }
      await client.invalidateQueries({ queryKey: ['admin', 'all_coupons'] });
      await client.invalidateQueries({ queryKey: ['admin', 'coupons'] });
      await client.invalidateQueries({ queryKey: ['admin', 'dashboard'] });
    } catch (error) {
      notify((error as Error).message, true);
    }
  }

  async function handleCreateCoupon(event: FormEvent) {
    event.preventDefault();
    if (!code.trim()) return;
    setCreating(true);
    try {
      const now = new Date();
      const validTo = new Date(now.getTime() + parseInt(validDays, 10) * 86400000);
      await api('admin/staff/coupons', 'POST', {
        code: code.trim().toUpperCase(),
        discount: parseInt(discount, 10),
        num_available: parseInt(numAvailable, 10),
        valid_from: now.toISOString(),
        valid_to: validTo.toISOString(),
        active: true,
      });
      notify(`Coupon ${code.trim().toUpperCase()} created`);
      setCreateOpen(false);
      setCode('');
      await client.invalidateQueries({ queryKey: ['admin', 'all_coupons'] });
      await client.invalidateQueries({ queryKey: ['admin', 'coupons'] });
      await client.invalidateQueries({ queryKey: ['admin', 'dashboard'] });
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setCreating(false);
    }
  }

  if (!user?.is_staff && !user?.is_superuser && !user?.is_business_admin) {
    return (
      <Empty
        title="Administrator access required"
        text="Sign in with a staff or administrator account to manage promotion coupons."
        href="/admin"
        label="Back to dashboard"
      />
    );
  }

  return (
    <div className="container section">
      <div className="merchant-heading">
        <div>
          <h1>Coupons & promotions</h1>
          <p>Manage discount codes, monitor redemptions, deactivate expired offers, and audit creators.</p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          {coupons.data?.count !== undefined && (
            <span className="badge" style={{ fontSize: '0.9rem', padding: '0.4rem 0.8rem' }}>
              {coupons.data.count} total coupons
            </span>
          )}
          <button type="button" className="button" onClick={() => setCreateOpen(true)}>
            <Plus size={16} /> Create coupon
          </button>
        </div>
      </div>

      <div className="merchant-toolbar" style={{ flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1.5rem' }}>
        <div className="search-box" style={{ flex: '1 1 280px' }}>
          <Search size={17} />
          <input
            aria-label="Search coupons"
            placeholder="Search coupon code…"
            value={search}
            onChange={event => { setSearch(event.target.value); setPage(1); }}
          />
        </div>
        <select
          aria-label="Filter coupons by active status"
          value={activeFilter}
          onChange={event => { setActiveFilter(event.target.value); setPage(1); }}
        >
          <option value="">All coupons</option>
          <option value="true">Active only</option>
          <option value="false">Inactive only</option>
        </select>
        <select
          aria-label="Sort coupons"
          value={ordering}
          onChange={event => { setOrdering(event.target.value); setPage(1); }}
        >
          <option value="-created">Newest first</option>
          <option value="created">Oldest first</option>
          <option value="-discount">Highest discount</option>
          <option value="-num_used">Most used</option>
        </select>
        {(search || activeFilter || ordering !== '-created') && (
          <button
            type="button"
            className="button secondary"
            onClick={() => { setSearch(''); setActiveFilter(''); setOrdering('-created'); setPage(1); }}
          >
            Reset
          </button>
        )}
      </div>

      <CollectionFilters filters={extraFilters} label="additional filters" hideSearch fields={[{ key: 'type', label: 'Coupon type', options: ['order_total', 'product', 'product_quantity', 'category'].map(value => ({ value, label: value.replaceAll('_', ' ') })) }, { key: 'validity', label: 'Validity', options: ['current', 'expired', 'upcoming'].map(value => ({ value, label: value })) }, { key: 'created_by', label: 'Creator email' }]} />
      <button type="button" className="button secondary" onClick={() => {
        extraFilters.reset();
        setSearch('');
        setActiveFilter(''); setOrdering('-created'); setPage(1);
      }}>Reset all filters</button>
      {coupons.isFetching && !coupons.isLoading && <Loading compact overlay />}

      {coupons.isLoading ? (
        <Loading />
      ) : coupons.error ? (
        <ErrorState error={coupons.error} retry={() => coupons.refetch()} />
      ) : !coupons.data?.results.length ? (
        <Empty
          title="No coupons found"
          text={search || activeFilter || extraFilters.active ? "No coupons matched your search or filters." : "No promotion coupons have been configured yet."}
          onAction={() => {
            setSearch('');
            setActiveFilter('');
            setOrdering('-created');
            setPage(1);
            extraFilters.reset();
          }}
          label={search || activeFilter || extraFilters.active ? "Reset filters" : "Refresh coupons"}
        />
      ) : (
        <>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Discount</th>
                  <th>Status</th>
                  <th>Usage</th>
                  <th>Valid from</th>
                  <th>Valid to</th>
                  <th>Created by</th>
                  <th>Redemptions</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {coupons.data.results.map(coupon => (
                  <tr key={coupon.id}>
                    <td>
                      <button
                        type="button"
                        className="text-link"
                        aria-label={`View details for coupon ${coupon.code}`}
                        onClick={() => setDetail({
                          title: `Coupon ${coupon.code}`,
                          rows: [
                            ['Status', coupon.active ? 'Active' : 'Inactive'],
                            ['Discount', `${coupon.discount}%`],
                            ['Created by', coupon.created_by || 'Not recorded'],
                            ['Valid from', activityDate(coupon.valid_from)],
                            ['Valid to', activityDate(coupon.valid_to)],
                            ['Usage', `${coupon.num_used} of ${coupon.num_available}`],
                            ...(coupon.redemptions?.length ? [['Redemptions', `${coupon.redemptions.length} orders redeemed`] as [string, string]] : []),
                          ],
                        })}
                      >
                        {coupon.code}
                      </button>
                    </td>
                    <td>{coupon.discount}% off</td>
                    <td><Status value={coupon.active ? 'active' : 'inactive'} /></td>
                    <td>{coupon.num_used} / {coupon.num_available}</td>
                    <td><DateStamp value={coupon.valid_from} dateOnly /></td>
                    <td><DateStamp value={coupon.valid_to} dateOnly /></td>
                    <td><small>{coupon.created_by || 'Not recorded'}</small></td>
                    <td>{coupon.redemptions?.length || 0} orders</td>
                    <td>
                      <div className="form-actions" style={{ justifyContent: 'flex-start' }}>
                        <button
                          type="button"
                          className="button secondary"
                          onClick={() => void setCoupon(coupon, 'toggle')}
                        >
                          {coupon.active ? 'Deactivate' : 'Reactivate'}
                        </button>
                        <button
                          type="button"
                          className="icon-button"
                          aria-label={
                            coupon.num_used > 0
                              ? `Used coupon ${coupon.code} cannot be deleted (click to see reason)`
                              : `Delete unused coupon ${coupon.code}`
                          }
                          title={
                            coupon.num_used > 0
                              ? 'Used coupons cannot be deleted to preserve order records. Click for details.'
                              : 'Delete unused coupon'
                          }
                          onClick={() => void setCoupon(coupon, 'delete')}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} totalPages={Math.ceil(coupons.data.count / 15)} onChange={setPage} />
        </>
      )}

      {createOpen && (
        <div className="dialog-backdrop" role="presentation" onMouseDown={() => setCreateOpen(false)}>
          <section
            className="dialog-card"
            role="dialog"
            aria-modal="true"
            aria-label="Create promotion coupon"
            onMouseDown={event => event.stopPropagation()}
          >
            <div className="section-heading">
              <h2>Create promotion coupon</h2>
              <button className="icon-button" aria-label="Close" onClick={() => setCreateOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleCreateCoupon}>
              <Field label="Coupon code">
                <input
                  required
                  placeholder="e.g. FLASH20"
                  value={code}
                  onChange={e => setCode(e.target.value.toUpperCase())}
                />
              </Field>
              <div className="form-row" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <Field label="Discount percentage (%)">
                  <input
                    type="number"
                    min="1"
                    max="100"
                    required
                    value={discount}
                    onChange={e => setDiscount(e.target.value)}
                  />
                </Field>
                <Field label="Available count">
                  <input
                    type="number"
                    min="1"
                    required
                    value={numAvailable}
                    onChange={e => setNumAvailable(e.target.value)}
                  />
                </Field>
              </div>
              <Field label="Validity duration (days from now)">
                <input
                  type="number"
                  min="1"
                  required
                  value={validDays}
                  onChange={e => setValidDays(e.target.value)}
                />
              </Field>
              <div className="form-actions" style={{ marginTop: '1.5rem', justifyContent: 'flex-end' }}>
                <button type="button" className="button secondary" onClick={() => setCreateOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="button" disabled={creating}>
                  {creating ? 'Creating…' : 'Create coupon'}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}

      <DashboardDetailDialog detail={detail} onClose={() => setDetail(null)} />
      {actionDialog.dialog}
    </div>
  );
}

export function AdminRefundsPage() {
  const { user, notify } = useShop();
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search);
  const [statusFilter, setStatusFilter] = useState('');
  const [refundTypeFilter, setRefundTypeFilter] = useState('');
  const [ordering, setOrdering] = useState('-created');
  const [detail, setDetail] = useState<{ title: string; rows: [string, string][] } | null>(null);
  const actionDialog = useActionDialog();

  function showNotificationRecord(refund: AdminRefund): void {
    setDetail({
      title: `Refund #${refund.id}`,
      rows: [
        ['Order', `#${refund.order}`],
        ['Customer', refund.email],
        ['Method', refund.refund_type.replaceAll('_', ' ')],
        ['Status', refund.status],
        ...(refund.processed_by_email ? [['Processed by', refund.processed_by_email] as [string, string]] : []),
        ['Reason', refund.reason],
        ...(refund.provider_reference ? [['Provider Reference', refund.provider_reference] as [string, string]] : []),
        ...(refund.failure_reason ? [['Failure Details', refund.failure_reason] as [string, string]] : []),
        ['Created', activityDate(refund.created)],
      ],
    });
  }

  const clearNotificationDetail = useNotificationDetail<AdminRefund>('refund', 'admin/staff/refunds', showNotificationRecord);

  const queryParams = new URLSearchParams({
    limit: '15',
    offset: String((page - 1) * 15),
    ordering,
  });
  if (debouncedSearch.trim()) queryParams.set('search', debouncedSearch.trim());
  if (statusFilter) queryParams.set('status', statusFilter);
  if (refundTypeFilter) queryParams.set('refund_type', refundTypeFilter);

  const refunds = useQuery({
    queryKey: ['admin', 'all_refunds', page, debouncedSearch, statusFilter, refundTypeFilter, ordering, user?.id],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey.at(-1) === user?.id ? previousData : undefined,
    queryFn: () => api<Page<AdminRefund>>(`admin/staff/refunds?${queryParams.toString()}`),
    enabled: !!user && (user.is_staff || user.is_superuser || user.is_business_admin),
  });

  async function processRefund(refund: AdminRefund, action: 'approve' | 'decline') {
    const reason = await actionDialog.ask({ title: `${action === 'approve' ? 'Approve' : 'Decline'} refund #${refund.id}`, message: 'A reason is required for every refund decision.', confirmLabel: action === 'approve' ? 'Approve refund' : 'Decline refund', reasonLabel: 'Reason' });
    if (reason === null) return;
    try {
      const result = await api<{ detail: string }>(`admin/staff/refunds/${refund.id}/process`, 'POST', { action, reason });
      notify(result.detail);
      await client.invalidateQueries({ queryKey: ['admin', 'all_refunds'] });
      await client.invalidateQueries({ queryKey: ['admin', 'refunds'] });
      await client.invalidateQueries({ queryKey: ['admin', 'dashboard'] });
    } catch (error) {
      notify((error as Error).message, true);
    }
  }

  if (!user?.is_staff && !user?.is_superuser && !user?.is_business_admin) {
    return (
      <Empty
        title="Administrator access required"
        text="Sign in with a staff or administrator account to manage refund requests."
        href="/admin"
        label="Back to dashboard"
      />
    );
  }

  return (
    <div className="container section">
      <div className="merchant-heading">
        <div>
          <h1>Refund operations</h1>
          <p>Review customer refund requests, process payouts or wallet store credit, and track audit references.</p>
        </div>
        {refunds.data?.count !== undefined && (
          <div>
            <span className="badge" style={{ fontSize: '0.9rem', padding: '0.4rem 0.8rem' }}>
              {refunds.data.count} total refunds
            </span>
          </div>
        )}
      </div>

      <div className="merchant-toolbar" style={{ flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1.5rem' }}>
        <div className="search-box" style={{ flex: '1 1 280px' }}>
          <Search size={17} />
          <input
            aria-label="Search refunds"
            placeholder="Search order ID, email, reason, reference…"
            value={search}
            onChange={event => { setSearch(event.target.value); setPage(1); }}
          />
        </div>
        <select
          aria-label="Filter refunds by status"
          value={statusFilter}
          onChange={event => { setStatusFilter(event.target.value); setPage(1); }}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending review</option>
          <option value="approved">Approved</option>
          <option value="declined">Declined</option>
          <option value="failed">Failed</option>
        </select>
        <select
          aria-label="Filter refunds by refund method"
          value={refundTypeFilter}
          onChange={event => { setRefundTypeFilter(event.target.value); setPage(1); }}
        >
          <option value="">All refund methods</option>
          <option value="store_credit">Store Credit (Wallet)</option>
          <option value="original_payment">Original Payment Method</option>
        </select>
        <select
          aria-label="Sort refunds"
          value={ordering}
          onChange={event => { setOrdering(event.target.value); setPage(1); }}
        >
          <option value="-created">Newest first</option>
          <option value="created">Oldest first</option>
        </select>
        {(search || statusFilter || refundTypeFilter || ordering !== '-created') && (
          <button
            type="button"
            className="button secondary"
            onClick={() => { setSearch(''); setStatusFilter(''); setRefundTypeFilter(''); setOrdering('-created'); setPage(1); }}
          >
            Reset
          </button>
        )}
      </div>

      {refunds.isFetching && !refunds.isLoading && <Loading compact overlay />}

      {refunds.isLoading ? (
        <Loading />
      ) : refunds.error ? (
        <ErrorState error={refunds.error} retry={() => refunds.refetch()} />
      ) : !refunds.data?.results.length ? (
        <Empty
          title="No refund requests found"
          text={search || statusFilter || refundTypeFilter ? "No refunds matched your search or filters." : "No customer refund requests currently exist."}
          onAction={() => {
            setSearch('');
            setStatusFilter('');
            setRefundTypeFilter('');
            setOrdering('-created');
            setPage(1);
          }}
          label={search || statusFilter || refundTypeFilter ? "Reset filters" : "Refresh refunds"}
        />
      ) : (
        <>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Refund #</th>
                  <th>Order #</th>
                  <th>Customer</th>
                  <th>Method</th>
                  <th>Status</th>
                  <th>Processed by</th>
                  <th>Reason</th>
                  <th>Reference / Details</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {refunds.data.results.map(refund => (
                  <tr key={refund.id}>
                    <td>
                      <button
                        type="button"
                        className="text-link"
                        aria-label={`View details for refund ${refund.id}`}
                        onClick={() => showNotificationRecord(refund)}
                      >
                        #{refund.id}
                      </button>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="text-link"
                        aria-label={`View order ${refund.order} details`}
                        onClick={async () => {
                          try {
                            const order = await api<Order>(`orders/${refund.order}`);
                            setDetail({
                              title: `Order #${order.reference}`,
                              rows: [
                                ['Status', order.status],
                                ['Payment method', order.payment_type.replaceAll('_', ' ')],
                                ['Subtotal', money(order.subtotal)],
                                ['Total', money(order.total)],
                                ['Paid', money(order.paid_total)],
                                ['Refunded', money(order.refunded_total)],
                                ['Carrier', order.carrier || 'Not assigned'],
                                ['Tracking number', order.tracking_number || 'Not assigned'],
                                ['Items', `${order.items.length} items`],
                                ['Created', activityDate(order.created)],
                              ],
                            });
                          } catch (error) {
                            notify((error as Error).message, true);
                          }
                        }}
                      >
                        Order #{refund.order}
                      </button>
                    </td>
                    <td>{refund.email}</td>
                    <td><span style={{ textTransform: 'capitalize' }}>{refund.refund_type.replaceAll('_', ' ')}</span></td>
                    <td><Status value={refund.status} /></td>
                    <td>{refund.processed_by_email || '—'}</td>
                    <td title={refund.reason} style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {refund.reason}
                    </td>
                    <td>
                      {refund.provider_reference ? (
                        <small style={{ fontFamily: 'monospace' }}>{refund.provider_reference}</small>
                      ) : refund.failure_reason ? (
                        <small style={{ color: 'var(--red)' }}>{refund.failure_reason}</small>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td><DateStamp value={refund.created} dateOnly /></td>
                    <td>
                      <div className="form-actions" style={{ justifyContent: 'flex-start' }}>
                        {(refund.status === 'pending' || refund.status === 'failed') && (
                          <>
                            <button
                              type="button"
                              className="button"
                              onClick={() => void processRefund(refund, 'approve')}
                            >
                              {refund.status === 'failed' ? 'Retry Approve' : 'Approve'}
                            </button>
                            <button
                              type="button"
                              className="button secondary"
                              onClick={() => void processRefund(refund, 'decline')}
                            >
                              Decline
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} totalPages={Math.ceil(refunds.data.count / 15)} onChange={setPage} />
        </>
      )}

      <DashboardDetailDialog detail={detail} onClose={() => {
          setDetail(null);
          clearNotificationDetail();
        }} />
      {actionDialog.dialog}
    </div>
  );
}

export function AdminCommissionPage() {
  const { user, notify } = useShop();
  const client = useQueryClient();
  const actionDialog = useActionDialog();
  const [detail, setDetail] = useState<DashboardDetail | null>(null);
  const [preview, setPreview] = useState<{reference: string; amount: string; method: string; status: string; left: number; top: number} | null>(null);
  const filters = useCollectionFilters();
  const wallet = useQuery({
    queryKey: ['admin', 'commission-wallet', filters.query, user?.id],
    queryFn: () =>
      api<{
        earned: string;
        marketplace_commission?: string;
        official_stores_revenue?: string;
        withdrawn_or_pending: string;
        available: string;
        withdrawal_count: number;
        withdrawals: Array<{
          id: number;
          amount: string;
          payout_method: string;
          status: string;
          reference: string;
          created: string;
            processed_at: string | null;
            processing_note: string;
        }>;
      }>(`admin/staff/commission-wallet?${filters.query}`),
    enabled: Boolean(user?.is_superuser || user?.is_business_admin),
  });
  const [busy, setBusy] = useState(false);
  const [bankAccountId, setBankAccountId] = useState<number | null>(null);
  const [stripeDestinationId, setStripeDestinationId] = useState<number | null>(null);
  const [payoutMethod, setPayoutMethod] = useState<'stripe' | 'bank'>('stripe');
  async function processWithdrawal(
    withdrawal: NonNullable<typeof wallet.data>['withdrawals'][number],
    action: 'complete' | 'fail',
  ): Promise<void> {
    const note = await actionDialog.ask({
      title: `${action === 'complete' ? 'Complete' : 'Fail'} treasury withdrawal ${withdrawal.reference}`,
      message: action === 'complete'
        ? 'Confirm the external transfer has already been sent. Record its provider or bank reference.'
        : 'Record why this withdrawal failed. The reserved amount will return to available treasury funds.',
      confirmLabel: action === 'complete' ? 'Confirm transfer sent' : 'Mark withdrawal failed',
      reasonLabel: action === 'complete' ? 'Transfer confirmation note' : 'Failure reason',
    });
    if (note === null) return;

    setBusy(true);
    try {
      await api(
        `admin/staff/commission-wallet/withdrawals/${withdrawal.id}/process`,
        'POST',
        { action, note },
      );
      await client.invalidateQueries({ queryKey: ['admin', 'commission-wallet'] });
      notify(`Treasury withdrawal ${withdrawal.reference} marked ${action === 'complete' ? 'completed' : 'failed'}.`);
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  async function withdraw(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setBusy(true);
    const form = new FormData(formElement);
    try {
      await api('admin/staff/commission-wallet/withdraw', 'POST', {
        amount: form.get('amount'),
        payout_method: form.get('payout_method'),
        ...(form.get('payout_method') === 'bank'
          ? { bank_account_id: bankAccountId }
          : { stripe_destination_id: stripeDestinationId }),
      });
      formElement.reset();
      setPayoutMethod('stripe');
      setBankAccountId(null);
      setStripeDestinationId(null);
      await client.invalidateQueries({ queryKey: ['admin', 'commission-wallet'] });
      notify('Platform treasury withdrawal request created');
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  if (!user) return <Empty title="Admin sign-in required" text="Sign in to manage platform commissions." href="/login?next=/admin/commission" label="Sign in" />;
  if (!(user.is_superuser || user.is_business_admin)) return <Empty title="Administrator access only" text="Staff accounts cannot view or withdraw platform commissions." href="/admin" label="Back to dashboard" />;
  return (
    <div className="container section">
      <div className="merchant-heading">
        <div>
          <span className="eyebrow green">PLATFORM FINANCE</span>
          <h1>Platform Treasury & Commission</h1>
          <p>Withdraw accumulated 3P marketplace commission and official company store revenues through a centralized, audited workflow.</p>
        </div>
        <Link className="button secondary" href="/admin">Dashboard</Link>
      </div>
      {wallet.isFetching && !wallet.isLoading && <Loading compact overlay />}
      {wallet.isLoading ? (
        <Loading />
      ) : wallet.error ? (
        <ErrorState error={wallet.error} />
      ) : wallet.data && (
        <>
          <div className="stats-grid treasury-stats-grid">
            <div className="stat-item stat-0">
              <span>Total Treasury Earned</span>
              <strong>{money(wallet.data.earned)}</strong>
              <small>Combined cleared platform funds</small>
            </div>
            <div className="stat-item stat-1">
              <span>Marketplace Fees (3P)</span>
              <strong>{money(wallet.data.marketplace_commission || '0.00')}</strong>
              <small>4% commission from merchant sales</small>
            </div>
            <div className="stat-item stat-2">
              <span>Official Stores Net Sales</span>
              <strong>{money(wallet.data.official_stores_revenue || '0.00')}</strong>
              <small>100% net sales from company stores</small>
            </div>
            <div className="stat-item stat-3">
              <span>Available to Withdraw</span>
              <strong>{money(wallet.data.available)}</strong>
              <small>Cleared net after previous withdrawals</small>
            </div>
            <div className="stat-item stat-4">
              <span>Withdrawn or Pending</span>
              <strong>{money(wallet.data.withdrawn_or_pending)}</strong>
              <small>Audited platform withdrawals</small>
            </div>
          </div>
          <section className="analytics-panel treasury-withdrawal-panel" style={{ marginTop: '1.5rem' }}>
            <div className="treasury-withdrawal-heading">
              <div>
                <h2>Request treasury withdrawal</h2>
                <p>Choose an amount and destination for this withdrawal.</p>
              </div>
              <div className="treasury-available-balance">
                <span>Available to withdraw</span>
                <strong>{money(wallet.data.available)}</strong>
              </div>
            </div>
            <form className="treasury-withdrawal-form" onSubmit={withdraw}>
              <div className="treasury-withdrawal-fields">
                <Field label="Amount">
                  <input name="amount" type="number" min="0.01" step="0.01" max={wallet.data.available} required />
                </Field>
                <Field label="Payout method">
                  <select name="payout_method" value={payoutMethod} onChange={event => setPayoutMethod(event.target.value as 'stripe' | 'bank')}>
                    <option value="stripe">Stripe transfer</option>
                    <option value="bank">Bank transfer</option>
                  </select>
                </Field>
              </div>
              {payoutMethod === 'stripe' ? (
                <div className="treasury-bank-picker">
                  <StripePayoutDestinations
                    pickerOnly
                    selectedId={stripeDestinationId}
                    onSelect={setStripeDestinationId}
                  />
                </div>
              ) : (
                <div className="treasury-bank-picker">
                  <BankAccounts
                    compact
                    pickerOnly
                    selectedId={bankAccountId}
                    onSelect={setBankAccountId}
                  />
                </div>
              )}
              <button className="button compact treasury-withdrawal-submit" disabled={busy || Number(wallet.data.available) <= 0 || (payoutMethod === 'bank' ? !bankAccountId : !stripeDestinationId)}>
                {busy ? 'Submitting…' : 'Request withdrawal'}
              </button>
            </form>
          </section>
          <section className="merchant-section" style={{ marginTop: '2rem' }}>
            <h2>Withdrawal history</h2>
            <CollectionFilters filters={filters} label="withdrawals" fields={[
              { key: 'status', label: 'Status', options: [{ value: 'pending', label: 'Pending' }, { value: 'completed', label: 'Completed' }, { value: 'failed', label: 'Failed' }] },
              { key: 'payout_method', label: 'Method', options: [{ value: 'stripe', label: 'Stripe' }, { value: 'bank', label: 'Bank transfer' }] },
              ...financialFields,
            ]} />
            {typeof wallet.data.withdrawal_count === 'number' && (
              <CollectionCount count={wallet.data.withdrawal_count} />
            )}
            {!wallet.data.withdrawals.length && (
              <p className="muted">{filters.active ? 'No withdrawals match your filters.' : 'No withdrawals yet.'}</p>
            )}
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Reference</th>
                    <th>Amount</th>
                    <th>Method</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th><span className="sr-only">Actions</span>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {wallet.data.withdrawals.map(row => (
                    <tr key={row.id}>
                      <td>
                        <div className="treasury-reference-preview">
                          <button
                            type="button"
                            className="text-link"
                            onMouseEnter={event => {
                              const rect = event.currentTarget.getBoundingClientRect();
                              setPreview({reference: row.reference, amount: row.amount, method: row.payout_method, status: row.status, left: Math.min(rect.left, window.innerWidth - 240), top: Math.min(rect.bottom + 8, window.innerHeight - 110)});
                            }}
                            onFocus={event => {
                              const rect = event.currentTarget.getBoundingClientRect();
                              setPreview({reference: row.reference, amount: row.amount, method: row.payout_method, status: row.status, left: Math.min(rect.left, window.innerWidth - 240), top: Math.min(rect.bottom + 8, window.innerHeight - 110)});
                            }}
                            onBlur={() => setPreview(null)}
                            onMouseLeave={() => setPreview(null)}
                            onClick={() => setDetail({
                              title: `Withdrawal ${row.reference}`,
                              category: 'Treasury withdrawal',
                              rows: [
                                ['Reference', row.reference],
                                ['Amount', money(row.amount)],
                                ['Method', row.payout_method],
                                ['Status', row.status],
                                ['Created', new Date(row.created).toLocaleString()],
                                ...(row.processed_at ? [['Processed', new Date(row.processed_at).toLocaleString()] as [string, string]] : []),
                                ...(row.processing_note ? [['Processing note', row.processing_note] as [string, string]] : []),
                              ],
                            })}
                          >
                            {row.reference}
                          </button>

                        </div>
                      </td>
                      <td>{money(row.amount)}</td>
                      <td>{row.payout_method}</td>
                      <td><Status value={row.status} /></td>
                      <td><DateStamp value={row.created} /></td>
                      <td>
                        {row.status === 'pending' && (
                          <div className="table-actions admin-withdrawal-actions">
                            <button
                              type="button"
                              className="button compact"
                              disabled={busy}
                              onClick={() => void processWithdrawal(row, 'complete')}
                            >
                              Confirm
                            </button>
                            <button
                              type="button"
                              className="button secondary compact danger"
                              disabled={busy}
                              onClick={() => void processWithdrawal(row, 'fail')}
                            >
                              Fail
                            </button>
                          </div>
                        )}
                        {row.processing_note && <small>{row.processing_note}</small>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <CollectionPagination filters={filters} count={wallet.data.withdrawal_count} />
          </section>
        </>
      )}
      {preview && !detail && (
        <div className="treasury-reference-tooltip" role="tooltip" style={{left: preview.left, top: preview.top}}>
          <strong>{money(preview.amount)}</strong>
          <span>{preview.method} · {preview.status}</span>
          <span>Click to view and print details</span>
        </div>
      )}
      <DashboardDetailDialog detail={detail} onClose={() => { setDetail(null); setPreview(null); }} />
      {actionDialog.dialog}
    </div>
  );
}

export function AdminTaxesPage() {
  const { user, notify } = useShop();
  const queryClient = useQueryClient();
  const actionDialog = useActionDialog();

  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search);
  const [stateFilter, setStateFilter] = useState('');
  const debouncedState = useDebouncedValue(stateFilter);
  const [activeFilter, setActiveFilter] = useState('');

  const [editTarget, setEditTarget] = useState<AdminTaxJurisdiction | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [formCountry, setFormCountry] = useState('US');
  const [formState, setFormState] = useState('');
  const [formPostalCode, setFormPostalCode] = useState('');
  const [formName, setFormName] = useState('');
  const [formRate, setFormRate] = useState('');
  const [formTaxShipping, setFormTaxShipping] = useState(false);
  const [formTaxDigital, setFormTaxDigital] = useState(true);
  const [formIsActive, setFormIsActive] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const editDialogRef = useDialogFocus(Boolean(editTarget || isCreating), () => {
    setEditTarget(null);
    setIsCreating(false);
  });

  const queryParams = new URLSearchParams();
  if (debouncedSearch.trim()) queryParams.set('search', debouncedSearch.trim());
  if (debouncedState.trim()) queryParams.set('state', debouncedState.trim());
  if (activeFilter) queryParams.set('is_active', activeFilter);

  const taxes = useQuery({
    queryKey: ['admin', 'taxes', debouncedSearch, debouncedState, activeFilter, user?.id],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey.at(-1) === user?.id ? previousData : undefined,
    queryFn: () => api<AdminTaxesResponse>(`admin/taxes?${queryParams.toString()}`),
    enabled: !!(user?.is_staff || user?.is_superuser || user?.is_business_admin),
  });

  function openCreate() {
    setEditTarget(null);
    setFormCountry('US');
    setFormState('');
    setFormPostalCode('');
    setFormName('');
    setFormRate('');
    setFormTaxShipping(false);
    setFormTaxDigital(true);
    setFormIsActive(true);
    setIsCreating(true);
  }

  function openEdit(jurisdiction: AdminTaxJurisdiction): void {
    setIsCreating(false);
    setEditTarget(jurisdiction);
    setFormCountry(jurisdiction.country);
    setFormState(jurisdiction.state);
    setFormPostalCode(jurisdiction.postal_code || '');
    setFormName(jurisdiction.name);
    const percentage: number = Number(jurisdiction.rate) * 100;
    setFormRate(percentage.toFixed(3).replace(/\.?0+$/, ''));
    setFormTaxShipping(jurisdiction.tax_shipping);
    setFormTaxDigital(jurisdiction.tax_digital);
    setFormIsActive(jurisdiction.is_active);
  }

  async function handleFormSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setSubmitting(true);
    try {
      const parsedRate: string = formRate.trim().replace(/%$/, '').trim();
      const percentage: number = parsedRate === '' ? NaN : Number(parsedRate);
      if (!Number.isFinite(percentage) || percentage < 0 || percentage > 100) {
        throw new Error('Please enter a tax percentage between 0 and 100.');
      }
      const decimalRate: string = (percentage / 100).toFixed(5);

      if (isCreating) {
        await api<AdminTaxJurisdiction>('admin/taxes', 'POST', {
          country: formCountry.trim().toUpperCase() || 'US',
          state: formState.trim(),
          postal_code: formPostalCode.trim(),
          name: formName.trim(),
          rate: decimalRate,
          tax_shipping: formTaxShipping,
          tax_digital: formTaxDigital,
          is_active: formIsActive,
        });
        notify('Tax jurisdiction created successfully.');
      } else if (editTarget) {
        await api<AdminTaxJurisdiction>(`admin/taxes/${editTarget.id}`, 'PATCH', {
          country: formCountry.trim().toUpperCase() || 'US',
          state: formState.trim(),
          postal_code: formPostalCode.trim(),
          name: formName.trim(),
          rate: decimalRate,
          tax_shipping: formTaxShipping,
          tax_digital: formTaxDigital,
          is_active: formIsActive,
        });
        notify(`Updated ${formName || editTarget.name} successfully.`);
      }

      setIsCreating(false);
      setEditTarget(null);
      await queryClient.invalidateQueries({ queryKey: ['admin', 'taxes'] });
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(jurisdiction: AdminTaxJurisdiction) {
    const ok = await actionDialog.ask({
      title: 'Delete tax jurisdiction',
      message: `Delete tax rule for ${jurisdiction.name} (${jurisdiction.state} ${jurisdiction.postal_code || 'statewide'})? Historical order receipts will remain intact.`,
      confirmLabel: 'Delete',
    });
    if (ok === null) return;

    try {
      await api(`admin/taxes/${jurisdiction.id}`, 'DELETE');
      notify(`Removed ${jurisdiction.name}.`);
      await queryClient.invalidateQueries({ queryKey: ['admin', 'taxes'] });
    } catch (err) {
      notify((err as Error).message);
    }
  }

  async function handleToggleActive(jurisdiction: AdminTaxJurisdiction) {
    try {
      await api(`admin/taxes/${jurisdiction.id}`, 'PATCH', { is_active: !jurisdiction.is_active });
      notify(`${jurisdiction.name} is now ${!jurisdiction.is_active ? 'active' : 'inactive'}.`);
      await queryClient.invalidateQueries({ queryKey: ['admin', 'taxes'] });
    } catch (err) {
      notify((err as Error).message);
    }
  }

  async function handleRestoreDefaults() {
    const ok = await actionDialog.ask({
      title: 'Restore 50 US State Baselines',
      message: 'This will seed or update the standard statutory rates for all 50 US states and DC. Any custom ZIP code overrides you created will be preserved.',
      confirmLabel: 'Restore Baselines',
    });
    if (ok === null) return;

    try {
      const res = await api<{ detail: string }>('admin/taxes/seed-defaults', 'POST', {});
      notify(res.detail || 'Baseline rates restored.');
      await queryClient.invalidateQueries({ queryKey: ['admin', 'taxes'] });
    } catch (err) {
      notify((err as Error).message);
    }
  }

  return (
    <div className="container section admin-page">
      <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <span className="eyebrow green">COMPLIANCE & JURISDICTIONS</span>
          <h1>Destination Sales Tax Engine</h1>
          <p className="muted">Configure multi-jurisdiction destination sales taxes, state rates, municipal ZIP overrides, and taxability rules.</p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button type="button" className="button secondary" onClick={handleRestoreDefaults}>
            <RotateCcw size={16} /> Restore 50 US Baselines
          </button>
          <button type="button" className="button" onClick={openCreate}>
            <Plus size={16} /> Add Jurisdiction / Override
          </button>
        </div>
      </div>

      {taxes.data && (
        <div className="stats-grid" style={{ marginTop: '1.5rem', marginBottom: '2rem' }}>
          <div className="stat-item stat-0">
            <div>
              <span>Tax Calculation Mode</span>
              <Landmark size={19} />
            </div>
            <strong style={{ fontSize: '1.25rem', textTransform: 'capitalize' }}>
              {taxes.data.provider === 'stripe' ? 'Stripe Tax (Automated)' : 'Local Database Engine'}
            </strong>
            <small>
              {taxes.data.stripe_tax_enabled ? 'External Stripe Tax active with local fallback' : 'Destination statutory rates resolved from local database'}
            </small>
          </div>
          <div className="stat-item stat-1">
            <div>
              <span>Total Jurisdictions</span>
              <FileText size={19} />
            </div>
            <strong>{taxes.data.summary.total_jurisdictions}</strong>
            <small>{taxes.data.summary.active_jurisdictions} active compliance rules</small>
          </div>
          <div className="stat-item stat-2">
            <div>
              <span>ZIP Code Overrides</span>
              <Package size={19} />
            </div>
            <strong>{taxes.data.summary.zip_overrides}</strong>
            <small>Special municipal & county district overrides</small>
          </div>
          <div className="stat-item stat-3">
            <div>
              <span>Default Fallback Rate</span>
              <Check size={19} />
            </div>
            <strong>{(parseFloat(taxes.data.default_tax_rate) * 100).toFixed(2)}%</strong>
            <small>Used when destination has no rule configured</small>
          </div>
        </div>
      )}

      <div className="filter-bar" style={{ marginBottom: '1.5rem' }}>
        <div className="search-box">
          <Search size={18} />
          <input
            placeholder="Search by state, city, or ZIP code…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <input
          style={{ width: '130px' }}
          placeholder="State (e.g. CA)"
          value={stateFilter}
          onChange={e => setStateFilter(e.target.value.toUpperCase())}
        />
        <select
          aria-label="Filter status"
          value={activeFilter}
          onChange={e => setActiveFilter(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="true">Active only</option>
          <option value="false">Inactive only</option>
        </select>
        {(search || stateFilter || activeFilter) && (
          <button
            type="button"
            className="button secondary"
            onClick={() => { setSearch(''); setStateFilter(''); setActiveFilter(''); }}
          >
            Reset
          </button>
        )}
      </div>

      {taxes.isFetching && !taxes.isLoading && <Loading compact overlay />}

      {taxes.isLoading ? (
        <Loading />
      ) : taxes.error ? (
        <ErrorState error={taxes.error} retry={() => taxes.refetch()} />
      ) : !taxes.data?.results.length ? (
        <Empty
          title="No tax jurisdictions found"
          text={search || stateFilter || activeFilter ? "No tax rules matched your search or filters." : "No tax jurisdictions have been configured yet. Click 'Restore 50 US Baselines' in the header to initialize all standard US rates."}
          onAction={() => {
            setSearch('');
            setStateFilter('');
            setActiveFilter('');
          }}
          label={search || stateFilter || activeFilter ? "Reset filters" : "Refresh tax rules"}
        />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Region / Scope</th>
                <th>Jurisdiction Name</th>
                <th>Tax Rate</th>
                <th>Shipping Tax</th>
                <th>Digital Tax</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {taxes.data.results.map(jur => {
                const pct = (parseFloat(jur.rate) * 100).toFixed(3).replace(/\.?0+$/, '');
                return (
                  <tr key={jur.id}>
                    <td>
                      <strong>{jur.country} · {jur.state}</strong>
                      <small style={{ display: 'block', color: 'var(--muted)' }}>
                        {jur.postal_code ? `ZIP ${jur.postal_code} (District Override)` : 'Statewide Baseline'}
                      </small>
                    </td>
                    <td>{jur.name}</td>
                    <td>
                      <strong style={{ fontSize: '1.05rem', color: 'var(--green)' }}>{pct}%</strong>
                      <small style={{ display: 'block', color: 'var(--muted)' }}>({jur.rate})</small>
                    </td>
                    <td>
                      {jur.tax_shipping ? (
                        <span style={{ color: 'var(--amber)', fontSize: '0.85rem', fontWeight: 600 }}>Taxable</span>
                      ) : (
                        <span style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>Exempt</span>
                      )}
                    </td>
                    <td>
                      {jur.tax_digital ? (
                        <span style={{ color: 'var(--green)', fontSize: '0.85rem', fontWeight: 600 }}>Taxable</span>
                      ) : (
                        <span style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>Exempt</span>
                      )}
                    </td>
                    <td>
                      <button
                        type="button"
                        onClick={() => handleToggleActive(jur)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                        title="Click to toggle status"
                      >
                        <Status value={jur.is_active ? 'active' : 'inactive'} />
                      </button>
                    </td>
                    <td>
                      <div className="form-actions" style={{ justifyContent: 'flex-start', gap: '0.5rem' }}>
                        <button
                          type="button"
                          className="button secondary"
                          style={{ padding: '0.4rem 0.75rem', fontSize: '0.85rem' }}
                          onClick={() => openEdit(jur)}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="icon-button"
                          title={`Delete ${jur.name}`}
                          onClick={() => handleDelete(jur)}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / Edit Modal */}
      {(isCreating || editTarget) && (
        <div className="admin-dialog-backdrop" role="presentation" onMouseDown={e => e.target === e.currentTarget && (setIsCreating(false), setEditTarget(null))}>
          <section ref={editDialogRef} className="admin-dialog" role="dialog" aria-modal="true" aria-labelledby="tax-dialog-title" style={{ maxWidth: 560 }}>
            <div className="admin-dialog-head">
              <div>
                <span className="eyebrow green">{isCreating ? 'NEW JURISDICTION' : 'EDIT JURISDICTION'}</span>
                <h2 id="tax-dialog-title">{isCreating ? 'Add Tax Rule or ZIP Override' : `Edit ${editTarget?.name}`}</h2>
              </div>
              <button className="icon-button" aria-label="Close dialog" onClick={() => { setIsCreating(false); setEditTarget(null); }}>
                <X size={19} />
              </button>
            </div>

            <form onSubmit={handleFormSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <Field label="State / Territory Code (2 Letters)">
                  <input
                    required
                    placeholder="e.g. CA or NY"
                    value={formState}
                    onChange={e => setFormState(e.target.value.toUpperCase())}
                  />
                </Field>
                <Field label="Postal Code (Optional ZIP Prefix)">
                  <input
                    placeholder="e.g. 90210 or leave blank"
                    value={formPostalCode}
                    onChange={e => setFormPostalCode(e.target.value.trim())}
                  />
                </Field>
              </div>

              <Field label="Jurisdiction Label / Name">
                <input
                  required
                  placeholder="e.g. California State + Avg Local or NYC Special Rate"
                  value={formName}
                  onChange={e => setFormName(e.target.value)}
                />
              </Field>

              <Field label="Tax Rate (Percentage, e.g. 0.5 for 0.5%)">
                <input
                  required
                  placeholder="e.g. 8.85"
                  value={formRate}
                  onChange={e => setFormRate(e.target.value)}
                />
              </Field>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '0.5rem', padding: '0.75rem', background: 'var(--surface-sunken)', borderRadius: 'var(--radius)' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                  <input
                    type="checkbox"
                    checked={formTaxShipping}
                    onChange={e => setFormTaxShipping(e.target.checked)}
                  />
                  <span><strong>Tax Shipping Fees:</strong> Carrier shipping charges are subject to sales tax</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                  <input
                    type="checkbox"
                    checked={formTaxDigital}
                    onChange={e => setFormTaxDigital(e.target.checked)}
                  />
                  <span><strong>Tax Digital Downloads:</strong> Software, ebooks, and digital goods are taxable</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                  <input
                    type="checkbox"
                    checked={formIsActive}
                    onChange={e => setFormIsActive(e.target.checked)}
                  />
                  <span><strong>Active:</strong> Rule applies to incoming checkout and shipping quote calculations</span>
                </label>
              </div>

              <div className="form-actions" style={{ marginTop: '1rem', justifyContent: 'flex-end' }}>
                <button type="button" className="button secondary" onClick={() => { setIsCreating(false); setEditTarget(null); }}>
                  Cancel
                </button>
                <button type="submit" className="button" disabled={submitting}>
                  {submitting ? 'Saving…' : (isCreating ? 'Create Jurisdiction' : 'Save Changes')}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}

      {actionDialog.dialog}
    </div>
  );
}

