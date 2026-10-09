'use client';

import { browserTimeZone, calendarDateLabel, toLocalDateTimeInput } from '@/lib/datetime';

import { activityDate } from './activity';
import { StoreBranding } from './store-branding';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FormEvent, useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Archive, ArrowDownToLine, ArrowLeft, ArrowRight, ArrowUpRight, Bell, ChartNoAxesCombined, Check, CheckCheck, ChevronLeft, ChevronRight, CircleHelp, Clock, Eye, FileText, Heart, Inbox, LayoutDashboard, Package, Plus, RotateCcw, Search, Settings, ShieldCheck, ShoppingBag, Star, Store as StoreIcon, Truck, Upload, WalletCards, X } from 'lucide-react';
import { api, categories, money } from '@/lib/api';
import type { Dashboard, MerchantProduct, NotificationCounts, NotificationItem, Page, ProductVariant, Store, StoreEarningsLedger, StorePayout, TrackingEvent, StoreProfile } from '@/lib/types';
import { useShop } from './providers';
import { Gate } from './account';
import { useDialogFocus, Pagination, Empty, ErrorState, Field, Loading, ProductImage, ProductGallery, FlashCountdown, Status, VerifiedBadge, normalizeImageUrl } from './ui';

type MerchantOrder = {
  id: number;
  reference: string;
  status: string;
  created: string;
  ordered: boolean;
  carrier?: string;
  tracking_number?: string;
  tracking_url?: string;
  shipped_at?: string | null;
  delivered_at?: string | null;
  tracking_events?: TrackingEvent[];
  items: { product: number; title: string; quantity: number }[];
};

type PreviewProduct = {
  title: string; description: string; brand: string; category: string; is_digital: boolean;
  price: number; sale_price: number; discount: number; available: number; image: string;
  variants: ProductVariant[]; digital_file_name?: string; digital_file_url?: string;
  images: string[]; flash_sale_end?: string | null; digital_preview_watermark?: boolean;
  product_type?: 'standard' | 'affiliate_clickbank';
  affiliate_hoplink?: string;
  affiliate_vendor_nickname?: string;
  affiliate_button_text?: string;
};


export function MerchantPage({ segments }: { segments: string[] }) {
  const { user } = useShop();
  const [selection, setSelection] = useState<{ owner: number; storeId: number | null } | null>(null);
  const selectionReady = !!user && selection?.owner === user.id;
  useEffect(() => {
    if (!user) { setSelection(null); return; }
    let storeId: number | null = null;
    try {
      const saved = Number(localStorage.getItem(`proace-active-store-${user.id}`));
      if (Number.isSafeInteger(saved) && saved > 0) storeId = saved;
    } catch { /* Storage may be unavailable; keep switching usable. */ }
    setSelection({ owner: user.id, storeId });
  }, [user?.id]);
  function selectStore(storeId: number) {
    if (!user) return;
    setSelection({ owner: user.id, storeId });
    try { localStorage.setItem(`proace-active-store-${user.id}`, String(storeId)); }
    catch { /* The current selection still works when storage is unavailable. */ }
  }
  const stores = useQuery({ queryKey: ['stores', user?.id], queryFn: () => api<Page<Store>>('stores?limit=100'), enabled: !!user, refetchInterval: 30000 });
  const selectedStore = useQuery({ queryKey: ['stores', 'selected', user?.id, selection?.storeId], queryFn: () => api<Store>(`stores/${selection?.storeId}`), enabled: !!user && selectionReady && !!selection?.storeId });
  const store = selectionReady ? (selectedStore.data?.id ? selectedStore.data : stores.data?.results.find(store => store.id === selection.storeId) || stores.data?.results[0]) : undefined;
  const section = segments[0] || 'overview';
  const storeLimitReached = !user?.is_superuser && !user?.is_business_admin && (stores.data?.count || 0) >= 10;

  const notifCounts = useQuery({
    queryKey: ['merchant-notifications-count', store?.id],
    queryFn: () => api<NotificationCounts>(`notifications/counts/?store=${store?.id}`),
    enabled: !!store?.id,
    refetchInterval: 12000,
  });

  const links = [
    ['overview', 'Overview', LayoutDashboard],
    ['products', 'Products', Package],
    ['orders', 'Orders', ShoppingBag],
    ['payments', 'Payments', WalletCards],
    ['notifications', 'Notifications', Bell],
    ['settings', 'Store settings', Settings],
  ] as const;

  return (
    <Gate next="/merchant">
      <div className="merchant-shell">
        <aside className="merchant-sidebar">
          <Link className="merchant-brand" href="/merchant">
            <span>
              <StoreIcon size={20} />
            </span>
            <div>
              Seller workspace
              <small>MAKE GOOD THINGS HAPPEN</small>
            </div>
          </Link>

          {store && (
            <label className="store-select">
              <span>YOUR STORE</span>
              <select
                aria-label="Select store"
                value={store.id}
                onChange={(event) => selectStore(Number(event.target.value))}
              >
                {stores.data?.results.map((store) => (
                  <option key={store.id} value={store.id}>
                    {store.name}
                  </option>
                ))}
              </select>
            </label>
          )}

          <nav>
            {links
              .filter(
                ([key]) =>
                  key !== 'payments' ||
                  !user?.is_staff ||
                  user?.is_superuser ||
                  user?.is_business_admin
              )
              .map(([key, name, Icon]) => (
                <Link
                  key={key}
                  className={section === key ? 'active' : ''}
                  href={key === 'overview' ? '/merchant' : `/merchant/${key}`}
                >
                  <Icon size={19} />
                  {name}
                  {key === 'products' && <ChevronRight size={14} />}
                  {key === 'notifications' && (notifCounts.data?.unread || 0) > 0 && (
                    <span
                      className="count-pill highlight"
                      style={{ marginLeft: 'auto', fontSize: 10, padding: '1px 6px' }}
                    >
                      {notifCounts.data!.unread}
                    </span>
                  )}
                </Link>
              ))}
          </nav>

          <div className="merchant-sidebar-bottom">
            {!storeLimitReached &&
              (!user?.is_staff || user?.is_superuser || user?.is_business_admin) && (
                <Link href="/merchant/new-store">
                  <Plus size={18} />
                  Open another store
                </Link>
              )}
            <Link href="/help">
              <CircleHelp size={18} />
              Help & support
            </Link>
            <Link href="/">
              <ArrowUpRight size={18} />
              Back to marketplace
            </Link>
            <div className="merchant-person">
              {user?.avatar_url ? (
                <img
                  src={user.avatar_url}
                  alt={user.first_name || 'User'}
                  style={{ width: 32, height: 32, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }}
                />
              ) : (
                <span>{user?.first_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}</span>
              )}
              <div>
                <strong>
                  {user?.first_name} {user?.last_name}
                </strong>
                <small>
                  {user?.is_staff ? 'Official store operations' : 'Store owner'}
                </small>
              </div>
            </div>
          </div>
        </aside>

        <div className="merchant-main">
          <div className="merchant-topline">
            <span>
              Workspace <ChevronRight size={12} />
              {section.replaceAll('-', ' ')}
            </span>
            <Link href={store ? `/shop?store=${store.id}` : '/shop'}>
              <Eye size={16} />
              View storefront <ArrowUpRight size={14} />
            </Link>
          </div>

          {stores.isLoading || !selectionReady ? (
            <Loading />
          ) : stores.error ? (
            <ErrorState error={stores.error} retry={() => stores.refetch()} />
          ) : !store || section === 'new-store' ? (
            user?.is_staff && !user?.is_superuser && !user?.is_business_admin ? (
              <Empty
                title="No official stores available"
                text="Official stores created by administrators will automatically appear here."
              />
            ) : storeLimitReached ? (
              <Empty
                title="10-store limit reached"
                text="You can create a maximum of 10 stores."
                href="/merchant"
                label="Back to your stores"
              />
            ) : (
              <OnboardStore />
            )
          ) : store.status === 'blocked' ? (
            <Empty
              title="Your store is unavailable"
              text="Contact support about your store status before making further changes."
              href="/help"
              label="Visit help centre"
            />
          ) : section === 'products' && segments[1] ? (
            <ProductEditor
              key={`${store.id}-${segments[1]}`}
              store={store}
              id={segments[1]}
            />
          ) : section === 'products' ? (
            <MerchantProducts key={store.id} store={store} />
          ) : section === 'orders' ? (
            <MerchantOrders key={store.id} store={store} />
          ) : section === 'payments' ? (
            <MerchantPayments key={store.id} store={store} />
          ) : section === 'notifications' ? (
            <MerchantNotifications key={store.id} store={store} />
          ) : section === 'settings' ? (
            <MerchantSettings key={store.id} store={store} />
          ) : (
            <MerchantDashboard key={store.id} store={store} />
          )}
        </div>
      </div>
    </Gate>
  );
}

function OnboardStore() {
  const { user, notify } = useShop();
  const client = useQueryClient();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    const data = Object.fromEntries(new FormData(event.currentTarget));

    try {
      await api('stores', 'POST', {
        name: data.name,
        profile: { email: data.email, bio: data.bio },
        address: {
          address: data.address,
          city: data.city,
          state: data.state,
          country: data.country,
          zip: data.zip,
        },
      });
      await client.invalidateQueries({ queryKey: ['stores'] });
      notify('Your store is ready. Time for your first product.');
      router.push('/merchant/products/new');
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="onboarding">
      <span className="eyebrow green">YOUR NEXT CHAPTER</span>
      <h1>A home for your business.</h1>
      <p className="muted">Introduce your store. Add your products. Meet your customers.</p>
      <div className="onboarding-steps">
        <span className="active">
          <b>1</b>Store details
        </span>
        <ChevronRight size={16} />
        <span>
          <b>2</b>Your first product
        </span>
        <ChevronRight size={16} />
        <span>
          <b>3</b>Open for business
        </span>
      </div>

      <form className="form-stack" onSubmit={submit}>
        <h2>Let’s make it official</h2>
        <div className="form-row">
          <Field label="Store name">
            <input name="name" required maxLength={40} placeholder="Something memorable" />
          </Field>
          <Field label="Contact email">
            <input type="email" name="email" required defaultValue={user?.email} />
          </Field>
        </div>
        <Field label="About your store">
          <textarea name="bio" placeholder="A little about what makes your store yours" />
        </Field>
        <h3>Business address</h3>
        <p className="muted">
          Required for every store, including digital sellers. Physical orders use this as the pickup address.
        </p>
        <Field label="Street address">
          <input name="address" required />
        </Field>
        <div className="form-row">
          <Field label="City">
            <input name="city" required />
          </Field>
          <Field label="State / region">
            <input name="state" required maxLength={30} />
          </Field>
        </div>
        <div className="form-row">
          <Field label="Country">
            <input name="country" required />
          </Field>
          <Field label="Postal code">
            <input name="zip" required maxLength={10} />
          </Field>
        </div>
        {error && <p className="form-error">{error}</p>}
        <button className="button" disabled={busy}>
          {busy ? 'Creating your store…' : 'Create my store'}
          <ArrowRight size={17} />
        </button>
      </form>
    </section>
  );
}

