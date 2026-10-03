'use client';

import { FormEvent, useState } from 'react';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  ChartNoAxesCombined,
  DollarSign,
  LockKeyhole,
  Package,
  Plus,
  RotateCcw,
  Search,
  ShieldAlert,
  ShoppingBag,
  Store,
  Truck,
  UserRound,
  UserRoundCheck,
  UserRoundX,
  UsersRound,
  X,
} from 'lucide-react';
import { api, money } from '@/lib/api';
import type { AdminDashboardData, Page, StaffUser } from '@/lib/types';
import { useShop } from './providers';
import { Empty, ErrorState, Field, Loading, Status } from './ui';

export function AdminDashboardPage() {
  const { user, sessionLoading } = useShop();
  const [days, setDays] = useState('30');
  const dashboard = useQuery({
    queryKey: ['admin', 'dashboard', days],
    queryFn: () => api<AdminDashboardData>(`admin/staff/dashboard?days=${days}`),
    enabled: !!(user?.is_staff || user?.is_superuser),
  });

  if (sessionLoading) return <Loading />;
  if (!user) return <Empty title="Admin sign-in required" text="Sign in with a staff or administrator account to access platform insights." href="/login?next=/admin" label="Sign in" icon={<LockKeyhole size={36} />} />;
  if (!user.is_staff && !user.is_superuser) return <Empty title="Staff access only" text="Your account does not have permission to view administrative dashboards." href="/account" label="Back to your account" icon={<ShieldAlert size={36} />} />;

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
        <div className="form-actions">
          {user.is_superuser && (
            <Link className="button secondary" href="/admin/staff">
              <UsersRound size={17} />
              Manage staff team
            </Link>
          )}
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

      {dashboard.isLoading ? (
        <Loading />
      ) : dashboard.error ? (
        <ErrorState error={dashboard.error} retry={() => dashboard.refetch()} />
      ) : data && (
        <>
          <div className="stats-grid">
            <div className="stat-item stat-0">
              <div>
                <span>Gross Platform Revenue</span>
                <DollarSign size={19} />
              </div>
              <strong>{money(data.orders.gross_total)}</strong>
              <small>Paid orders over the last {days} days</small>
            </div>

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
          </div>

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
                <span style={{ background: '#fef3f2', color: '#b42318' }}><RotateCcw size={19} /></span>
                <div>
                  <strong>Refund Requests</strong>
                  <small>{data.refunds.pending} pending review · {data.refunds.accepted} approved</small>
                </div>
              </div>

              <div className="stock-row" style={{ alignItems: 'center' }}>
                <span style={{ background: '#eff8ff', color: '#175cd3' }}><ShoppingBag size={19} /></span>
                <div>
                  <strong>Catalog Products</strong>
                  <small>{data.products.published} published · {data.products.out_of_stock} out of stock</small>
                </div>
              </div>

              <div className="stock-row" style={{ alignItems: 'center' }}>
                <span style={{ background: '#fdf2fa', color: '#c11574' }}><ChartNoAxesCombined size={19} /></span>
                <div>
                  <strong>Active Promotions</strong>
                  <small>{data.coupons.active} live coupons · {data.marketers.total} affiliates</small>
                </div>
              </div>
            </section>
          </div>

          <section className="merchant-section" style={{ marginTop: '2.5rem' }}>
            <div className="section-heading">
              <h2>Top performing stores</h2>
              <span className="muted">Ranked by order volume</span>
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
                    {data.top_stores.map(store => (
                      <tr key={store.id}>
                        <td><strong>{store.name}</strong></td>
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
            <div className="section-heading">
              <h2>Recent platform orders</h2>
            </div>
            {!data.recent_orders.length ? (
              <p className="muted">No recent orders found.</p>
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
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_orders.map(order => (
                      <tr key={order.orderId}>
                        <td><strong>#{order.orderId}</strong></td>
                        <td>{order.buyer_email}</td>
                        <td><Status value={order.status} /></td>
                        <td>
                          {order.tracking_number ? (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.85rem' }}>
                              <Truck size={14} color="#0066cc" />
                              {order.carrier || 'USPS'}: {order.tracking_number}
                            </span>
                          ) : (
                            <span className="muted">Pending shipment</span>
                          )}
                        </td>
                        <td><strong>{money(order.total)}</strong></td>
                        <td>{new Date(order.created).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

export function AdminStaffPage() {
  const { user, sessionLoading, notify } = useShop();
  const client = useQueryClient();
  const [search, setSearch] = useState('');
  const [adding, setAdding] = useState(false);
  const staff = useQuery({
    queryKey: ['admin', 'staff', search],
    queryFn: () => api<Page<StaffUser>>(`admin/staff${search.trim() ? `?search=${encodeURIComponent(search.trim())}` : ''}`),
    enabled: !!user?.is_superuser,
  });
  const statusAction = useMutation({
    mutationFn: ({ id, action }: { id: number; action: 'block' | 'unblock' }) => api<StaffUser>(`admin/staff/${id}/${action}`, 'POST', {}),
    onSuccess: async (_, variables) => {
      await client.invalidateQueries({ queryKey: ['admin', 'staff'] });
      notify(`Staff member ${variables.action === 'block' ? 'blocked' : 'unblocked'}`);
    },
    onError: error => notify((error as Error).message, true),
  });

  if (sessionLoading) return <Loading />;
  if (!user) return <Empty title="Admin sign-in required" text="Sign in with an administrator account to manage staff." href="/login?next=/admin/staff" label="Sign in" icon={<LockKeyhole size={36} />} />;
  if (!user.is_superuser) return <Empty title="Administrator access only" text="Your account does not have permission to add, block, or unblock staff." href="/account" label="Back to your account" icon={<ShieldAlert size={36} />} />;

  const rows = staff.data?.results || [];
  return (
    <div className="container admin-staff-page section">
      <div className="admin-staff-heading">
        <div>
          <span className="eyebrow green">ADMINISTRATION</span>
          <h1>Staff management</h1>
          <p>Add trusted team members and control their access.</p>
        </div>
        <div className="form-actions">
          <Link className="button secondary" href="/admin">
            <ChartNoAxesCombined size={17} />
            Platform Dashboard
          </Link>
          <button className="button" onClick={() => setAdding(true)}>
            <Plus size={17} />
            Add staff
          </button>
        </div>
      </div>
      <div className="admin-staff-toolbar">
        <div className="search-box">
          <Search size={17} />
          <input aria-label="Search staff" placeholder="Search by name or email…" value={search} onChange={event => setSearch(event.target.value)} />
        </div>
        <span>{staff.data?.count || 0} staff account{staff.data?.count === 1 ? '' : 's'}</span>
      </div>
      {staff.isLoading ? (
        <Loading />
      ) : staff.error ? (
        <ErrorState error={staff.error} retry={() => staff.refetch()} />
      ) : rows.length ? (
        <div className="admin-staff-table table-scroll">
          <table>
            <thead>
              <tr>
                <th>Staff member</th>
                <th>Joined</th>
                <th>Status</th>
                <th>Access</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(member => (
                <tr key={member.id}>
                  <td>
                    <div className="admin-staff-person">
                      <span>{member.first_name?.[0] || member.email[0]}</span>
                      <div>
                        <strong>{`${member.first_name} ${member.last_name}`.trim() || 'Staff member'}</strong>
                        <small>{member.email}</small>
                      </div>
                    </div>
                  </td>
                  <td>{new Date(member.date_joined).toLocaleDateString('en-NG', { day: 'numeric', month: 'short', year: 'numeric' })}</td>
                  <td><Status value={member.is_active ? 'active' : 'blocked'} /></td>
                  <td>
                    <button
                      className={`button secondary ${member.is_active ? 'danger' : ''}`}
                      disabled={statusAction.isPending}
                      onClick={() => statusAction.mutate({ id: member.id, action: member.is_active ? 'block' : 'unblock' })}
                    >
                      {member.is_active ? <UserRoundX size={16} /> : <UserRoundCheck size={16} />}
                      {member.is_active ? 'Block' : 'Unblock'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="admin-staff-empty">
          <UsersRound size={36} />
          <h2>{search ? 'No staff found' : 'No staff accounts yet'}</h2>
          <p>{search ? 'Try a different name or email address.' : 'Add your first staff member to give them access.'}</p>
          {!search && <button className="button" onClick={() => setAdding(true)}>Add staff</button>}
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
    </div>
  );
}

function StaffDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => Promise<void> }) {
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
      <section className="admin-dialog" role="dialog" aria-modal="true" aria-labelledby="add-staff-title">
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
          <Field label="Temporary password"><input name="password" type="password" required minLength={8} maxLength={90} autoComplete="new-password" /></Field>
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