function MerchantDashboard({ store }: { store: Store }) {
  const [days, setDays] = useState('30'); const { user, notify } = useShop(); const client = useQueryClient();
  const stats = useQuery({ queryKey: ['dashboard', store.id, days], queryFn: () => api<Dashboard>(`stores/${store.id}/dashboard?days=${days}&time_zone=${encodeURIComponent(browserTimeZone())}`) });
  const orders = useQuery({ queryKey: ['merchant-recent', store.id], queryFn: () => api<Page<MerchantOrder>>(`stores/${store.id}/orders?limit=5`) });
  const payouts = useQuery({ queryKey: ['merchant-payouts', store.id], queryFn: () => api<StorePayout[]>(`stores/${store.id}/payouts`) });
  const checklist = useQuery({ queryKey: ['onboarding', store.id], queryFn: () => api<{complete: boolean; steps: Record<string, boolean>}>(`stores/${store.id}/onboarding`) });
  const [requestingPayout, setRequestingPayout] = useState(false);
  const [payoutAmount, setPayoutAmount] = useState('');
  const [bankName, setBankName] = useState('');
  const [accountNumber, setAccountNumber] = useState('');
  const [payoutBusy, setPayoutBusy] = useState(false);
  const data = stats.data;
  const values = data?.orders_by_day.slice(-30) || []; const max = Math.max(1, ...values.map(day => day.count));

  async function submitPayout(event: FormEvent) {
    event.preventDefault(); setPayoutBusy(true);
    try {
      await api(`stores/${store.id}/payouts`, 'POST', {
        amount: payoutAmount,
        payout_method: 'bank_transfer',
        account_details: { bank_name: bankName, account_number: accountNumber },
      });
      await client.invalidateQueries({ queryKey: ['dashboard', store.id] });
      await client.invalidateQueries({ queryKey: ['merchant-payouts', store.id] });
      notify('Payout request submitted. Staff will review and process your transfer.');
      setRequestingPayout(false);
      setPayoutAmount('');
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setPayoutBusy(false);
    }
  }

  const isOfficial = Boolean(store.is_official || user?.is_superuser);
  const currentTier = store.seller_tier?.tier;
  const [showCelebration, setShowCelebration] = useState(false);

  useEffect(() => {
    if (currentTier && currentTier !== 'starter' && currentTier !== 'official') {
      const storageKey = `celebrated_tier_${store.id}_${currentTier}`;
      if (!localStorage.getItem(storageKey)) {
        setShowCelebration(true);
      }
    }
  }, [currentTier, store.id]);

  function dismissCelebration() {
    if (currentTier) {
      localStorage.setItem(`celebrated_tier_${store.id}_${currentTier}`, 'true');
    }
    setShowCelebration(false);
  }

  return (
    <>
      {showCelebration && (
        <div
          style={{
            background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
            color: "#fff",
            borderRadius: "12px",
            padding: "20px 24px",
            marginBottom: "24px",
            boxShadow: "0 10px 25px rgba(0,0,0,0.15)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "16px",
            flexWrap: "wrap",
            border: "1px solid rgba(255,255,255,0.1)"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <div style={{ fontSize: "32px" }}>🎉</div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <h3 style={{ margin: 0, fontSize: "17px", color: "#fff" }}>
                  Congratulations! You unlocked {store.seller_tier?.name} Rank
                </h3>
                <VerifiedBadge tierData={store.seller_tier} size={20} />
              </div>
              <p style={{ margin: "4px 0 0", fontSize: "13px", color: "#94a3b8" }}>
                Your cumulative sales have passed {money(store.seller_tier?.min_sales || 0)}. Your store profile and products now display the verified {store.seller_tier?.name} badge!
              </p>
            </div>
          </div>
          <button
            className="button"
            style={{ background: store.seller_tier?.badge_hex || "#1d9bf0", borderColor: "transparent", color: "#fff" }}
            onClick={dismissCelebration}
          >
            Claim & Continue
          </button>
        </div>
      )}
      {store.status === 'pending' && !isOfficial && (
        <p className="muted" role="status">
          Your store is awaiting staff verification. You can prepare product drafts while we review it; products cannot be published until approval.
        </p>
      )}
      <div className="merchant-heading">
        <div>
          <span className="eyebrow green">LET’S MAKE IT A GOOD DAY</span>
          <h1>Hello, {user?.first_name}.</h1>
          <p style={{ display: 'inline-flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            Here’s what’s happening at {store.name}.
            <VerifiedBadge
              tier={isOfficial ? 'official' : 'starter'}
              tierData={store.seller_tier}
              size={17}
            />
            <span
              className={`seller-tier-pill ${
                isOfficial
                  ? 'tier-official'
                  : store.seller_tier?.tier
                    ? `tier-${store.seller_tier.tier}`
                    : 'tier-starter'
              }`}
            >
              {isOfficial ? 'Official Store' : (store.seller_tier?.name ? `${store.seller_tier.name} Seller` : 'Starter')}
            </span>
          </p>
        </div>
        <div className="form-actions">
          {isOfficial ? (
            (user?.is_superuser || user?.is_business_admin) ? (
              <Link className="button secondary" href="/admin/commission" title="Official company store earnings consolidate into Platform Treasury">
                <WalletCards size={17} />
                Platform Treasury
              </Link>
            ) : null
          ) : (
            <button className="button secondary" onClick={() => setRequestingPayout(true)}>
              <WalletCards size={17} />
              Request payout
            </button>
          )}
          <Link className="button" href="/merchant/products/new">
            <Plus size={17} />
            Add product
          </Link>
        </div>
      </div>

      {!isOfficial && store.seller_tier?.next_tier && store.seller_tier.next_threshold && (
        <div className="tier-progress-banner">
          <div>
            <strong className="tier-progress-title">
              Seller Level: <VerifiedBadge tierData={store.seller_tier} size={15} /> {store.seller_tier.name}
            </strong>
            <small className="tier-progress-subtext">
              Total Sales: {money(store.seller_tier.current_sales || 0)} · Reach {money(store.seller_tier.next_threshold)} to unlock <strong>{store.seller_tier.next_tier}</strong> badge
            </small>
          </div>
          <div className="tier-progress-bar-wrap">
            <div className="tier-progress-track">
              <div
                className="tier-progress-fill"
                style={{
                  background: store.seller_tier.badge_hex || 'var(--green)',
                  width: `${Math.min(100, Math.round(((store.seller_tier.current_sales || 0) / store.seller_tier.next_threshold) * 100))}%`
                }}
              />
            </div>
            <div className="tier-progress-labels">
              <span>{money(store.seller_tier.current_sales || 0)}</span>
              <span>Next: {store.seller_tier.next_tier} ({money(store.seller_tier.next_threshold)})</span>
            </div>
          </div>
        </div>
      )}

      <div className="dashboard-period">
        <h2>Your store at a glance</h2>
        <select
          aria-label="Dashboard period"
          value={days}
          onChange={(event) => setDays(event.target.value)}
        >
          <option value="7">Last 7 days</option>
          <option value="30">Last 30 days</option>
          <option value="90">Last 90 days</option>
        </select>
      </div>

      {stats.isLoading ? (
        <Loading />
      ) : stats.error ? (
        <ErrorState error={stats.error} retry={() => stats.refetch()} />
      ) : (
        data && (
          <>
            <div className="stats-grid">
              {[
                {
                  label: 'Available for Payout',
                  value: money(data.wallet?.available_balance || '0.00'),
                  icon: WalletCards,
                  note: 'Cleared sales past 7-day refund window',
                },
                {
                  label: 'In Review (Escrow)',
                  value: money(data.wallet?.in_review || '0.00'),
                  icon: Clock,
                  note: 'Orders within 7-day refund period',
                },
                {
                  label: isOfficial
                    ? 'Gross Sales (100% Retained)'
                    : 'Gross Sales (Item Value)',
                  value: money(
                    data.wallet?.gross_sales || data.sales.estimated_item_value
                  ),
                  icon: ChartNoAxesCombined,
                  note: isOfficial
                    ? 'Total sales with 0% platform fee'
                    : 'Total item sales before 4% platform fee',
                },
                {
                  label: isOfficial
                    ? 'Platform Fee (0%)'
                    : `Platform Commission (${data.wallet?.platform_fee_percent || '4'}%)`,
                  value: isOfficial
                    ? '$0.00'
                    : money(data.wallet?.platform_fee_deducted || '0.00'),
                  icon: ShoppingBag,
                  note: isOfficial
                    ? 'Official company store exemption (0% fee)'
                    : 'Marketplace hosting & payment processing',
                },
              ].map(({ label, value, icon: Icon, note }, index) => (
                <div key={label} className={`stat-item stat-${index}`}>
                  <div>
                    <span>{label}</span>
                    <Icon size={19} />
                  </div>
                  <strong>{value}</strong>
                  <small>{note}</small>
                </div>
              ))}
            </div>

            {requestingPayout && !isOfficial && (
              <div
                className="setup-notice"
                style={{ flexDirection: 'column', alignItems: 'stretch' }}
              >
                <h3>Request Merchant Payout</h3>
                <p className="muted">
                  Withdraw available cleared funds directly to your bank account.
                </p>
                <form className="form-stack" onSubmit={submitPayout}>
                  <div className="form-row">
                    <Field
                      label={`Payout amount (Max: ${money(data.wallet?.available_balance || '0.00')})`}
                    >
                      <input
                        type="number"
                        min="5.00"
                        max={Number(data.wallet?.available_balance || '0')}
                        step="0.01"
                        required
                        value={payoutAmount}
                        onChange={(e) => setPayoutAmount(e.target.value)}
                        placeholder="0.00"
                      />
                    </Field>
                    <Field label="Bank Name">
                      <input
                        required
                        value={bankName}
                        onChange={(e) => setBankName(e.target.value)}
                        placeholder="e.g. JPMorgan Chase"
                      />
                    </Field>
                  </div>
                  <Field label="Account Number / IBAN">
                    <input
                      required
                      value={accountNumber}
                      onChange={(e) => setAccountNumber(e.target.value)}
                      placeholder="e.g. 1234567890"
                    />
                  </Field>
                  <div className="form-row">
                    <button className="button" disabled={payoutBusy}>
                      {payoutBusy ? 'Submitting…' : 'Submit withdrawal request'}
                    </button>
                    <button
                      type="button"
                      className="button secondary"
                      onClick={() => setRequestingPayout(false)}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            )}

            {checklist.data && !checklist.data.complete && (
              <div className="setup-notice">
                <span className="setup-check">
                  <StoreIcon size={23} />
                </span>
                <div>
                  <strong>Your store is taking shape.</strong>
                  <p>
                    {Object.values(checklist.data.steps).filter(Boolean).length} of{' '}
                    {Object.values(checklist.data.steps).length} setup steps complete.
                  </p>
                </div>
                <Link
                  className="text-link"
                  href={
                    checklist.data.steps.product_added
                      ? '/merchant/settings'
                      : '/merchant/products/new'
                  }
                >
                  Continue setup <ArrowRight size={16} />
                </Link>
              </div>
            )}

            <div className="dashboard-columns">
              <section className="analytics-panel">
                <div className="section-heading">
                  <div>
                    <h2>Order activity</h2>
                    <p>
                      {data.orders.total} orders in the last {days} days
                    </p>
                  </div>
                  <span className="chart-legend">
                    <i />
                    Orders
                  </span>
                </div>
                <div
                  className="bar-chart"
                  role="img"
                  aria-label={`Order activity: ${data.orders.total} orders in ${days} days`}
                >
                  <div className="chart-y">
                    <span>{max}</span>
                    <span>{max / 2}</span>
                    <span>0</span>
                  </div>
                  <div className="chart-bars">
                    {values.map((day, index) => (
                      <div
                        className="chart-column"
                        key={day.date}
                        title={`${day.date}: ${day.count} orders`}
                      >
                        <span
                          style={{
                            height: `${(day.count / max) * 100}%`,
                            minHeight: day.count ? 5 : 1,
                          }}
                        />
                        <small>
                          {index === 0 ||
                          index === values.length - 1 ||
                          (index % 7 === 0 && index < values.length - 3)
                            ? calendarDateLabel(day.date)
                            : ''}
                        </small>
                      </div>
                    ))}
                  </div>
                </div>
              </section>

              <section className="stock-panel">
                <div className="section-heading">
                  <h2>Needs a little attention</h2>
                  <span className="stock-number">
                    {data.inventory.low_stock + data.inventory.out_of_stock}
                  </span>
                </div>
                <p className="muted">Keep your best finds in stock.</p>
                {data.low_stock_products.length ? (
                  data.low_stock_products.slice(0, 4).map((product) => (
                    <Link
                      className="stock-row"
                      href={`/merchant/products/${product.id}`}
                      key={product.id}
                    >
                      <span>
                        <Package size={19} />
                      </span>
                      <div>
                        <strong>{product.title}</strong>
                        <small>
                          {product.available
                            ? `${product.available} units left`
                            : 'Out of stock'}
                        </small>
                      </div>
                      <ArrowUpRight size={16} />
                    </Link>
                  ))
                ) : (
                  <div className="all-good">
                    <Check size={26} />
                    <strong>Looking good.</strong>
                    <p>Your inventory is in a healthy place.</p>
                  </div>
                )}
                <Link className="text-link" href="/merchant/products">
                  Manage inventory <ArrowRight size={16} />
                </Link>
              </section>
            </div>

            <section className="merchant-section">
              <div className="section-heading">
                <h2>Recent orders</h2>
                <Link className="text-link" href="/merchant/orders">
                  View all orders <ArrowRight size={16} />
                </Link>
              </div>
              {orders.isLoading ? (
                <Loading />
              ) : orders.error ? (
                <ErrorState error={orders.error} />
              ) : (
                <MerchantOrderTable
                  orders={orders.data?.results || []}
                  storeId={store.id}
                  onUpdated={() => {
                    client.invalidateQueries({
                      queryKey: ['merchant-recent', store.id],
                    });
                    client.invalidateQueries({
                      queryKey: ['dashboard', store.id],
                    });
                    client.invalidateQueries({
                      queryKey: ['merchant-orders', store.id],
                    });
                  }}
                />
              )}
            </section>

            <section className="merchant-section">
              <div className="section-heading">
                <h2>Payout history</h2>
                <span className="muted">
                  {payouts.data?.length || 0} payout requests
                </span>
              </div>
              {payouts.isLoading ? (
                <Loading />
              ) : payouts.error ? (
                <ErrorState error={payouts.error} />
              ) : !payouts.data?.length ? (
                <p className="muted">No payouts requested yet.</p>
              ) : (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Reference</th>
                        <th>Amount</th>
                        <th>Method</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {payouts.data.map((p) => (
                        <tr key={p.id}>
                          <td>{new Date(p.created).toLocaleDateString()}</td>
                          <td>
                            <strong>{p.reference}</strong>
                          </td>
                          <td>{money(p.amount)}</td>
                          <td>{p.payout_method}</td>
                          <td>
                            <Status value={p.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <div className="dashboard-footnote">
              {isOfficial
                ? 'Company official store: 100% of sales are retained and consolidated into the Platform Treasury at /admin/commission.'
                : 'Net sales are calculated at 96% after the 4% platform fee. Funds clear from review to your available payout balance after the 7-day customer refund window expires.'}
            </div>
          </>
        )
      )}
    </>
  );
}

function exportRows(products: MerchantProduct[]) {
  const escape = (value: unknown) =>
    `"${String(value).replace(/^[=+@-]/, "'$&").replaceAll('"', '""')}"`;

  const rows = [
    ['ID', 'Product', 'Price', 'Stock', 'Published'],
    ...products.map((product) => [
      product.id,
      product.title,
      product.price,
      product.is_digital ? 'Unlimited' : product.available,
      product.visibility,
    ]),
  ];

  const csvContent = rows.map((row) => row.map(escape).join(',')).join('\r\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');

  link.href = url;
  link.download = 'proace-products.csv';
  link.click();
  URL.revokeObjectURL(url);
}

function MerchantProducts({ store }: { store: Store }) {
  const [ordering, setOrdering] = useState<string>('-updated');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('');
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState<number | null>(null);
  const { notify } = useShop();
  const client = useQueryClient();

  const query = new URLSearchParams({ search, ordering, limit: '15', offset: String(offset) });
  if (filter) {
    query.set('visibility', filter);
  }

  const products = useQuery({
    queryKey: ['merchant-products', store.id, query.toString()],
    queryFn: () => api<Page<MerchantProduct>>(`stores/${store.id}/products?${query}`),
  });

  async function toggle(product: MerchantProduct) {
    setBusy(product.id);
    try {
      await api(`stores/${store.id}/products/${product.id}`, 'PATCH', {
        visibility: !product.visibility,
      });
      await client.invalidateQueries({ queryKey: ['merchant-products'] });
      await client.invalidateQueries({ queryKey: ['dashboard'] });
      await client.invalidateQueries({ queryKey: ['products'] });
      notify(product.visibility ? 'Product unpublished' : 'Your product is live');
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setBusy(null);
    }
  }

function parseCsvRows(text: string): string[][] {
  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentField = '';
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    const nextChar = text[i + 1];

    if (inQuotes) {
      if (char === '"' && nextChar === '"') {
        currentField += '"';
        i++; // skip escaped quote
      } else if (char === '"') {
        inQuotes = false;
      } else {
        currentField += char;
      }
    } else {
      if (char === '"') {
        inQuotes = true;
      } else if (char === ',') {
        currentRow.push(currentField);
        currentField = '';
      } else if (char === '\r') {
        if (nextChar === '\n') {
          i++;
        }
        currentRow.push(currentField);
        if (currentRow.some(field => field.trim().length > 0)) {
          rows.push(currentRow);
        }
        currentRow = [];
        currentField = '';
      } else if (char === '\n') {
        currentRow.push(currentField);
        if (currentRow.some(field => field.trim().length > 0)) {
          rows.push(currentRow);
        }
        currentRow = [];
        currentField = '';
      } else {
        currentField += char;
      }
    }
  }

  if (inQuotes) throw new Error('CSV contains an unterminated quoted field.');
  if (currentField.length > 0 || currentRow.length > 0) {
    currentRow.push(currentField);
    if (currentRow.some(field => field.trim().length > 0)) {
      rows.push(currentRow);
    }
  }

  return rows;
}

  async function handleCsvImport(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) { notify('CSV files must be at most 2 MB.', true); return; }
    const text = await file.text();
    let rows: string[][];
    try { rows = parseCsvRows(text); } catch (error) { notify((error as Error).message, true); return; }
    if (rows.length < 2) {
      notify('CSV file is empty or missing rows.', true);
      return;
    }
    if (rows.length > 501) { notify('Import at most 500 products per CSV.', true); return; }
    const headers = rows[0].map(h => h.trim().toLowerCase().replace(/^["']|["']$/g, ''));
    let count = 0;
    const failedRows: number[] = [];
    for (let i = 1; i < rows.length; i++) {
      const values = rows[i].map(v => v.trim());
      if (values.length < 2 || !values[0]) continue;
      const row: Record<string, string> = {};
      headers.forEach((header, idx) => {
        row[header] = values[idx] || '';
      });
      const title = row['title'] || row['product'] || values[0];
      const priceText = row['price'] || values[1] || '';
      if (!/^\d+(?:\.\d{1,2})?$/.test(priceText)) { failedRows.push(i + 1); continue; }
      const price = Number(priceText);
      const category = row['category'] || 'sports';
      const available = Number(row['stock'] || row['available'] || values[2] || 10);
      const description = row['description'] || `${title} - Quality listing`;
      const brand = row['brand'] || store.name;
      const imageUrl = row['image_url'] || row['image'] || '';
      let variantsList: ProductVariant[] = [];
      if (row['variants']) {
        try {
          if (row['variants'].startsWith('[')) {
            variantsList = JSON.parse(row['variants']);
          } else {
            variantsList = row['variants'].split(';').map(part => {
              const [vName, vDelta, vStock] = part.split(':');
              return { name: vName?.trim() || '', price_delta: vDelta?.trim() || '0.00', available: Number(vStock || 10) };
            }).filter(v => v.name);
          }
        } catch (_) { failedRows.push(i + 1); continue; }
        if (!Array.isArray(variantsList) || variantsList.length > 100) { failedRows.push(i + 1); continue; }
      }
      if (!Number.isFinite(price) || price <= 0 || !Number.isSafeInteger(available) || available < 0) { failedRows.push(i + 1); continue; }
      try {
        await api(`stores/${store.id}/products`, 'POST', {
          title,
          price,
          category,
          available,
          description,
          brand,
          image_url: imageUrl,
          discount: Number(row['discount'] || 0),
          variants: variantsList,
          visibility: true,
          tags: ['imported'],
        });
        count++;
      } catch (err) {
        failedRows.push(i + 1);
        console.error(err);
      }
    }
    await client.invalidateQueries({ queryKey: ['merchant-products'] });
    await client.invalidateQueries({ queryKey: ['dashboard'] });
    await client.invalidateQueries({ queryKey: ['products'] });
    notify(`Imported ${count} products.${failedRows.length ? ` Failed rows: ${failedRows.slice(0, 10).join(', ')}${failedRows.length > 10 ? '…' : ''}. Use plain decimal prices, for example 1200.50.` : ''}`, failedRows.length > 0);
    event.target.value = '';
  }

  return (
    <>
      <div className="merchant-heading">
        <div>
          <h1>Your products</h1>
          <p>A collection worth discovering.</p>
        </div>
        <div className="form-actions">
          <label
            className="button secondary"
            style={{
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
            title="Bulk import products from CSV"
          >
            <Upload size={17} />
            Import CSV
            <input
              type="file"
              accept=".csv,text/csv"
              style={{ display: 'none' }}
              onChange={handleCsvImport}
            />
          </label>
          <button
            className="button secondary"
            title="Export current page"
            disabled={!products.data?.results.length}
            onClick={() => exportRows(products.data!.results)}
          >
            <ArrowDownToLine size={17} />
            Export page
          </button>
          <Link className="button" href="/merchant/products/new">
            <Plus size={17} />
            Add product
          </Link>
        </div>
      </div>

      <div className="merchant-toolbar">
        <select
          aria-label="Sort products"
          value={ordering}
          onChange={(event) => {
            setOrdering(event.target.value);
            setOffset(0);
          }}
        >
          <option value="-updated">Recently updated</option>
          <option value="-created">Recently created</option>
          <option value="created">Oldest first</option>
        </select>
        <div className="tabs">
          {[
            ['', 'All products'],
            ['true', 'Published'],
            ['false', 'Drafts'],
          ].map(([value, label]) => (
            <button
              className={filter === value ? 'active' : ''}
              key={value}
              onClick={() => {
                setFilter(value);
                setOffset(0);
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="search-box">
          <Search size={17} />
          <input
            aria-label="Search your products"
            placeholder="Search products…"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
          />
        </div>
      </div>

      {products.isLoading ? (
        <Loading />
      ) : products.error ? (
        <ErrorState error={products.error} retry={() => products.refetch()} />
      ) : !products.data?.results.length ? (
        <Empty
          title={search ? 'Nothing matches just yet' : 'Your first product starts here'}
          text={
            search
              ? 'Try another search or change the filter.'
              : 'Add your first listing and give your customers something to discover.'
          }
          href="/merchant/products/new"
          label="Add product"
        />
      ) : (
        <>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Created / Updated</th>
                  <th>Category</th>
                  <th>Price</th>
                  <th>Inventory</th>
                  <th>Status</th>
                  <th>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {products.data.results.map((product) => (
                  <tr key={product.id}>
                    <td>
                      <Link
                        className="table-product"
                        href={`/merchant/products/${product.id}`}
                      >
                        <ProductImage
                          src={product.images[0]?.image || product.image_url}
                          alt={product.title}
                        />
                        <span>
                          <strong>{product.title}</strong>
                          <small
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 3,
                            }}
                          >
                            #{String(product.id).padStart(5, '0')} ·{' '}
                            {product.brand || store.name}
                            <VerifiedBadge
                              tier={store.is_official ? 'official' : 'starter'}
                              tierData={store.seller_tier}
                              size={12}
                            />
                          </small>
                        </span>
                      </Link>
                    </td>
                    <td>
                      {activityDate(product.created)}
                      <br />
                      {activityDate(product.updated)}
                    </td>
                    <td>
                      {categories.find((category) => category.key === product.category)
                        ?.name || product.category}
                    </td>
                    <td className="table-price">{money(product.price)}</td>
                    <td>
                      {product.is_digital ? (
                        <span>Unlimited</span>
                      ) : (
                        <span className={product.available <= 5 ? 'low-stock' : ''}>
                          {product.available} in stock
                        </span>
                      )}
                    </td>
                    <td>
                      <button
                        className={`publish-toggle ${product.visibility ? 'on' : ''}`}
                        disabled={busy === product.id}
                        role="switch"
                        aria-checked={product.visibility}
                        aria-label={`Publish ${product.title}`}
                        onClick={() => toggle(product)}
                      >
                        <span />
                        {product.visibility ? 'Published' : 'Draft'}
                      </button>
                    </td>
                    <td>
                      <Link
                        className="icon-button"
                        title="Edit product"
                        aria-label={`Edit ${product.title}`}
                        href={`/merchant/products/${product.id}`}
                      >
                        <ArrowUpRight size={18} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={Math.floor(offset / 15) + 1}
            totalPages={Math.ceil(products.data.count / 15)}
            onChange={(page) => setOffset((page - 1) * 15)}
          />
        </>
      )}
    </>
  );
}

const DIGITAL_IMAGE_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'webp', 'svg', 'gif', 'avif', 'bmp', 'tiff']);

function isDigitalImage(file: File | null, url: string | null | undefined): boolean {
  if (file) {
    if (file.type && file.type.startsWith('image/')) return true;
    const clean = (file.name || '').split('?')[0].split('#')[0];
    const ext = clean.split('.').pop()?.toLowerCase();
    return ext ? DIGITAL_IMAGE_EXTENSIONS.has(ext) : false;
  }
  if (url) {
    const clean = url.split('?')[0].split('#')[0];
    const ext = clean.split('.').pop()?.toLowerCase();
    return ext ? DIGITAL_IMAGE_EXTENSIONS.has(ext) : false;
  }
  return false;
}

function ProductEditor({ store, id }: { store: Store; id: string }) {
  const [savedProductId, setSavedProductId] = useState<number | null>(null);
  const persistedId = useRef<number | null>(id === 'new' ? null : Number(id));
  const saving = useRef<boolean>(false);
  const productId: string = savedProductId !== null ? String(savedProductId) : id;
  const isNew: boolean = productId === 'new';
  const client = useQueryClient(); const router = useRouter(); const { notify, user } = useShop(); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const product = useQuery({ queryKey: ['merchant-product', store.id, productId], queryFn: () => api<MerchantProduct>(`stores/${store.id}/products/${productId}`), enabled: !isNew });
  const [productType, setProductType] = useState<string | null>(null);
  const effectiveProductType = productType ?? product.data?.product_type ?? 'standard';
  const isAffiliate = effectiveProductType === 'affiliate_clickbank';
  const [isDigital, setIsDigital] = useState<boolean | null>(null);
  const effectiveIsDigital = !isAffiliate && (isDigital ?? product.data?.is_digital ?? false);
  const [variants, setVariants] = useState<ProductVariant[] | null>(null);

  const effectiveVariants = variants ?? product.data?.variants ?? [];
  const [coverImage, setCoverImage] = useState<string | null>(null);
  const [coverFile, setCoverFile] = useState<File | null>(null);
  const [coverPreview, setCoverPreview] = useState<string | null>(null);
  const [showCoverUrlInput, setShowCoverUrlInput] = useState(false);

  const [digitalFile, setDigitalFile] = useState<File | null>(null);
  const [digitalPreviewUrl, setDigitalPreviewUrl] = useState<string | null>(null);
  const [digitalUrlInput, setDigitalUrlInput] = useState<string | null>(null);
  const [digitalWatermark, setDigitalWatermark] = useState<boolean | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [showDigitalUrlInput, setShowDigitalUrlInput] = useState(false);

  const effectiveCoverImage = coverPreview || coverImage || product.data?.image_url || '';
  const variantImages = [...new Set([effectiveCoverImage, ...(product.data?.images || []).map(image => image.image)].filter(Boolean))];
  const [basePrice, setBasePrice] = useState<string | null>(null);
  const [discount, setDiscount] = useState<string | null>(null);
  const effectiveBasePrice = basePrice ?? product.data?.price ?? '';
  const effectiveDiscount = discount ?? String(product.data?.discount ?? 0);
  const salePrice = Math.round(Number(effectiveBasePrice) * (100 - Number(effectiveDiscount))) / 100;

  function handleCoverFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      notify('Image must be 5 MB or smaller.', true);
      event.target.value = '';
      return;
    }
    setCoverFile(file);
    setCoverPreview(URL.createObjectURL(file));
  }

  function removeCoverFile() {
    setCoverFile(null);
    if (coverPreview) {
      URL.revokeObjectURL(coverPreview);
      setCoverPreview(null);
    }
  }

  function handleDigitalFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 50 * 1024 * 1024) {
      notify('Digital file must be 50 MB or smaller.', true);
      event.target.value = '';
      return;
    }
    setDigitalFile(file);
    if (!isDigitalImage(file, null)) {
      setDigitalWatermark(false);
    }
    if (digitalPreviewUrl) URL.revokeObjectURL(digitalPreviewUrl);
    setDigitalPreviewUrl(URL.createObjectURL(file));
  }

  const syncTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const getPreviewData = useCallback((): PreviewProduct | null => {
    const form = formRef.current;
    if (!form) return null;
    const values = Object.fromEntries(new FormData(form)) as Record<string, string>;
    const affiliate = values.product_type === 'affiliate_clickbank' || effectiveProductType === 'affiliate_clickbank';
    const digital = !affiliate && (values.is_digital === 'on' || effectiveIsDigital);
    const price = Number(values.price);
    const activeFileUrl = values.digital_file_url || digitalPreviewUrl || product.data?.digital_file_url || '';
    const isImage = isDigitalImage(digitalFile, activeFileUrl);
    const galleryUrls = (product.data?.images || []).map((img) => img.image);
    const fallbackCover = effectiveCoverImage || product.data?.image_url || 'https://placehold.co/900x900/1b2921/9bd7b5?text=Product+Preview';
    return {
      title: values.title?.trim() || product.data?.title || 'Untitled product',
      description: values.description?.trim() || product.data?.description || 'Product description coming soon.',
      brand: values.brand?.trim() || store.name,
      category: values.category || product.data?.category || 'General',
      is_digital: digital,
      price: Number.isFinite(price) && price > 0 ? price : Number(product.data?.price || 0),
      sale_price: Number.isFinite(price) && price > 0
        ? (price * (100 - Number(values.discount || 0))) / 100
        : (Number(product.data?.price || 0) * (100 - Number(product.data?.discount || 0))) / 100,
      discount: Number(values.discount ?? product.data?.discount ?? 0),
      available: affiliate ? 999 : digital ? 0 : Number(values.available ?? product.data?.available ?? 0),
      image: fallbackCover,
      images: Array.from(
        new Set([
          fallbackCover,
          product.data?.image_url,
          ...galleryUrls,
          ...effectiveVariants.map((v) => v.image_url || ''),
        ])
      ).filter((x): x is string => Boolean(x)),
      flash_sale_end: values.flash_sale_end ? new Date(values.flash_sale_end).toISOString() : (product.data?.flash_sale_end || null),
      digital_preview_watermark: digital && isImage && (digitalWatermark ?? (values.digital_preview_watermark === 'on')),
      variants: digital || affiliate
        ? []
        : effectiveVariants
            .filter((v) => v.name && v.name.trim())
            .map((v) => ({
              ...v,
              price_delta: v.price_delta || '0.00',
              available: Number(v.available || 0),
            })),
      digital_file_name: digitalFile?.name || (values.digital_file_url ? 'Digital download' : undefined),
      digital_file_url: digitalPreviewUrl || values.digital_file_url || product.data?.digital_file_url || undefined,
      product_type: affiliate ? 'affiliate_clickbank' : 'standard',
      affiliate_hoplink: values.affiliate_hoplink?.trim() || '',
      affiliate_vendor_nickname: values.affiliate_vendor_nickname?.trim() || '',
      affiliate_button_text: values.affiliate_button_text?.trim() || 'Buy on Partner Site',
    };
  }, [
    effectiveProductType,
    effectiveIsDigital,
    digitalFile,
    digitalPreviewUrl,
    product.data,
    effectiveCoverImage,
    effectiveVariants,
    digitalWatermark,
    store.name,
  ]);

  const syncPreviewStorage = useCallback((previewData?: PreviewProduct | null) => {
    const data = previewData ?? getPreviewData();
    if (!data) return;
    try {
      const serialized = JSON.stringify(data);
      if (typeof window !== 'undefined') {
        localStorage.setItem('proace-product-preview', serialized);
        sessionStorage.setItem('proace-product-preview', serialized);
        if (typeof BroadcastChannel !== 'undefined') {
          const channel = new BroadcastChannel('proace-product-preview');
          channel.postMessage(data);
          channel.close();
        }
      }
    } catch {
      /* ignore storage quota or serialization errors */
    }
  }, [getPreviewData]);

  const scheduleSync = useCallback(() => {
    if (syncTimeoutRef.current) clearTimeout(syncTimeoutRef.current);
    syncTimeoutRef.current = setTimeout(() => {
      syncPreviewStorage();
    }, 150);
  }, [syncPreviewStorage]);

  useEffect(() => {
    syncPreviewStorage();
    return () => {
      if (syncTimeoutRef.current) clearTimeout(syncTimeoutRef.current);
    };
  }, [syncPreviewStorage]);

  function openPreview() {
    const preview = getPreviewData();
    if (!preview) return;
    syncPreviewStorage(preview);
    const tab: Window | null = window.open('/merchant/products/preview', 'proace-product-preview');
    if (!tab) {
      setError('Allow pop-ups to open the product preview. Your draft is still here.');
      return;
    }
    try {
      tab.sessionStorage.setItem('proace-product-preview', JSON.stringify(preview));
      tab.focus();
      setError('');
    } catch {
      try {
        tab.focus();
      } catch {
        /* ignore */
      }
      setError('');
    }
  }

  function addVariant() {
    setVariants([...effectiveVariants, { name: '', price_delta: '0.00', available: 10 }]);
  }

  function updateVariant(index: number, field: keyof ProductVariant, value: string | number) {
    const next = [...effectiveVariants];
    next[index] = { ...next[index], [field]: value };
    setVariants(next);
  }

  function removeVariant(index: number) {
    setVariants(effectiveVariants.filter((_, i) => i !== index));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving.current) return;
    saving.current = true;
    setBusy(true); setError(''); const form = Object.fromEntries(new FormData(event.currentTarget)) as Record<string, string>;
    const affiliate = form.product_type === 'affiliate_clickbank';
    const digital = !affiliate && form.is_digital === 'on';
    const flashEnd = form.flash_sale_end ? new Date(form.flash_sale_end).toISOString() : null;
    const validVariants = (affiliate || digital) ? [] : effectiveVariants
      .filter(v => v.name && v.name.trim().length > 0)
      .map(v => ({
        ...v,
        name: v.name.trim(),
        price_delta: v.price_delta || '0.00',
        available: typeof v.available === 'number' ? v.available : Number(v.available || 0),
      }));

    let fileUrl = form.digital_file_url || data?.digital_file_url || '';
    if (digital && !fileUrl && digitalFile) {
      // Use a temporary valid placeholder while we upload the digital file to MinIO
      fileUrl = `https://minio.local/pending-asset-${Date.now()}`;
    }
    const isImage = isDigitalImage(digitalFile, fileUrl);

    const payload = {
      ...form,
      product_type: affiliate ? 'affiliate_clickbank' : 'standard',
      affiliate_hoplink: affiliate ? (form.affiliate_hoplink?.trim() || '') : '',
      affiliate_vendor_nickname: affiliate ? (form.affiliate_vendor_nickname?.trim() || '') : '',
      affiliate_button_text: affiliate ? (form.affiliate_button_text?.trim() || 'Buy on Partner Site') : '',
      image_url: coverFile ? '' : (form.image_url || data?.image_url || ''),
      available: affiliate ? 999 : (digital ? 0 : Number(form.available)),
      discount: Number(form.discount || 0),
      flash_sale_end: flashEnd,
      variants: validVariants,
      weight: (affiliate || digital) ? '0.00' : (form.weight || '1.00'),
      length: (affiliate || digital) ? null : (form.length ? Number(form.length) : null),
      width: (affiliate || digital) ? null : (form.width ? Number(form.width) : null),
      height: (affiliate || digital) ? null : (form.height ? Number(form.height) : null),
      visibility: form.visibility === 'on',
      is_digital: digital,
      digital_file_url: digital ? fileUrl : '',
      digital_preview_watermark: digital && isImage ? (digitalWatermark ?? (form.digital_preview_watermark === 'on')) : false,
      tags: form.tags ? form.tags.split(',').map(value => value.trim()).filter(Boolean) : [],
    };
    try {
      const existingId: number | null = persistedId.current;
      const result = await api<MerchantProduct>(`stores/${store.id}/products${existingId === null ? '' : `/${existingId}`}`, existingId === null ? 'POST' : 'PATCH', payload);
      const targetId: number = result.id;
      // Remember the saved listing before uploads, which can fail independently.
      persistedId.current = targetId;
      client.setQueryData<MerchantProduct>(['merchant-product', store.id, String(targetId)], result);
      setSavedProductId(targetId);

      // Direct file upload to MinIO for cover image
      if (coverFile) {
        const coverForm = new FormData();
        coverForm.append('image', coverFile);
        coverForm.append('is_cover', 'true');
        await api(`stores/${store.id}/products/${targetId}/images`, 'POST', coverForm);
        setCoverFile(null);
      }

      // Direct file upload to MinIO for digital download
      if (digital && digitalFile) {
        const assetForm = new FormData();
        assetForm.append('file', digitalFile);
        await api(`stores/${store.id}/products/${targetId}/digital-file`, 'POST', assetForm);
        setDigitalFile(null);
      }

      await client.invalidateQueries({ queryKey: ['merchant-products'] });
      await client.invalidateQueries({ queryKey: ['dashboard'] });
      await client.invalidateQueries({ queryKey: ['merchant-product'] });
      await client.invalidateQueries({ queryKey: ['products'] });
      notify(isNew ? 'Your product has been created with assets uploaded' : 'Product and assets updated');
      if (id === 'new') router.replace(`/merchant/products/${targetId}`);
    } catch (error) {
      const message: string = error instanceof Error ? error.message : 'Please try again.';
      setError(persistedId.current !== null ? `Your product is saved, but this step failed: ${message} Save changes will retry on the same product.` : message);
      void client.invalidateQueries({ queryKey: ['merchant-products'] });
      void client.invalidateQueries({ queryKey: ['merchant-product'] });
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }
  if (!isNew && product.isLoading) return <Loading />;
  if (product.error) return <ErrorState error={product.error} />;

  const data = product.data;
  const activeDigitalUrl = digitalUrlInput ?? data?.digital_file_url ?? '';
  const isImageDigitalAsset = isDigitalImage(digitalFile, activeDigitalUrl);
  const hasDigitalAsset = Boolean(digitalFile || (activeDigitalUrl && activeDigitalUrl.trim().length > 0));
  const effectiveWatermark = isImageDigitalAsset ? (digitalWatermark ?? data?.digital_preview_watermark ?? false) : false;

  return (
    <>
      <Link className="text-link" href="/merchant/products">
        <ArrowLeft size={16} />
        All products
      </Link>
      <div className="merchant-heading">
        <div>
          <h1>{isNew ? 'Something new to discover.' : 'The details make it yours.'}</h1>
          <p>{isNew ? 'Give your next best-seller a good start.' : `Editing ${data?.title}`}</p>
        </div>
        {Boolean(
          data?.visibility &&
          ((store.status === 'active' && store.verified_at) ||
            store.is_official ||
            Boolean(user?.is_staff || user?.is_superuser || user?.is_business_admin))
        ) && (
          <Link
            className="button secondary"
            href={`/products/${productId}${
              Boolean(user?.is_staff || user?.is_superuser || user?.is_business_admin)
                ? '?preview=1'
                : ''
            }`}
          >
            <Eye size={16} />
            View listing
          </Link>
        )}
      </div>

      <form
        ref={formRef}
        className="product-editor"
        onSubmit={save}
        onInput={scheduleSync}
        onChange={scheduleSync}
      >
        <section className="form-stack">
          <h2>Product information</h2>
          {store.is_official || isAffiliate ? (
            <Field label="Listing type">
              <select
                name="product_type"
                value={effectiveProductType}
                onChange={(e) => setProductType(e.target.value)}
              >
                <option value="standard">
                  Standard marketplace listing (Fulfilled by your store)
                </option>
                <option value="affiliate_clickbank">
                  ClickBank partner offer (External affiliate listing)
                </option>
              </select>
            </Field>
          ) : (
            <input type="hidden" name="product_type" value="standard" />
          )}

          {isAffiliate && (
            <div
              style={{
                background: 'var(--surface-subtle, rgba(234, 88, 12, 0.08))',
                border: '1px solid rgba(234, 88, 12, 0.25)',
                borderRadius: '8px',
                padding: '14px 16px',
                marginBottom: '16px',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  marginBottom: '6px',
                }}
              >
                <span
                  style={{
                    background: '#ea580c',
                    color: '#fff',
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: '4px',
                  }}
                >
                  ClickBank Offer
                </span>
                <strong>Partner Offer Configuration</strong>
              </div>
              <p className="fine-print" style={{ margin: '0 0 12px 0' }}>
                Shoppers viewing this product will be routed via ProAce tracking to the partner merchant. You earn affiliate commissions directly on ClickBank.
              </p>
              <Field label="Affiliate HopLink (Target URL)">
                <input
                  name="affiliate_hoplink"
                  type="url"
                  required={isAffiliate}
                  defaultValue={data?.affiliate_hoplink || ''}
                  placeholder="https://hop.clickbank.net/?affiliate=proace&vendor=sample"
                />
              </Field>
              <div className="form-row" style={{ marginTop: '10px' }}>
                <Field label="ClickBank Vendor Nickname (Optional)">
                  <input
                    name="affiliate_vendor_nickname"
                    maxLength={64}
                    defaultValue={data?.affiliate_vendor_nickname || ''}
                    placeholder="e.g. samplevendor"
                  />
                </Field>
                <Field label="Button CTA text">
                  <input
                    name="affiliate_button_text"
                    maxLength={64}
                    defaultValue={data?.affiliate_button_text || 'Buy on Partner Site'}
                    placeholder="Buy on Partner Site"
                  />
                </Field>
              </div>
            </div>
          )}

          <Field label="Product title">
            <input
              name="title"
              defaultValue={data?.title}
              required
              maxLength={225}
              placeholder="A clear, descriptive name"
            />
          </Field>
          <Field label="Description">
            <textarea
              name="description"
              defaultValue={data?.description}
              required
              rows={5}
              placeholder="What makes this product a good find?"
            />
          </Field>
          <div className="form-row">
            <Field label="Brand">
              <input
                name="brand"
                maxLength={80}
                defaultValue={data?.brand}
              />
            </Field>
            <Field label="Category">
              <select
                name="category"
                defaultValue={data?.category || ''}
                required
              >
                <option value="" disabled>
                  Select a category
                </option>
                {categories.map((category) => (
                  <option value={category.key} key={category.key}>
                    {category.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          {!isAffiliate && (
            <label className="check-row">
              <input
                type="checkbox"
                name="is_digital"
                checked={effectiveIsDigital}
                onChange={(e) => setIsDigital(e.target.checked)}
              />
              Digital download / e-book (available worldwide, 0 lbs weight)
            </label>
          )}
          {!isAffiliate && (effectiveIsDigital ? (
    <div style={{ marginTop: '10px', marginBottom: '14px' }}>
      {digitalFile ? (
        <div className="upload-preview-card">
          <div className="upload-file-icon-box"><FileText size={22} /></div>
          <div className="upload-preview-meta">
            <strong>{digitalFile.name}</strong>
            <span>{(digitalFile.size / (1024 * 1024)).toFixed(2)} MB · Uploads to MinIO storage</span>
            <span className="upload-preview-badge">Ready to upload</span>
          </div>
          <button
            type="button"
            className="icon-button"
            aria-label="Remove digital file"
            onClick={() => {
              setDigitalFile(null);
              if (!isDigitalImage(null, activeDigitalUrl)) {
                setDigitalWatermark(false);
              }
              if (digitalPreviewUrl) {
                URL.revokeObjectURL(digitalPreviewUrl);
                setDigitalPreviewUrl(null);
              }
            }}
          >
            <X size={16} />
          </button>
        </div>
      ) : data?.digital_file_url ? (
        <div className="upload-preview-card">
          <div className="upload-file-icon-box"><FileText size={22} /></div>
          <div className="upload-preview-meta">
            <strong>Active digital product file</strong>
            <span style={{ fontSize: '11px', color: 'var(--muted)', wordBreak: 'break-all' }}>{data.digital_file_url}</span>
            <span className="upload-preview-badge">Stored in MinIO</span>
          </div>
          <div style={{ display: 'flex', gap: '6px' }}>
            <a href={`/api/stores/${store.id}/products/${id}/digital-file`} target="_blank" rel="noopener noreferrer" download className="button secondary" style={{ fontSize: '11px', padding: '6px 10px' }} title="Test file download">
              <ArrowDownToLine size={13} /> Test
            </a>
            <label className="button secondary" style={{ fontSize: '11px', padding: '6px 10px', cursor: 'pointer' }}>
              <Upload size={13} /> Replace
              <input type="file" accept=".pdf,.zip,.epub,.mp3,.mp4,.mobi,.rar,.txt,.doc,.docx,.png,.jpg,.jpeg,.webp,.svg,.avif" style={{ display: 'none' }} onChange={handleDigitalFileChange} />
            </label>
          </div>
        </div>
      ) : (
        <label className="upload-dropzone">
          <div className="upload-dropzone-icon"><FileText size={20} /></div>
          <span className="upload-dropzone-text">Click or drag digital file to upload</span>
          <span className="upload-dropzone-sub">PDF, ZIP, EPUB, MP3, MP4, PNG, JPG up to 50 MB · Saved directly to MinIO storage</span>
          <input type="file" accept=".pdf,.zip,.epub,.mp3,.mp4,.mobi,.rar,.txt,.doc,.docx,.png,.jpg,.jpeg,.webp,.svg,.avif" style={{ display: 'none' }} onChange={handleDigitalFileChange} />
        </label>
      )}
      <div style={{ marginTop: '8px', display: 'flex', justifyContent: 'flex-end' }}>
        <button type="button" className="text-button" style={{ fontSize: '11px' }} onClick={() => setShowDigitalUrlInput(!showDigitalUrlInput)}>
          {showDigitalUrlInput ? 'Hide download URL field' : 'Or enter external download link'}
        </button>
      </div>
      <label
        className={`check-row ${!isImageDigitalAsset ? 'disabled' : ''}`}
        style={!isImageDigitalAsset ? { opacity: 0.65, cursor: 'not-allowed' } : undefined}
      >
        <input
          type="checkbox"
          name="digital_preview_watermark"
          checked={effectiveWatermark}
          disabled={!isImageDigitalAsset}
          onChange={(event) => {
            if (isImageDigitalAsset) {
              setDigitalWatermark(event.target.checked);
            }
          }}
        />
        <span>
          Protect image previews with a buyer watermark
          <span style={{ display: 'block', fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>
            {hasDigitalAsset
              ? isImageDigitalAsset
                ? 'Overlays a PROACE PREVIEW watermark on storefront image gallery to protect your digital artwork before purchase.'
                : 'Not applicable — buyer watermarking only applies to digital image and artwork files, not PDF, audio, or software downloads.'
              : 'Upload a digital image file (PNG, JPG, WebP, SVG) to enable preview watermarking.'}
          </span>
        </span>
      </label>
      {showDigitalUrlInput && (
        <Field label="Download URL">
          <input
            name="digital_file_url"
            type="url"
            maxLength={1000}
            defaultValue={data?.digital_file_url}
            placeholder="https://…"
            onChange={(e) => {
              setDigitalUrlInput(e.target.value);
              if (!isDigitalImage(digitalFile, e.target.value)) {
                setDigitalWatermark(false);
              }
            }}
          />
        </Field>
      )}
    </div>
  ) : (
    <div className="form-row">
      <Field label="Shipping weight (lbs)">
        <input
          name="weight"
          type="number"
          min="0.01"
          max="999.99"
          step="0.01"
          defaultValue={data?.weight || '1.00'}
          required
          placeholder="e.g. 1.25"
        />
      </Field>
      <Field label="Length (in)">
        <input
          name="length"
          type="number"
          min="0.01"
          step="0.01"
          defaultValue={data?.length || '10'}
          required
        />
      </Field>
      <Field label="Width (in)">
        <input
          name="width"
          type="number"
          min="0.01"
          step="0.01"
          defaultValue={data?.width || '8'}
          required
        />
      </Field>
      <Field label="Height (in)">
        <input
          name="height"
          type="number"
          min="0.01"
          step="0.01"
          defaultValue={data?.height || '4'}
          required
        />
      </Field>
    </div>
  ))}

  <p className="fine-print">
    {isAffiliate
      ? 'Partner products are fulfilled directly by the external ClickBank vendor.'
      : effectiveIsDigital
        ? 'Digital products are fulfilled automatically worldwide with $0.00 shipping and unlimited inventory.'
        : 'Physical products are shipped within the US with live USPS rate calculation.'}
  </p>

  <Field label="Tags">
    <input
      name="tags"
      defaultValue={data?.tags?.join(', ')}
      placeholder="Audio, wireless, everyday"
    />
  </Field>

  {!isAffiliate && !effectiveIsDigital && (
    <>
      <h2>Product options &amp; variants</h2>
      <p className="fine-print">
        Add a separate option for each color, size, or combination, such as Black / Large. Each option has its own stock and price adjustment.
      </p>
      <p className="fine-print">
        The base price after the product discount is <strong>{money(salePrice)}</strong>. Enter 0 to use that price, 5 to add $5, or -5 to subtract $5. Changing the base price or discount updates every variant price.
      </p>
      <div className="variant-list">
        {effectiveVariants.map((variant, index) => (
          <fieldset className="variant-card" key={index}>
            <legend>
              Variant {index + 1}
              {variant.name ? ` · ${variant.name}` : ''}
            </legend>
            <div className="variant-card-heading">
              <strong>
                Customer price: {money(salePrice + Number(variant.price_delta || 0))}
              </strong>
              <button
                type="button"
                className="icon-button"
                aria-label={`Remove variant ${index + 1}`}
                onClick={() => removeVariant(index)}
              >
                <X size={16} />
              </button>
            </div>
            <div className="variant-fields">
              <Field label="Variant name">
                <input
                  placeholder="e.g. Black / Large"
                  value={variant.name}
                  onChange={(event) => updateVariant(index, 'name', event.target.value)}
                  required
                />
              </Field>
              <Field label="SKU (optional)">
                <input
                  placeholder="e.g. TEE-BLK-L"
                  value={variant.sku || ''}
                  onChange={(event) => updateVariant(index, 'sku', event.target.value)}
                />
              </Field>
              <Field label="Barcode (optional)">
                <input
                  placeholder="UPC / EAN / ISBN"
                  value={variant.barcode || ''}
                  onChange={(event) => updateVariant(index, 'barcode', event.target.value)}
                />
              </Field>
              <Field label="Price adjustment (USD)">
                <input
                  type="number"
                  step="0.01"
                  min={(0.01 - salePrice).toFixed(2)}
                  placeholder="0.00"
                  value={variant.price_delta ?? '0.00'}
                  onChange={(event) =>
                    updateVariant(index, 'price_delta', event.target.value)
                  }
                  required
                />
              </Field>
              <Field label="Variant image">
                <select
                  value={variant.image_url || ''}
                  onChange={(event) => updateVariant(index, 'image_url', event.target.value)}
                >
                  <option value="">Use main product image</option>
                  {variant.image_url && !variantImages.includes(variant.image_url) && (
                    <option value={variant.image_url}>Previously mapped image</option>
                  )}
                  {variantImages.map((image, photoIndex) => (
                    <option value={image} key={image}>
                      {image === effectiveCoverImage
                        ? 'Cover image'
                        : `Gallery photo ${photoIndex + 1}`}
                    </option>
                  ))}
                </select>
              </Field>
              {variant.image_url && (
                <div
                  style={{
                    width: '80px',
                    height: '80px',
                    overflow: 'hidden',
                    borderRadius: '6px',
                  }}
                >
                  <ProductImage
                    src={variant.image_url}
                    alt={`${variant.name || 'Variant'} mapped photo`}
                  />
                </div>
              )}
              <Field label="Variant stock">
                <input
                  type="number"
                  min="0"
                  step="1"
                  placeholder="Units of this option"
                  value={variant.available ?? ''}
                  onChange={(event) =>
                    updateVariant(
                      index,
                      'available',
                      event.target.value === '' ? '' : Number(event.target.value)
                    )
                  }
                  required
                />
              </Field>
            </div>
          </fieldset>
        ))}
      </div>
      <button
        type="button"
        className="button secondary"
        onClick={addVariant}
        style={{ width: 'fit-content', marginBottom: '16px' }}
      >
        <Plus size={15} />
        Add variant
      </button>
    </>
  )}

  <h2>Product photography</h2>
  <p className="fine-print">
    Upload a primary cover image for your product (stored directly on MinIO). Gallery photos and variant mapping can be managed below after saving.
  </p>

  {coverPreview ? (
    <div className="upload-preview-card">
      <img src={coverPreview} alt="Cover preview" className="upload-preview-thumb" />
      <div className="upload-preview-meta">
        <strong>{coverFile?.name || 'Selected cover photo'}</strong>
        <span>
          {coverFile ? `${(coverFile.size / 1024).toFixed(1)} KB` : ''} · Direct MinIO upload
        </span>
        <span className="upload-preview-badge">Ready to upload</span>
      </div>
      <button
        type="button"
        className="icon-button"
        aria-label="Remove photo"
        onClick={removeCoverFile}
      >
        <X size={16} />
      </button>
    </div>
  ) : effectiveCoverImage ? (
    <div className="upload-preview-card">
      <ProductImage
        src={effectiveCoverImage}
        alt="Current cover photo"
        className="upload-preview-thumb"
      />
      <div className="upload-preview-meta">
        <strong>Cover photo</strong>
        <span style={{ fontSize: '11px', color: 'var(--muted)', wordBreak: 'break-all' }}>
          {normalizeImageUrl(effectiveCoverImage)}
        </span>
        <span className="upload-preview-badge">Active cover</span>
      </div>
      <label
        className="button secondary"
        style={{ fontSize: '11px', padding: '6px 10px', cursor: 'pointer' }}
      >
        <Upload size={13} /> Change
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          style={{ display: 'none' }}
          onChange={handleCoverFileChange}
        />
      </label>
    </div>
  ) : (
    <label className="upload-dropzone">
      <div className="upload-dropzone-icon">
        <Upload size={20} />
      </div>
      <span className="upload-dropzone-text">Click or drag image to upload cover photo</span>
      <span className="upload-dropzone-sub">
        PNG, JPG, or WEBP up to 5 MB · Saved directly to MinIO storage
      </span>
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        style={{ display: 'none' }}
        onChange={handleCoverFileChange}
      />
    </label>
  )}

  <div style={{ marginTop: '8px', display: 'flex', justifyContent: 'flex-end' }}>
    <button
      type="button"
      className="text-button"
      style={{ fontSize: '11px' }}
      onClick={() => setShowCoverUrlInput(!showCoverUrlInput)}
    >
      {showCoverUrlInput ? 'Hide image URL field' : 'Or paste online image URL'}
    </button>
  </div>

  {showCoverUrlInput && (
    <Field label="Image URL">
      <input
        name="image_url"
        type="url"
        maxLength={1000}
        value={coverImage ?? (coverPreview ? '' : data?.image_url ?? '')}
        onChange={(event) => setCoverImage(event.target.value)}
        placeholder="https://…"
      />
    </Field>
  )}
</section>

<aside className="editor-aside">
  <section>
    <h2>{effectiveIsDigital || isAffiliate ? 'Pricing' : 'Pricing & stock'}</h2>
    <Field label="Price (USD)">
      <input
        name="price"
        type="number"
        min="0.01"
        step="0.01"
        required
        value={effectiveBasePrice}
        onChange={(event) => setBasePrice(event.target.value)}
      />
    </Field>
    <div className="form-row">
      <Field label="Discount (%)">
        <input
          type="number"
          name="discount"
          min="0"
          max="60"
          step="1"
          required
          value={effectiveDiscount}
          onChange={(event) => setDiscount(event.target.value)}
        />
      </Field>
      {!effectiveIsDigital && !isAffiliate && (
        <Field label="Stock quantity">
          <input
            name="available"
            type="number"
            min="0"
            step="1"
            required
            defaultValue={data?.available || 0}
          />
        </Field>
      )}
    </div>
    {effectiveIsDigital && <input type="hidden" name="available" value="0" />}
    {isAffiliate && (
      <p className="fine-print" style={{ color: 'var(--muted)', marginTop: '4px' }}>
        Inventory is managed directly by ClickBank partner vendor.
      </p>
    )}
    <Field label="Flash Deal Expiration (Optional)">
      <input
        name="flash_sale_end"
        type="datetime-local"
        defaultValue={
          data?.flash_sale_end ? toLocalDateTimeInput(data.flash_sale_end) : ''
        }
      />
    </Field>
    <hr />
    <h3>Availability</h3>
    <label className="check-row">
      <input
        type="checkbox"
        name="visibility"
        defaultChecked={data?.visibility || false}
      />
      Publish to the marketplace
    </label>
    {error && <p className="form-error">{error}</p>}
    <div className="form-actions">
      <button type="button" className="button secondary" onClick={openPreview}>
        <Eye size={17} />
        Preview
      </button>
      <button className="button" disabled={busy}>
        {busy ? 'Saving…' : isNew ? 'Create product' : 'Save changes'}
        <Check size={17} />
      </button>
    </div>
    <Link className="button secondary" href="/merchant/products">
      Back to products
    </Link>
  </section>
</aside>
</form>
{!isNew && <ProductAssets store={store} product={data!} />}
</>
);
}

function ProductAssets({ store, product }: { store: Store; product: MerchantProduct }) {
  const { notify } = useShop(); const client = useQueryClient(); const [uploading, setUploading] = useState(false);
  const [digitalUploading, setDigitalUploading] = useState(false);
  const base = `stores/${store.id}/products/${product.id}`;
  const specs = useQuery({
    queryKey: ['specs', product.id],
    queryFn: () => api<Record<string, string>>(`${base}/specifications`),
    enabled: !product.is_digital && product.product_type !== 'affiliate_clickbank',
  });
  async function uploadImages(event: React.ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const files = Array.from(input.files || []);
    if (!files.length) return;
    if (files.some(file => file.size > 5 * 1024 * 1024)) {
      notify('Each image must be 5 MB or smaller.', true);
      input.value = '';
      return;
    }
    setUploading(true);
    let uploaded = 0;
    try {
      for (const file of files) {
        const form = new FormData();
        form.append('image', file);
        await api(`${base}/images`, 'POST', form);
        uploaded++;
      }
      notify(`${uploaded} image${uploaded === 1 ? '' : 's'} uploaded to MinIO storage`);
    } catch (error) {
      notify(`${uploaded} of ${files.length} images uploaded. ${(error as Error).message}`, true);
    } finally {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['merchant-product'] }),
        client.invalidateQueries({ queryKey: ['merchant-products'] }),
        client.invalidateQueries({ queryKey: ['product', String(product.id)] }),
        client.invalidateQueries({ queryKey: ['products'] }),
      ]);
      setUploading(false);
      input.value = '';
    }
  }

  async function setAsCover(image: { id: number; image: string }) {
    try {
      await api(`${base}/images/${image.id}/cover`, 'PATCH');
      notify('Primary cover photo updated');
      await Promise.all([
        client.invalidateQueries({ queryKey: ['merchant-product'] }),
        client.invalidateQueries({ queryKey: ['merchant-products'] }),
        client.invalidateQueries({ queryKey: ['product', String(product.id)] }),
        client.invalidateQueries({ queryKey: ['products'] }),
      ]);
    } catch (error) {
      notify((error as Error).message, true);
    }
  }

  async function handleDigitalUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) return;
    if (file.size > 50 * 1024 * 1024) {
      notify('Digital file must be 50 MB or smaller.', true);
      input.value = '';
      return;
    }
    setDigitalUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      await api(`${base}/digital-file`, 'POST', form);
      notify('Digital product asset uploaded to MinIO storage');
      await Promise.all([
        client.invalidateQueries({ queryKey: ['merchant-product'] }),
        client.invalidateQueries({ queryKey: ['merchant-products'] }),
        client.invalidateQueries({ queryKey: ['product', String(product.id)] }),
        client.invalidateQueries({ queryKey: ['products'] }),
      ]);
    } catch (err) {
      notify((err as Error).message, true);
    } finally {
      setDigitalUploading(false);
      input.value = '';
    }
  }

  return (
    <section className="merchant-section">
      <div className="section-heading">
        <h2>Image gallery</h2>
        <label className="button secondary upload-label">
          <Upload size={17} />{uploading ? 'Uploading to MinIO…' : 'Upload gallery images'}
          <input type="file" multiple accept="image/jpeg,image/png,image/webp" disabled={uploading} onChange={uploadImages} />
        </label>
      </div>
      <div className="asset-gallery">
        {product.images.map(image => {
          const isCover = image.image === product.image_url;
          return (
            <div key={image.id}>
              <ProductImage src={image.image} alt={product.title} />
              {isCover ? (
                <span className="gallery-cover-badge" title="Primary cover photo">
                  <Star size={10} fill="currentColor" /> Cover
                </span>
              ) : (
                <button type="button" className="gallery-set-cover-btn" title="Set as primary cover photo" onClick={() => setAsCover(image)}>
                  <Star size={11} /> Cover
                </button>
              )}
              <button className="icon-button" aria-label="Delete image" onClick={async () => {
                try {
                  await api(`${base}/images/${image.id}`, 'DELETE');
                  await client.invalidateQueries({ queryKey: ['merchant-product'] });
                } catch (error) {
                  notify((error as Error).message, true);
                }
              }}>
                <X size={16} />
              </button>
            </div>
          );
        })}
      </div>

      {product.is_digital && (
        <div className="digital-asset-card">
          <div className="digital-asset-card-head">
            <div className="digital-asset-card-title">
              <div className="upload-file-icon-box"><FileText size={20} /></div>
              <div>
                <h3>Digital Product Asset (MinIO Storage)</h3>
                <p style={{ margin: 0, fontSize: '11px', color: 'var(--muted)' }}>
                  {product.digital_file_url ? 'Customers receive instant download access upon purchase.' : 'No digital file uploaded yet.'}
                </p>
              </div>
            </div>
            <div className="digital-asset-card-actions">
              {product.digital_file_url && (
                <a href={`/api/stores/${store.id}/products/${product.id}/digital-file`} target="_blank" rel="noopener noreferrer" download className="button secondary" style={{ fontSize: '11px', padding: '6px 12px' }}>
                  <ArrowDownToLine size={14} /> Test download
                </a>
              )}
              <label className="button secondary" style={{ fontSize: '11px', padding: '6px 12px', cursor: 'pointer' }}>
                <Upload size={14} /> {digitalUploading ? 'Uploading…' : product.digital_file_url ? 'Replace file' : 'Upload file'}
                <input type="file" accept=".pdf,.zip,.epub,.mp3,.mp4,.mobi,.rar,.txt,.doc,.docx" disabled={digitalUploading} style={{ display: 'none' }} onChange={handleDigitalUpload} />
              </label>
            </div>
          </div>
          {product.digital_file_url && (
            <div style={{ fontSize: '11px', color: 'var(--muted)', wordBreak: 'break-all', background: 'var(--soft)', padding: '6px 10px', borderRadius: '4px' }}>
              <strong>Current file URL: </strong>{product.digital_file_url}
            </div>
          )}
        </div>
      )}

      {!product.is_digital && product.product_type !== 'affiliate_clickbank' && (
        <details className="spec-editor">
          <summary>Product specifications</summary>
          {specs.isLoading ? <Loading /> : specs.error ? <ErrorState error={specs.error} /> : (
            <form className="form-stack" onSubmit={async event => {
              event.preventDefault();
              const payload = Object.fromEntries(new FormData(event.currentTarget));
              try {
                await api(`${base}/specifications`, 'PUT', payload);
                notify('Specifications saved');
                await specs.refetch();
              } catch (error) {
                notify((error as Error).message, true);
              }
            }}>
              <div className="form-row">
                <Field label="SKU / serial number"><input name="serial" maxLength={25} required defaultValue={specs.data?.serial} /></Field>
                <Field label="Colour"><input name="color" maxLength={25} required defaultValue={specs.data?.color} /></Field>
              </div>
              <Field label="Attributes"><input name="attributes" maxLength={250} required defaultValue={specs.data?.attributes} /></Field>
              <div className="form-row">
                {['height', 'width', 'breadth', 'weight'].map(field => (
                  <Field label={field.charAt(0).toUpperCase() + field.slice(1)} key={field}>
                    <input type="number" name={field} min="0.01" max="99.99" step="0.01" required defaultValue={specs.data?.[field]} />
                  </Field>
                ))}
              </div>
              <button className="button">Save specifications</button>
            </form>
          )}
        </details>
      )}
    </section>
  );
}

function MerchantOrderTable({ orders, storeId, onUpdated }: { orders: MerchantOrder[]; storeId?: number; onUpdated?: () => void }) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const [trackingOrder, setTrackingOrder] = useState<MerchantOrder | null>(null);
  const trackingDialogRef = useDialogFocus(!!trackingOrder, () => setTrackingOrder(null));
  const [trackingNumber, setTrackingNumber] = useState('');
  const [carrier, setCarrier] = useState('USPS');
  const [orderStatus, setOrderStatus] = useState('shipped');
  const [busy, setBusy] = useState(false);
  const [allowEditTracking, setAllowEditTracking] = useState(false);
  const [confirmVerified, setConfirmVerified] = useState(false);
  const { notify } = useShop();

  const hasExistingTracking = Boolean(trackingOrder?.tracking_number);
  const isTrackingModified = hasExistingTracking && trackingNumber.trim() !== (trackingOrder?.tracking_number || '').trim();

  async function submitTracking(event: FormEvent) {
    event.preventDefault();
    if (!storeId || !trackingOrder) return;
    if (isTrackingModified && !confirmVerified) {
      notify('Please confirm verification before replacing the tracking number', true);
      return;
    }
    setBusy(true);
    try {
      const orderId = trackingOrder.id ?? trackingOrder.reference;
      await api(`stores/${storeId}/orders/${orderId}/tracking`, 'POST', {
        tracking_number: trackingNumber,
        carrier,
        status: orderStatus,
      });
      notify(`Order #${trackingOrder.reference} updated to ${orderStatus}`);
      setTrackingOrder(null);
      setTrackingNumber('');
      setAllowEditTracking(false);
      setConfirmVerified(false);
      onUpdated?.();
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  if (!orders.length) {
    return (
      <div className="empty-state">
        <ShoppingBag size={30} />
        <h2>The first of many.</h2>
        <p>Your customer orders will appear here.</p>
      </div>
    );
  }

  return (
    <>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Order</th>
              <th>Date</th>
              <th>Products</th>
              <th>Units</th>
              <th>Tracking</th>
              <th>Status</th>
              <th>
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr key={order.id}>
                <td>
                  <strong>{order.reference}</strong>
                </td>
                <td>
                  {new Date(order.created).toLocaleDateString('en-GB', {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                  })}
                </td>
                <td>
                  {expanded === order.id
                    ? order.items.map((item) => (
                        <p key={item.product}>
                          {item.title} × {item.quantity}
                        </p>
                      ))
                    : `${order.items[0]?.title || 'Order'}${
                        order.items.length > 1 ? ` +${order.items.length - 1}` : ''
                      }`}
                </td>
                <td>
                  {order.items.reduce((sum, item) => sum + item.quantity, 0)}
                </td>
                <td>
                  {order.tracking_number ? (
                    <small style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Truck size={13} color="var(--green)" />
                      {order.carrier || 'USPS'}: {order.tracking_number}
                    </small>
                  ) : (
                    <span className="muted" style={{ fontSize: '0.8rem' }}>
                      No tracking
                    </span>
                  )}
                </td>
                <td>
                  <Status value={order.status} />
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button
                    className="icon-button"
                    aria-label={`View items for ${order.reference}`}
                    title="View order items"
                    onClick={() => setExpanded(expanded === order.id ? null : order.id)}
                  >
                    <Eye size={17} />
                  </button>
                  {storeId && ['pending', 'confirmed', 'shipped'].includes(order.status) && (
                    <button
                      className="button secondary"
                      style={{
                        padding: '0.25rem 0.6rem',
                        fontSize: '0.78rem',
                        marginLeft: '0.4rem',
                      }}
                      onClick={() => {
                        setTrackingOrder(order);
                        setTrackingNumber(order.tracking_number || '');
                        setCarrier(order.carrier || 'USPS');
                        setOrderStatus(order.status === 'pending' ? 'shipped' : order.status);
                        setAllowEditTracking(!order.tracking_number);
                        setConfirmVerified(false);
                      }}
                    >
                      <Truck size={13} />
                      Ship / Track
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {trackingOrder && (
        <div
          className="admin-dialog-backdrop"
          role="presentation"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setTrackingOrder(null);
          }}
        >
          <section
            ref={trackingDialogRef}
            className="admin-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="tracking-title"
          >
            <div className="admin-dialog-head">
              <div>
                <span className="eyebrow green">FULFILLMENT & TRACKING</span>
                <h2 id="tracking-title">Update Order #{trackingOrder.reference}</h2>
              </div>
              <button
                className="icon-button"
                aria-label="Close"
                onClick={() => setTrackingOrder(null)}
              >
                <X size={19} />
              </button>
            </div>

            <form className="form-stack" onSubmit={submitTracking}>
              <div className="form-row">
                <Field label="Shipping Carrier">
                  <select value={carrier} onChange={(e) => setCarrier(e.target.value)}>
                    <option value="USPS">USPS (United States Postal Service)</option>
                    <option value="UPS">UPS</option>
                    <option value="FedEx">FedEx</option>
                    <option value="DHL">DHL</option>
                  </select>
                </Field>
                <Field label="Order Status">
                  <select
                    value={orderStatus}
                    onChange={(e) => setOrderStatus(e.target.value)}
                  >
                    <option value="confirmed">Confirmed</option>
                    <option value="shipped">Shipped</option>
                    <option value="delivered">Delivered</option>
                  </select>
                </Field>
              </div>

              {hasExistingTracking && (
                <div className="tracking-info-callout">
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <span
                      style={{
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        color: 'var(--muted)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                      }}
                    >
                      Active Tracking Number
                    </span>
                    <span className="tracking-carrier-pill">
                      {trackingOrder.carrier || 'USPS'}
                    </span>
                  </div>
                  <strong>{trackingOrder.tracking_number}</strong>
                  <label className="check-row" style={{ margin: '0.25rem 0 0', fontSize: '0.85rem' }}>
                    <input
                      type="checkbox"
                      checked={allowEditTracking}
                      onChange={(e) => {
                        setAllowEditTracking(e.target.checked);
                        if (!e.target.checked) {
                          setTrackingNumber(trackingOrder.tracking_number || '');
                          setConfirmVerified(false);
                        }
                      }}
                    />
                    Enable editing to change or replace tracking number
                  </label>
                </div>
              )}

              <Field label="Order Tracking Number">
                <input
                  required
                  maxLength={100}
                  value={trackingNumber}
                  readOnly={hasExistingTracking && !allowEditTracking}
                  onChange={(e) => setTrackingNumber(e.target.value)}
                  placeholder="e.g. 9400 1000 0000 0000 00"
                  style={
                    hasExistingTracking && !allowEditTracking
                      ? { background: 'var(--soft)', color: 'var(--muted)', cursor: 'not-allowed' }
                      : undefined
                  }
                />
              </Field>

              {hasExistingTracking && !allowEditTracking && (
                <p className="fine-print" style={{ margin: '-0.4rem 0 0' }}>
                  Locked to prevent accidental edits. Check the box above to modify.
                </p>
              )}

              {isTrackingModified && (
                <div className="tracking-warning-callout">
                  <p>
                    ⚠️ You are replacing an active tracking number. This updates order history and re-notifies the customer.
                  </p>
                  <label className="check-row">
                    <input
                      type="checkbox"
                      required
                      checked={confirmVerified}
                      onChange={(e) => setConfirmVerified(e.target.checked)}
                    />
                    I confirm that I have verified this new tracking number with the carrier receipt.
                  </label>
                </div>
              )}

              <div className="form-actions">
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => setTrackingOrder(null)}
                >
                  Cancel
                </button>
                <button
                  className="button"
                  disabled={busy || (isTrackingModified && !confirmVerified)}
                >
                  {busy ? 'Updating…' : 'Save tracking & notify customer'}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </>
  );
}

function MerchantOrders({ store }: { store: Store }) {
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const client = useQueryClient();

  const orders = useQuery({
    queryKey: ['merchant-orders', store.id, status, offset],
    queryFn: () =>
      api<Page<MerchantOrder>>(
        `stores/${store.id}/orders?status=${status}&limit=20&offset=${offset}`
      ),
  });

  return (
    <>
      <div className="merchant-heading">
        <div>
          <h1>Every order, a good beginning.</h1>
          <p>Follow your customers’ finds from your store.</p>
        </div>
        <select
          aria-label="Filter orders by status"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setOffset(0);
          }}
        >
          <option value="">All statuses</option>
          {['pending', 'confirmed', 'shipped', 'delivered', 'cancelled', 'refunded'].map(
            (value) => (
              <option key={value} value={value}>
                {value.charAt(0).toUpperCase() + value.slice(1)}
              </option>
            )
          )}
        </select>
      </div>

      {orders.isLoading ? (
        <Loading />
      ) : orders.error ? (
        <ErrorState error={orders.error} retry={() => orders.refetch()} />
      ) : (
        <>
          <MerchantOrderTable
            orders={orders.data?.results || []}
            storeId={store.id}
            onUpdated={() => {
              client.invalidateQueries({ queryKey: ['merchant-orders', store.id] });
              client.invalidateQueries({ queryKey: ['merchant-recent', store.id] });
              client.invalidateQueries({ queryKey: ['dashboard', store.id] });
            }}
          />
          <Pagination
            page={Math.floor(offset / 20) + 1}
            totalPages={Math.ceil((orders.data?.count || 0) / 20)}
            onChange={(page) => setOffset((page - 1) * 20)}
          />
        </>
      )}
    </>
  );
}

function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);
    if (diffSec < 60) return 'Just now';
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return dateString;
  }
}

function MerchantPayments({ store }: { store: Store }) {
  const { user, notify } = useShop();
  const client = useQueryClient();
  const [requestingPayout, setRequestingPayout] = useState(false);
  const [payoutAmount, setPayoutAmount] = useState('');
  const [bankName, setBankName] = useState('');
  const [accountNumber, setAccountNumber] = useState('');
  const [notes, setNotes] = useState('');
  const [payoutBusy, setPayoutBusy] = useState(false);
  const [activeTab, setActiveTab] = useState<'requests' | 'ledger'>('requests');
  const [financeSearch, setFinanceSearch] = useState('');
  const [financeStatus, setFinanceStatus] = useState('');

  const stats = useQuery({
    queryKey: ['dashboard', store.id, '30'],
    queryFn: () => api<Dashboard>(`stores/${store.id}/dashboard?days=30&time_zone=${encodeURIComponent(browserTimeZone())}`),
  });

  const payouts = useQuery({
    queryKey: ['merchant-payouts', store.id],
    queryFn: () => api<StorePayout[]>(`stores/${store.id}/payouts`),
  });

  const ledger = useQuery({
    queryKey: ['merchant-ledger', store.id],
    queryFn: () => api<{ count: number; results: StoreEarningsLedger[] }>(`stores/wallet/ledger?store_id=${store.id}&limit=50`),
  });

  const wallet = stats.data?.wallet;
  const isOfficial = Boolean(store.is_official);
  const canWithdraw = !user?.is_staff && !user?.is_superuser && !user?.is_business_admin;
  const availableBal = Number(wallet?.available_balance || '0');

  async function submitPayout(event: FormEvent) {
    event.preventDefault();
    setPayoutBusy(true);
    try {
      await api(`stores/${store.id}/payouts`, 'POST', {
        amount: payoutAmount,
        payout_method: 'bank_transfer',
        account_details: { bank_name: bankName, account_number: accountNumber },
        notes: notes || undefined,
      });
      await client.invalidateQueries({ queryKey: ['dashboard', store.id] });
      await client.invalidateQueries({ queryKey: ['merchant-payouts', store.id] });
      await client.invalidateQueries({ queryKey: ['merchant-ledger', store.id] });
      await client.invalidateQueries({ queryKey: ['merchant-notifications-count', store.id] });
      notify('Payout request submitted. Staff will review and process your transfer.');
      setRequestingPayout(false);
      setPayoutAmount('');
      setNotes('');
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setPayoutBusy(false);
    }
  }

  return (
    <>
      <div className="merchant-heading">
        <div>
          <h1>Payments & Payouts</h1>
          <p>Financial balance, cleared withdrawals, and earnings ledger for {store.name}.</p>
        </div>
        <div className="form-actions">
          {isOfficial ? (
            (user?.is_superuser || user?.is_business_admin) ? (
              <Link className="button secondary" href="/admin/commission" title="Official company store revenues consolidate into Platform Treasury">
                <WalletCards size={17} />
                Platform Treasury
              </Link>
            ) : null
          ) : (
            canWithdraw && <button
              className="button"
              disabled={availableBal < 5}
              onClick={() => setRequestingPayout(true)}
              title={availableBal < 5 ? 'Minimum payout is $5.00' : 'Request payout to bank'}
            >
              <WalletCards size={17} />
              Request payout
            </button>
          )}
        </div>
      </div>

      <div className="stats-grid">
        {[
          {
            label: isOfficial ? 'Consolidated Treasury Sales' : 'Available for Payout',
            value: money(wallet?.available_balance || '0.00'),
            icon: WalletCards,
            note: isOfficial ? 'Cleared sales consolidated into Platform Treasury (/admin/commission)' : 'Cleared sales past 7-day refund window',
            highlight: availableBal > 0,
          },
          {
            label: 'In Review (Escrow)',
            value: money(wallet?.in_review || '0.00'),
            icon: Clock,
            note: 'Pending orders within 7-day refund protection period',
          },
          {
            label: isOfficial ? 'Gross Sales (100% Retained)' : 'Gross Sales (Item Value)',
            value: money(wallet?.gross_sales || stats.data?.sales.estimated_item_value || '0.00'),
            icon: ChartNoAxesCombined,
            note: isOfficial ? 'Zero commission official store exemption' : 'Cumulative sales before platform fee',
          },
          {
            label: isOfficial ? 'Platform Fee (0%)' : `Platform Commission (${wallet?.platform_fee_percent || '4'}%)`,
            value: isOfficial ? '$0.00' : money(wallet?.platform_fee_deducted || '0.00'),
            icon: ShoppingBag,
            note: isOfficial ? 'Exempt from platform commission fees' : 'Marketplace hosting & payment processing fee',
          },
        ].map(({ label, value, icon: Icon, note, highlight }, index) => (
          <div key={label} className={`stat-item stat-${index}`} style={highlight ? { borderColor: 'var(--green)' } : undefined}>
            <div>
              <span>{label}</span>
              <Icon size={19} />
            </div>
            <strong>{value}</strong>
            <small>{note}</small>
          </div>
        ))}
      </div>

      {!isOfficial && requestingPayout && (
        <div className="setup-notice" style={{ flexDirection: 'column', alignItems: 'stretch', marginTop: 24, padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 16 }}>Request Store Payout</h3>
              <p className="muted" style={{ margin: '4px 0 0', fontSize: 12 }}>
                Withdraw cleared funds directly to your verified bank account via direct bank transfer.
              </p>
            </div>
            <button
              className="icon-button"
              onClick={() => setRequestingPayout(false)}
              aria-label="Close payout form"
            >
              <X size={18} />
            </button>
          </div>
          <form className="form-stack" onSubmit={submitPayout}>
            <div className="form-row">
              <Field label={`Withdrawal Amount ($ USD, Max: ${money(availableBal)})`}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input
                    type="number"
                    min="5.00"
                    max={availableBal}
                    step="0.01"
                    required
                    value={payoutAmount}
                    onChange={e => setPayoutAmount(e.target.value)}
                    placeholder="0.00"
                    style={{ flex: 1 }}
                  />
                  <button
                    type="button"
                    className="button secondary"
                    style={{ minHeight: 42, padding: '0 12px', fontSize: 11 }}
                    onClick={() => setPayoutAmount(String(availableBal.toFixed(2)))}
                  >
                    Max ({money(availableBal)})
                  </button>
                </div>
              </Field>
              <Field label="Bank Name">
                <input
                  required
                  value={bankName}
                  onChange={e => setBankName(e.target.value)}
                  placeholder="e.g. Chase, Wells Fargo, Barclays"
                />
              </Field>
            </div>
            <div className="form-row">
              <Field label="Account Number / IBAN">
                <input
                  required
                  value={accountNumber}
                  onChange={e => setAccountNumber(e.target.value)}
                  placeholder="e.g. 1234567890"
                />
              </Field>
              <Field label="Payout Note / Memo (Optional)">
                <input
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  placeholder="e.g. Monthly withdrawal"
                />
              </Field>
            </div>
            <div className="form-actions" style={{ marginTop: 8 }}>
              <button className="button" disabled={payoutBusy || availableBal < 5}>
                {payoutBusy ? 'Submitting request…' : 'Submit withdrawal request'}
                <ArrowRight size={16} />
              </button>
              <button type="button" className="button secondary" onClick={() => setRequestingPayout(false)}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div style={{ marginTop: 32 }}>
        <div className="merchant-toolbar" style={{ marginBottom: 16 }}>
          <div className="tabs">
            <button
              className={activeTab === 'requests' ? 'active' : ''}
              onClick={() => setActiveTab('requests')}
            >
              Payout Requests ({payouts.data?.length || 0})
            </button>
            <button
              className={activeTab === 'ledger' ? 'active' : ''}
              onClick={() => setActiveTab('ledger')}
            >
              Store Earnings Ledger ({ledger.data?.results?.length || 0})
            </button>
          </div>
          <div className="search-box"><Search size={16} /><input aria-label="Search payments" placeholder="Search reference or description…" value={financeSearch} onChange={event => setFinanceSearch(event.target.value)} /></div>
          <select aria-label="Filter payment status" value={financeStatus} onChange={event => setFinanceStatus(event.target.value)}><option value="">All statuses</option><option value="pending">Pending</option><option value="available">Available</option><option value="completed">Completed</option><option value="rejected">Rejected</option><option value="reversed">Reversed</option></select>
        </div>

        {activeTab === 'requests' ? (
          payouts.isLoading ? (
            <Loading />
          ) : payouts.error ? (
            <ErrorState error={payouts.error} retry={() => payouts.refetch()} />
          ) : !payouts.data?.length ? (
            <div className="empty-state">
              <WalletCards size={36} />
              <h2>No payout requests yet</h2>
              <p>
                {isOfficial
                  ? 'Official company store earnings are consolidated into the Platform Treasury. Payouts and transfers are audited at /admin/commission.'
                  : 'When you request withdrawals for cleared sales, they will be tracked here with their status and references.'}
              </p>
              {!isOfficial && availableBal >= 5 && canWithdraw && (
                <button className="button" onClick={() => setRequestingPayout(true)}>
                  Request your first payout
                </button>
              )}
            </div>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Reference</th>
                    <th>Amount</th>
                    <th>Method</th>
                    <th>Status</th>
                    <th>Processed</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {payouts.data.filter(p => (!financeStatus || p.status === financeStatus) && `${p.reference} ${p.notes || ''} ${p.payout_method}`.toLowerCase().includes(financeSearch.toLowerCase())).map(p => (
                    <tr key={p.id}>
                      <td>{new Date(p.created).toLocaleDateString(undefined, { dateStyle: 'medium' })}</td>
                      <td><strong>{p.reference}</strong></td>
                      <td><strong style={{ color: 'var(--ink)' }}>{money(p.amount)}</strong></td>
                      <td style={{ textTransform: 'capitalize' }}>{p.payout_method.replace('_', ' ')}</td>
                      <td><Status value={p.status} /></td>
                      <td className="muted">{p.processed_at ? new Date(p.processed_at).toLocaleDateString() : 'Pending review'}</td>
                      <td className="muted">{p.notes || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : (
          ledger.isLoading ? (
            <Loading />
          ) : ledger.error ? (
            <ErrorState error={ledger.error} retry={() => ledger.refetch()} />
          ) : !ledger.data?.results?.length ? (
            <div className="empty-state">
              <ShoppingBag size={36} />
              <h2>No ledger entries yet</h2>
              <p>As orders are placed and confirmed for {store.name}, detailed earnings, fees, and credit status will appear here.</p>
            </div>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Entry Type</th>
                    <th>Description</th>
                    <th>Gross</th>
                    <th>Fee</th>
                    <th>Net Amount</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.data.results.filter(entry => (!financeStatus || entry.status === financeStatus) && `${entry.reference} ${entry.description} ${entry.entry_type}`.toLowerCase().includes(financeSearch.toLowerCase())).map(entry => (
                    <tr key={entry.id}>
                      <td>{new Date(entry.created).toLocaleDateString(undefined, { dateStyle: 'medium' })}</td>
                      <td>
                        <span className={`status status-${entry.entry_type}`} style={{ textTransform: 'uppercase', fontSize: 8 }}>
                          {entry.entry_type}
                        </span>
                      </td>
                      <td>
                        <strong>{entry.description}</strong>
                        {entry.reference && <small style={{ display: 'block', color: 'var(--muted)', fontSize: 9 }}>Ref: {entry.reference}</small>}
                      </td>
                      <td>{money(entry.gross_amount)}</td>
                      <td className="muted">{money(entry.fee_amount)}</td>
                      <td><strong style={{ color: Number(entry.net_amount) >= 0 ? 'var(--green)' : 'var(--red)' }}>{money(entry.net_amount)}</strong></td>
                      <td><Status value={entry.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>

      <div className="dashboard-footnote" style={{ marginTop: 24 }}>
        {isOfficial
          ? 'Company official store: 100% of sales are retained with zero platform commission fee. Funds clear from review after the 7-day refund window expires.'
          : 'Net sales are calculated after the 4% platform marketplace fee. To protect against buyer returns and disputes, funds remain in escrow review for 7 days before becoming available for withdrawal.'}
      </div>
    </>
  );
}

function MerchantNotifications({ store }: { store: Store }) {
  const { notify } = useShop();
  const client = useQueryClient();
  const [tab, setTab] = useState<'all' | 'unread' | 'orders' | 'payouts' | 'archived'>('all');
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [isLive, setIsLive] = useState(true);
  const [busyAction, setBusyAction] = useState<number | null>(null);

  const queryParams = new URLSearchParams({
    store: String(store.id),
    limit: '15',
    offset: String(offset),
  });

  if (tab === 'unread') queryParams.set('state', 'unread');
  else if (tab === 'orders') queryParams.set('category', 'order');
  else if (tab === 'payouts') queryParams.set('category', 'payout');
  else if (tab === 'archived') queryParams.set('include_archived', 'true');

  if (search.trim()) queryParams.set('search', search.trim());

  const endpoint = tab === 'archived'
    ? `notifications/archived/?${queryParams.toString()}`
    : `notifications?${queryParams.toString()}`;

  const notifications = useQuery({
    queryKey: ['merchant-notifications', store.id, tab, search, offset],
    queryFn: () => api<Page<NotificationItem>>(endpoint),
    refetchInterval: isLive ? 10000 : false,
  });

  const counts = useQuery({
    queryKey: ['merchant-notifications-count', store.id],
    queryFn: () => api<NotificationCounts>(`notifications/counts/?store=${store.id}`),
    refetchInterval: isLive ? 10000 : false,
  });

  async function handleMarkAllRead() {
    try {
      await api(`notifications/mark-all-read?store=${store.id}`, 'POST');
      await client.invalidateQueries({ queryKey: ['merchant-notifications', store.id] });
      await client.invalidateQueries({ queryKey: ['merchant-notifications-count', store.id] });
      notify(`All notifications for ${store.name} marked as read.`);
    } catch (e) {
      notify((e as Error).message, true);
    }
  }

  async function toggleRead(item: NotificationItem) {
    setBusyAction(item.id);
    try {
      if (item.unread) {
        await api(`notifications/${item.id}/mark-read`, 'POST');
      } else {
        await api(`notifications/${item.id}/mark-unread`, 'POST');
      }
      await client.invalidateQueries({ queryKey: ['merchant-notifications', store.id] });
      await client.invalidateQueries({ queryKey: ['merchant-notifications-count', store.id] });
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusyAction(null);
    }
  }

  async function toggleArchive(item: NotificationItem) {
    setBusyAction(item.id);
    try {
      if (item.deleted) {
        await api(`notifications/${item.id}/restore`, 'POST');
        notify('Notification restored.');
      } else {
        await api(`notifications/${item.id}/archive`, 'POST');
        notify('Notification archived.');
      }
      await client.invalidateQueries({ queryKey: ['merchant-notifications', store.id] });
      await client.invalidateQueries({ queryKey: ['merchant-notifications-count', store.id] });
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusyAction(null);
    }
  }

  const items = notifications.data?.results || [];
  const totalCount = notifications.data?.count || 0;

  return (
    <>
      <div className="merchant-heading">
        <div>
          <h1>Store Notifications</h1>
          <p>Real-time activity and alert stream for {store.name}.</p>
        </div>
        <div className="form-actions">
          <button
            type="button"
            className={`merchant-live-badge ${isLive ? 'live' : ''}`}
            onClick={() => setIsLive(!isLive)}
            title={isLive ? 'Live feed is running. Click to pause.' : 'Live feed is paused. Click to resume.'}
          >
            <span className="merchant-live-dot" />
            {isLive ? 'Live stream active' : 'Stream paused'}
          </button>
          <button
            className="button secondary"
            style={{ fontSize: 11, minHeight: 35, padding: '0 12px' }}
            disabled={!counts.data?.unread}
            onClick={handleMarkAllRead}
            title="Mark all notifications for this store as read"
          >
            <CheckCheck size={15} />
            Mark all read
          </button>
          <button
            className="icon-button"
            title="Refresh notifications"
            aria-label="Refresh notifications"
            onClick={() => {
              notifications.refetch();
              counts.refetch();
            }}
          >
            <RotateCcw size={16} />
          </button>
        </div>
      </div>

      <div className="merchant-toolbar" style={{ flexWrap: 'wrap', gap: 14 }}>
        <div className="tabs" style={{ border: 0 }}>
          {[
            ['all', `All (${counts.data?.total || 0})`],
            ['unread', `Unread (${counts.data?.unread || 0})`],
            ['orders', 'Orders'],
            ['payouts', 'Payouts'],
            ['archived', `Archived (${counts.data?.archived || 0})`],
          ].map(([key, label]) => (
            <button
              key={key}
              className={tab === key ? 'active' : ''}
              onClick={() => {
                setTab(key as typeof tab);
                setOffset(0);
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="search-box" style={{ height: 36, width: 260 }}>
          <Search size={16} />
          <input
            aria-label="Search store notifications"
            placeholder="Search notifications…"
            value={search}
            onChange={e => {
              setSearch(e.target.value);
              setOffset(0);
            }}
          />
          {search && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => {
                setSearch('');
                setOffset(0);
              }}
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {notifications.isLoading ? (
        <Loading />
      ) : notifications.error ? (
        <ErrorState error={notifications.error} retry={() => notifications.refetch()} />
      ) : !items.length ? (
        <div className="empty-state">
          <Bell size={36} />
          <h2>No notifications found</h2>
          <p>
            {search
              ? 'No notifications match your search query. Try different keywords.'
              : tab === 'unread'
              ? `You are completely caught up! No unread notifications for ${store.name}.`
              : `Notifications regarding orders, customer updates, and payouts for ${store.name} will be tracked here live.`}
          </p>
        </div>
      ) : (
        <div style={{ marginTop: 12 }}>
          {items.map(item => {
            const isOrder =
              item.category === 'order' ||
              item.verb.toLowerCase().includes('order') ||
              Boolean(item.data?.order_id);
            const isPayout =
              item.category === 'payout' ||
              item.verb.toLowerCase().includes('payout') ||
              Boolean(item.data?.payout_id);
            const isProduct =
              item.category === 'store' ||
              item.verb.toLowerCase().includes('product') ||
              item.verb.toLowerCase().includes('stock');

            const categoryLabel =
              item.category?.toUpperCase() ||
              (isOrder ? 'ORDER' : isPayout ? 'PAYOUT' : isProduct ? 'INVENTORY' : 'STORE');

            return (
              <div
                key={item.id}
                className={`merchant-notification-card ${item.unread ? 'unread' : ''}`}
              >
                <span className={`notif-dot ${item.level || 'info'}`} />
                <div>
                  <div className="merchant-notif-header">
                    <span className={`notification-tag ${isOrder ? 'store' : ''}`}>{categoryLabel}</span>
                    <span className="merchant-notif-time" title={new Date(item.timestamp).toLocaleString()}>
                      {formatRelativeTime(item.timestamp)}
                    </span>
                  </div>
                  <h3 className="merchant-notif-title">{item.verb}</h3>
                  <p className="merchant-notif-desc">
                    {item.description || 'No additional details provided for this event.'}
                  </p>
                  <div className="merchant-notif-footer">
                    {isOrder && (
                      <Link href="/merchant/orders" className="text-link" style={{ fontSize: 11 }}>
                        Go to Orders <ArrowRight size={13} />
                      </Link>
                    )}
                    {isPayout && (
                      <Link href="/merchant/payments" className="text-link" style={{ fontSize: 11 }}>
                        View in Payments <ArrowRight size={13} />
                      </Link>
                    )}
                    {isProduct && (
                      <Link href="/merchant/products" className="text-link" style={{ fontSize: 11 }}>
                        Manage Inventory <ArrowRight size={13} />
                      </Link>
                    )}
                  </div>
                </div>
                <div className="merchant-notif-actions">
                  <button
                    className="icon-button"
                    style={{ width: 30, height: 30 }}
                    disabled={busyAction === item.id}
                    onClick={() => toggleRead(item)}
                    title={item.unread ? 'Mark as read' : 'Mark as unread'}
                    aria-label={item.unread ? 'Mark as read' : 'Mark as unread'}
                  >
                    <CheckCheck size={16} color={item.unread ? 'var(--green)' : 'var(--muted)'} />
                  </button>
                  <button
                    className="icon-button"
                    style={{ width: 30, height: 30 }}
                    disabled={busyAction === item.id}
                    onClick={() => toggleArchive(item)}
                    title={item.deleted ? 'Restore' : 'Archive'}
                    aria-label={item.deleted ? 'Restore' : 'Archive'}
                  >
                    {item.deleted ? <RotateCcw size={16} /> : <Archive size={16} />}
                  </button>
                </div>
              </div>
            );
          })}

          <Pagination page={Math.floor(offset / 15) + 1} totalPages={Math.ceil(totalCount / 15)} onChange={page => setOffset((page - 1) * 15)} />
        </div>
      )}
    </>
  );
}


function MerchantSettings({ store }: { store: Store }) {
  const { notify } = useShop(); const client = useQueryClient(); const [busy, setBusy] = useState(false);
  const profile = useQuery({ queryKey: ['store-profile', store.id], queryFn: () => api<StoreProfile>(`stores/${store.id}/profile`) });
  const address = useQuery({ queryKey: ['store-address', store.id], queryFn: () => api<Record<string, string>>(`stores/${store.id}/pickup-address`) });
  async function brandingSaved(updatedProfile: StoreProfile): Promise<void> {
    client.setQueryData<StoreProfile>(['store-profile', store.id], updatedProfile);
    await client.invalidateQueries({ queryKey: ['public-store'] });
  }

  async function connectStripe() {
    try {
      const result = await api<{ url: string }>(`stores/${store.id}/connect-stripe`, 'POST');
      if (result.url) window.location.assign(result.url);
    } catch (error) { notify((error as Error).message, true); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await api(`stores/${store.id}`, 'PATCH', { name: data.name });
      await api(`stores/${store.id}/profile`, 'PATCH', {
        email: data.email,
        bio: data.bio,
        announcement: data.announcement,
        website: data.website,
        phone1: data.phone1,
        whatsapp: data.whatsapp,
        instagram: data.instagram,
        twitter: data.twitter,
      });
      await api(`stores/${store.id}/pickup-address`, 'PUT', {
        address: data.address,
        city: data.city,
        state: data.state,
        country: data.country,
        zip: data.zip,
        is_default: true,
      });
      await client.invalidateQueries({ queryKey: ['stores'] });
      await client.invalidateQueries({ queryKey: ['public-store', store.id] });
      await profile.refetch();
      await address.refetch();
      notify('Your store details are updated');
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="merchant-heading">
        <div>
          <h1>Make yourself at home.</h1>
          <p>Your store, your brand identity.</p>
        </div>
        <button type="button" className="button secondary" onClick={connectStripe}>Connect Stripe payouts</button>
      </div>
      {profile.isLoading || address.isLoading ? (
        <Loading />
      ) : profile.error || address.error ? (
        <ErrorState error={(profile.error || address.error)!} />
      ) : (
        <form className="form-stack settings-form" onSubmit={submit}>
          <h2>Store branding</h2>
          <StoreBranding
            store={store}
            profile={profile.data}
            onSaved={brandingSaved}
          />
          <Field label="Store announcement">
            <input
              name="announcement"
              defaultValue={profile.data?.announcement || ''}
              placeholder="e.g. Free shipping on all orders over $50 · Holiday sale now live!"
              maxLength={255}
            />
          </Field>

          <h2>Store profile</h2>
          <div className="form-row">
            <Field label="Store name">
              <input name="name" defaultValue={store.name} required maxLength={40} />
            </Field>
            <Field label="Contact email">
              <input type="email" name="email" defaultValue={profile.data?.email} required />
            </Field>
          </div>
          <Field label="About your store (Bio)">
            <textarea name="bio" defaultValue={profile.data?.bio} rows={3} placeholder="Tell shoppers about your products and company mission..." />
          </Field>
          <div className="form-row">
            <Field label="Website URL">
              <input name="website" type="url" placeholder="https://…" defaultValue={profile.data?.website || ''} />
            </Field>
            <Field label="Telephone number">
              <input name="phone1" type="tel" placeholder="+1 (555) 000-0000" defaultValue={profile.data?.phone1 || ''} />
            </Field>
          </div>
          <div className="form-row">
            <Field label="WhatsApp">
              <input name="whatsapp" type="tel" placeholder="+1 (555) 000-0000" defaultValue={profile.data?.whatsapp || ''} />
            </Field>
            <Field label="X / Twitter (@handle or URL)">
              <input name="twitter" defaultValue={profile.data?.twitter || ''} placeholder="https://x.com/yourhandle" />
            </Field>
          </div>
          <Field label="Instagram URL">
            <input name="instagram" type="url" defaultValue={profile.data?.instagram || ''} placeholder="https://instagram.com/yourhandle" />
          </Field>

          <h2>Pickup & shipping address</h2>
          <Field label="Street address">
            <input name="address" required defaultValue={address.data?.address} />
          </Field>
          <div className="form-row">
            {['city', 'state', 'country', 'zip'].map(field => (
              <Field label={field === 'zip' ? 'Postal code' : field[0].toUpperCase() + field.slice(1)} key={field}>
                <input name={field} required defaultValue={address.data?.[field] || ''} />
              </Field>
            ))}
          </div>
          <button className="button" disabled={busy}>
            {busy ? 'Saving…' : 'Save store details'}
            <Check size={17} />
          </button>
        </form>
      )}
    </>
  );
}


export function ProductPreviewPage(): React.JSX.Element {
  const [selectedVariant, setSelectedVariant] = useState<number>(0);
  const [selectedGalleryImage, setSelectedGalleryImage] = useState<string | null>(null);
  const [quantity, setQuantity] = useState<number>(1);
  const [preview, setPreview] = useState<PreviewProduct | null>(null);
  const [ready, setReady] = useState<boolean>(false);

  const loadPreview = useCallback((): boolean => {
    try {
      const local = typeof window !== 'undefined' ? localStorage.getItem('proace-product-preview') : null;
      if (local) {
        setPreview(JSON.parse(local) as PreviewProduct);
        return true;
      }
      const session = typeof window !== 'undefined' ? sessionStorage.getItem('proace-product-preview') : null;
      if (session) {
        setPreview(JSON.parse(session) as PreviewProduct);
        return true;
      }
    } catch {
      /* Show an empty state when storage is unavailable. */
    }
    return false;
  }, []);

  useEffect(() => {
    loadPreview();
    setReady(true);

    function handleStorage(e: StorageEvent) {
      if (e.key === 'proace-product-preview' && e.newValue) {
        try {
          setPreview(JSON.parse(e.newValue) as PreviewProduct);
        } catch {
          /* ignore malformed payloads */
        }
      }
    }
    window.addEventListener('storage', handleStorage);

    let channel: BroadcastChannel | null = null;
    try {
      if (typeof BroadcastChannel !== 'undefined') {
        channel = new BroadcastChannel('proace-product-preview');
        channel.onmessage = (event: MessageEvent<PreviewProduct>) => {
          if (event.data && typeof event.data === 'object') {
            setPreview(event.data);
          }
        };
      }
    } catch {
      /* BroadcastChannel not available */
    }

    return () => {
      window.removeEventListener('storage', handleStorage);
      if (channel) {
        channel.close();
      }
    };
  }, [loadPreview]);

  if (!ready) return <Loading />;
  if (!preview) return <Empty title="No product preview available" text="Open Preview from your product editor to see your unsaved listing here." href="/merchant/products" label="Back to products" />;
  const activeVariant: ProductVariant | undefined = preview.variants[selectedVariant];
  const displayedPrice: number = preview.sale_price + Number(activeVariant?.price_delta || 0);
  const effectiveStock: number = preview.is_digital ? 99 : typeof activeVariant?.available === 'number' ? activeVariant.available : preview.available;
  const originalPrice: number = preview.price + Number(activeVariant?.price_delta || 0);
  const previewImages = [...new Set([...(preview.images.length ? preview.images : [preview.image]), preview.image, ...(preview.variants || []).map(variant => variant.image_url || '')].filter(Boolean))];
  return (
    <Gate next="/merchant">
      <main className="container product-page">
        <div className="breadcrumb"><span>Home</span><ChevronRight size={12} /><span>Shop</span><ChevronRight size={12} /><span>{preview.title}</span></div>
        <div className="storefront-preview-banner">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '20px' }}>🔒</span>
            <div>
              <div className="storefront-preview-title">Product Preview Mode</div>
              <div className="storefront-preview-desc">Preview only. Nothing has been saved, and purchase actions are disabled.</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="button secondary storefront-preview-button"
              onClick={() => {
                loadPreview();
              }}
              title="Sync latest changes made in your product editor"
            >
              <RotateCcw size={14} />
              Sync changes
            </button>
            <button
              type="button"
              className="button secondary storefront-preview-button"
              onClick={() => window.close()}
            >
              Close preview
            </button>
          </div>
        </div>
        <div className="product-detail">
          <div>
            <div style={{ position: 'relative' }}>
              <ProductGallery
                key={preview.title + previewImages.join(',')}
                images={previewImages}
                title={preview.title}
                discount={preview.discount}
                activeImage={selectedGalleryImage ?? activeVariant?.image_url ?? preview.image}
                onImageChange={setSelectedGalleryImage}
              />
              {preview.digital_preview_watermark && <span style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: 'rgba(255,255,255,.55)', fontSize: 'clamp(18px, 4vw, 42px)', fontWeight: 700, transform: 'rotate(-24deg)', pointerEvents: 'none', textAlign: 'center' }}>PROACE PREVIEW</span>}
            </div>
          </div>
          <div className="product-information">
            <span className="eyebrow green" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              {preview.brand || preview.category}
              <VerifiedBadge tier="starter" size={14} />
            </span>
            <h1>{preview.title}</h1>
            <div className="rating-line" style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><Star size={16} fill="currentColor" /><strong>New arrival</strong></span>
              <span style={{ color: 'var(--line)' }}>•</span>
              <button className="text-button" type="button" disabled>0 reviews</button>
            </div>
            <div className="detail-price" style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <strong>{displayedPrice > 0 ? money(displayedPrice) : 'Price TBD'}</strong>
              {preview.discount > 0 && (
                <>
                  <del>{money(originalPrice)}</del>
                  <span>You save {money(originalPrice - displayedPrice)}</span>
                </>
              )}
              {preview.flash_sale_end && (
                <FlashCountdown end={preview.flash_sale_end} />
              )}
            </div>
            <p className="description">{preview.description}</p>
            {preview.variants.length > 0 && (
              <div className="product-variants" style={{ margin: '16px 0' }}>
                <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--ink)', display: 'block', marginBottom: '8px' }}>Option: <strong style={{ color: 'var(--green)' }}>{activeVariant?.name || 'Select'}</strong></span>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {preview.variants.map((variant, index) => (
                    <button
                      type="button"
                      key={index}
                      aria-pressed={selectedVariant === index}
                      onClick={() => {
                        setSelectedVariant(index);
                        setSelectedGalleryImage(variant.image_url || preview.image);
                      }}
                      style={{
                        padding: '6px 14px',
                        borderRadius: '8px',
                        border: selectedVariant === index ? '2px solid var(--green)' : '1px solid var(--line)',
                        background: selectedVariant === index ? 'var(--green-light)' : 'var(--paper)',
                        color: selectedVariant === index ? 'var(--green)' : 'var(--ink)',
                        fontWeight: selectedVariant === index ? 600 : 500,
                        fontSize: '13px',
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <span>{variant.name || `Option ${index + 1}`}</span>
                      {variant.price_delta && (
                        <span style={{ fontSize: '11px', opacity: 0.85 }}>
                          (
                          {variant.price_delta.startsWith('+') || variant.price_delta.startsWith('-')
                            ? variant.price_delta
                            : `+$${variant.price_delta}`}
                          )
                        </span>
                      )}
                      {typeof variant.available === 'number' && variant.available <= 0 && (
                        <span style={{ fontSize: '11px', color: 'var(--muted)' }}>(Sold out)</span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div
              className={`stock ${
                preview.product_type === 'affiliate_clickbank' || preview.is_digital || effectiveStock > 0
                  ? ''
                  : 'sold-out'
              }`}
            >
              <span />
              {preview.product_type === 'affiliate_clickbank'
                ? 'Official Partner Listing · In Stock'
                : preview.is_digital
                  ? 'Unlimited digital inventory'
                  : effectiveStock > 5
                    ? 'In stock. Ready for your everyday.'
                    : effectiveStock
                      ? `Only ${effectiveStock} left in stock`
                      : 'Currently out of stock'}
            </div>
            {!preview.is_digital && preview.product_type !== 'affiliate_clickbank' && (
              <label className="field">
                <span>Quantity</span>
                <span className="quantity">
                  <button
                    type="button"
                    disabled={quantity <= 1}
                    onClick={() => setQuantity((value) => Math.max(1, value - 1))}
                  >
                    −
                  </button>
                  <span>{quantity}</span>
                  <button
                    type="button"
                    disabled={quantity >= effectiveStock}
                    onClick={() => setQuantity((value) => Math.min(effectiveStock, value + 1))}
                  >
                    +
                  </button>
                </span>
              </label>
            )}
            {preview.is_digital && (
              <div className="digital-badge">
                <strong>Instant digital download</strong>
                <span>{preview.digital_file_name || 'File will be available after purchase'}</span>
              </div>
            )}
            <div className="purchase-actions">
              {preview.product_type === 'affiliate_clickbank' ? (
                <button
                  type="button"
                  className="button"
                  style={{ background: '#ea580c', borderColor: '#ea580c', color: '#fff' }}
                  disabled
                >
                  <ArrowUpRight size={16} />
                  {preview.affiliate_button_text || 'Buy on Partner Site'}
                </button>
              ) : (
                <button type="button" className="button" disabled>
                  <ShoppingBag size={16} />Add to bag
                </button>
              )}
              <button
                type="button"
                className="button secondary"
                aria-label="Save product"
                disabled
              >
                <Heart size={20} />
              </button>
            </div>
            <div className="delivery-note">
              <Truck size={21} />
              <div>
                <strong>
                  {preview.product_type === 'affiliate_clickbank'
                    ? 'Fulfilled by partner'
                    : preview.is_digital
                      ? 'Worldwide digital download'
                      : 'US delivery only'}
                </strong>
                <p>
                  {preview.product_type === 'affiliate_clickbank'
                    ? 'Order processing and shipping are handled directly by ClickBank and the partner vendor.'
                    : preview.is_digital
                      ? 'Your download link appears in your order after checkout. No shipping fee.'
                      : 'Physical products are currently delivered only within the United States.'}
                </p>
              </div>
            </div>
            <div className="delivery-note">
              <ShieldCheck size={21} />
              <div>
                <strong>Secure payment</strong>
                <p>
                  {preview.product_type === 'affiliate_clickbank'
                    ? 'ClickBank guarantees secure payment processing and customer purchase protection.'
                    : 'Major credit and debit cards, Apple Pay, Google Pay via Stripe, and ProAce Wallet are supported.'}
                </p>
              </div>
            </div>
            <div
              className="seller-link"
              aria-disabled="true"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                background: 'var(--soft)',
                border: '1px solid var(--line)',
                borderRadius: '10px',
                marginTop: '16px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div
                  style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: '50%',
                    background: 'var(--green-light)',
                    display: 'grid',
                    placeItems: 'center',
                    color: 'var(--green)',
                    flexShrink: 0,
                  }}
                >
                  <StoreIcon size={18} />
                </div>
                <div>
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 5,
                      fontSize: '13px',
                    }}
                  >
                    Sold by <strong style={{ color: 'var(--ink)' }}>{preview.brand || 'Your store'}</strong>
                    <VerifiedBadge tier="starter" size={16} />
                  </span>
                  <p className="muted" style={{ fontSize: '11px', margin: 0 }}>
                    Preview seller profile
                  </p>
                </div>
              </div>
              <ArrowUpRight size={18} className="muted" />
            </div>
          </div>
        </div>
        <section className="product-tabs">
          <div className="tabs" role="tablist">
            <button role="tab" aria-selected className="active" disabled>
              Product details
            </button>
            <button role="tab" disabled>
              Reviews (0)
            </button>
            <button role="tab" disabled>
              Delivery &amp; returns
            </button>
          </div>
          <div className="tab-content" role="tabpanel">
            <h2>Made for your everyday</h2>
            <p>{preview.description}</p>
            <p className="fine-print">
              Preview only. Customer reviews and delivery details will appear after publishing.
            </p>
          </div>
        </section>
      </main>
    </Gate>
  );
}
