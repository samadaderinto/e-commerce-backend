'use client';

import { useNotificationDetail } from './notification-detail';

import { CollectionCount, CollectionFilters, CollectionPagination, financialFields, useCollectionFilters, useDebouncedValue } from './collection-filters';


import { browserTimeZone, calendarDateLabel, toLocalDateTimeInput } from '@/lib/datetime';

import { DateStamp, activityDate } from './activity';
import { StoreBranding, type ImageKind } from './store-branding';
import { BankAccounts } from './bank-accounts';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Archive, ArrowDownToLine, ArrowLeft, ArrowRight, ArrowUpRight, Ban, Bell, ChartNoAxesCombined, Check, CheckCheck, ChevronLeft, ChevronRight, CircleHelp, Clock, Eye, FileText, Heart, Inbox, LayoutDashboard, Mail, Package, Pin, Plus, Printer, RotateCcw, Search, Settings, Share2, Shield, ShieldCheck, ShoppingBag, Star, Store as StoreIcon, Trash2, Truck, Upload, UserCheck, UserPlus, Users, WalletCards, X } from 'lucide-react';
import { api, categories, money } from '@/lib/api';
import type { Dashboard, MerchantProduct, MerchantRefund, MerchantRefundItem, NotificationCounts, NotificationItem, Page, ProductVariant, Store, StoreEarningsLedger, StorePayout, TrackingEvent, StoreProfile, StoreTeamMember, StoreTeamRole } from '@/lib/types';
import { useShop } from './providers';
import { Gate } from './account';
import { useDialogFocus, Pagination, Empty, ErrorState, Field, Loading, ProductImage, ProductGallery, FlashCountdown, DropCountdown, Status, VerifiedBadge, normalizeImageUrl, ResponsiveMediaImage } from './ui';

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
  has_physical_items?: boolean;
  order_status?: string;
  customer?: { name?: string; email?: string; phone?: string };
  shipping_address?: Record<string, unknown>;
  items: { product: number; title: string; quantity: number; is_digital?: boolean }[];
};

type PreviewProduct = {
  title: string; description: string; brand: string; category: string; is_digital: boolean;
  price: number; sale_price: number; discount: number; available: number; image: string;
  variants: ProductVariant[]; digital_file_name?: string; digital_file_url?: string;
  images: string[]; flash_sale_end?: string | null; drop_at?: string | null; digital_preview_watermark?: boolean;
  label?: string;
  product_type?: 'standard' | 'affiliate_clickbank';
  affiliate_hoplink?: string;
  affiliate_vendor_nickname?: string;
  affiliate_button_text?: string;
};

type StripeConnectStatus = {
  connected: boolean;
  details_submitted: boolean;
  payouts_enabled: boolean;
  currently_due: string[];
};

type StripeConnectResponse = {
  connected: boolean;
  pending: boolean;
  url: string;
};

type MerchantPaymentDetail = {
  title: string;
  category: string;
  rows: [string, string][];
};


export function MerchantPage({ segments }: { segments: string[] }) {
  const { user } = useShop();
  const searchParams = useSearchParams();
  const requestedStoreId = searchParams.get('store') || '';
  const [selection, setSelection] = useState<{ owner: number; storeId: number | null } | null>(null);
  const selectionReady = !!user && selection?.owner === user.id;
  useEffect(() => {
    if (!user) { setSelection(null); return; }
    let storeId: number | null = null;
    const requestedId = Number(requestedStoreId);
    if (Number.isSafeInteger(requestedId) && requestedId > 0) {
      storeId = requestedId;
    }
    try {
      if (storeId === null) {
        const saved = Number(localStorage.getItem(`proace-active-store-${user.id}`));
        if (Number.isSafeInteger(saved) && saved > 0) storeId = saved;
      } else {
        localStorage.setItem(`proace-active-store-${user.id}`, String(storeId));
      }
    } catch { /* Storage may be unavailable; keep switching usable. */ }
    setSelection({ owner: user.id, storeId });
  }, [user?.id, requestedStoreId]);
  function selectStore(storeId: number) {
    if (!user) return;
    setSelection({ owner: user.id, storeId });
    try { localStorage.setItem(`proace-active-store-${user.id}`, String(storeId)); }
    catch { /* The current selection still works when storage is unavailable. */ }
  }
  const stores = useQuery({ queryKey: ['stores', user?.id], queryFn: () => api<Page<Store>>('stores?limit=100'), enabled: !!user, refetchInterval: 30000 });
  const selectedStore = useQuery({ queryKey: ['stores', 'selected', user?.id, selection?.storeId], queryFn: () => api<Store>(`stores/${selection?.storeId}`), enabled: !!user && selectionReady && !!selection?.storeId });
  const store = selectionReady
    ? selectedStore.data?.id
      ? selectedStore.data
      : selection.storeId
        ? stores.data?.results.find(item => item.id === selection.storeId)
        : stores.data?.results[0]
    : undefined;
  const section = segments[0] || 'overview';
  const storeLimitReached = !user?.is_superuser && !user?.is_business_admin && (stores.data?.count || 0) >= 10;

  const notifCounts = useQuery({
    queryKey: ['merchant-notifications-count', store?.id],
    queryFn: () => api<NotificationCounts>(`notifications/counts/?store=${store?.id}`),
    enabled: !!store?.id,
    refetchInterval: 12000,
  });

  const role: StoreTeamRole = store?.user_role || 'owner';

  const links = [
    ['overview', 'Overview', LayoutDashboard],
    ['products', 'Products', Package],
    ['orders', 'Orders', ShoppingBag],
    ['refunds', 'Refunds', RotateCcw],
    ['payments', 'Payments', WalletCards],
    ['notifications', 'Notifications', Bell],
    ['team', 'Store team', Users],
    ['settings', 'Store settings', Settings],
  ] as const;

  const isLinkAllowed = (key: string) => {
    if (key === 'overview' || key === 'notifications') return true;
    if (role === 'owner') {
      if (key === 'payments' && user?.is_staff && !user?.is_superuser && !user?.is_business_admin) {
        return false;
      }
      return true;
    }
    if (role === 'store_admin') {
      if (key === 'payments') return false;
      return true;
    }
    if (role === 'catalog_manager') {
      return key === 'products';
    }
    if (role === 'fulfillment_specialist') {
      return key === 'orders' || key === 'refunds';
    }
    return false;
  };

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
              .filter(([key]) => isLinkAllowed(key))
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
                <ResponsiveMediaImage
                  src={user.avatar_url}
                  alt={user.first_name || 'User'}
                  style={{ width: 32, height: 32, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }}
                  sizes="32px"
                  width={64}
                  height={64}
                />
              ) : (
                <span>{user?.first_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}</span>
              )}
              <div>
                <strong>
                  {user?.first_name} {user?.last_name}
                </strong>
                <small>
                  {user?.is_staff
                    ? 'Official store operations'
                    : role === 'owner'
                    ? 'Store owner'
                    : role === 'store_admin'
                    ? 'Store administrator'
                    : role === 'catalog_manager'
                    ? 'Catalog manager'
                    : 'Fulfillment specialist'}
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

          {stores.isLoading || !selectionReady || (selectedStore.isLoading && !store) ? (
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
              <OnboardStore onCreated={selectStore} />
            )
          ) : store.status === 'blocked' ? (
            <Empty
              title="Your store is unavailable"
              text="Contact support about your store status before making further changes."
              href="/help"
              label="Visit help centre"
            />
          ) : section === 'products' && segments[1] ? (
            role === 'fulfillment_specialist' ? (
              <Empty
                title="Access Restricted"
                text="Fulfillment specialists do not have permission to edit catalog products."
                href="/merchant"
                label="Return to workspace"
              />
            ) : (
              <ProductEditor
                key={`${store.id}-${segments[1]}`}
                store={store}
                id={segments[1]}
              />
            )
          ) : section === 'products' ? (
            role === 'fulfillment_specialist' ? (
              <Empty
                title="Access Restricted"
                text="Fulfillment specialists do not have permission to manage catalog products."
                href="/merchant"
                label="Return to workspace"
              />
            ) : (
              <MerchantProducts key={store.id} store={store} />
            )
          ) : section === 'orders' ? (
            role === 'catalog_manager' ? (
              <Empty
                title="Access Restricted"
                text="Catalog managers do not have permission to view store orders."
                href="/merchant"
                label="Return to workspace"
              />
            ) : (
              <MerchantOrders
                key={store.id}
                store={store}
                stores={stores.data?.results || []}
                onSelectStore={selectStore}
              />
            )
          ) : section === 'refunds' ? (
            role === 'catalog_manager' ? (
              <Empty
                title="Access Restricted"
                text="Catalog managers do not have permission to manage refunds."
                href="/merchant"
                label="Return to workspace"
              />
            ) : (
              <MerchantRefunds
                key={store.id}
                store={store}
                stores={stores.data?.results || []}
                onSelectStore={selectStore}
              />
            )
          ) : section === 'payments' ? (
            role !== 'owner' ? (
              <Empty
                title="Access Restricted"
                text="Only the primary store owner can view financial payouts and banking."
                href="/merchant"
                label="Return to workspace"
              />
            ) : (
              <MerchantPayments key={store.id} store={store} />
            )
          ) : section === 'notifications' ? (
            <MerchantNotifications key={store.id} store={store} />
          ) : section === 'team' ? (
            role !== 'owner' && role !== 'store_admin' ? (
              <Empty
                title="Access Restricted"
                text="Only store owners and administrators can manage team members."
                href="/merchant"
                label="Return to workspace"
              />
            ) : (
              <MerchantTeam key={store.id} store={store} />
            )
          ) : section === 'settings' ? (
            role !== 'owner' && role !== 'store_admin' ? (
              <Empty
                title="Access Restricted"
                text="Only store owners and administrators can manage store settings."
                href="/merchant"
                label="Return to workspace"
              />
            ) : (
              <MerchantSettings key={store.id} store={store} />
            )
          ) : (
            <MerchantDashboard key={store.id} store={store} />
          )}
        </div>
      </div>
    </Gate>
  );
}

function OnboardStore({
  onCreated,
}: {
  onCreated: (storeId: number) => void;
}) {
  const { user, notify } = useShop();
  const client = useQueryClient();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [storeName, setStoreName] = useState<string>('');
  const [images, setImages] = useState<Partial<Record<ImageKind, File>>>({});
  const [imageUrls, setImageUrls] = useState<Partial<Record<ImageKind, string>>>({});
  const createdStore = useRef<Store | null>(null);

  useEffect(() => () => {
    if (imageUrls.avatar) URL.revokeObjectURL(imageUrls.avatar);
  }, [imageUrls.avatar]);

  useEffect(() => () => {
    if (imageUrls.banner) URL.revokeObjectURL(imageUrls.banner);
  }, [imageUrls.banner]);

  function selectImage(kind: ImageKind, file: File | null): void {
    setImages(current => ({ ...current, [kind]: file || undefined }));
    setImageUrls(current => ({ ...current, [kind]: file ? URL.createObjectURL(file) : undefined }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    const data = Object.fromEntries(new FormData(event.currentTarget));

    try {
      const store = createdStore.current || await api<Store>('stores', 'POST', {
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
      createdStore.current = store;
      for (const kind of ['avatar', 'banner'] as const) {
        const file = images[kind];
        if (!file) continue;
        const upload = new FormData();
        upload.append('image', file);
        await api(`stores/${store.id}/profile-images/${kind}`, 'POST', upload);
        setImages(current => ({ ...current, [kind]: undefined }));
      }
      await client.invalidateQueries({ queryKey: ['stores'] });
      onCreated(store.id);
      notify('Your store is ready. Time for your first product.');
      router.push('/merchant/products/new');
    } catch (error) {
      setError(
        `${createdStore.current ? 'Your store was created, but an image could not be saved. Retry to finish uploading. ' : ''}${(error as Error).message}`,
      );
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
            <input name="name" required maxLength={40} placeholder="Something memorable" value={storeName} onChange={event => setStoreName(event.target.value)} />
          </Field>
          <Field label="Contact email">
            <input type="email" name="email" required defaultValue={user?.email} />
          </Field>
        </div>
        <Field label="About your store">
          <textarea name="bio" placeholder="A little about what makes your store yours" />
        </Field>
        <h3>Your store identity</h3>
        <StoreBranding
          store={{ name: storeName || 'Your store', username: '' }}
          profile={{ avatar_url: imageUrls.avatar, banner_url: imageUrls.banner }}
          onDraftChange={selectImage}
          disabled={busy}
        />
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
  const stats = useQuery({
    queryKey: ['dashboard', store.id, days],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[1] === store.id ? previousData : undefined,
    queryFn: () => api<Dashboard>(
      `stores/${store.id}/dashboard?days=${days}&time_zone=${encodeURIComponent(browserTimeZone())}`,
    ),
  });
  const orders = useQuery({ queryKey: ['merchant-recent', store.id], queryFn: () => api<Page<MerchantOrder>>(`stores/${store.id}/orders?limit=5`) });
  const payouts = useQuery({ queryKey: ['merchant-payouts', store.id], queryFn: () => api<StorePayout[]>(`stores/${store.id}/payouts`) });
  const checklist = useQuery({ queryKey: ['onboarding', store.id], queryFn: () => api<{complete: boolean; steps: Record<string, boolean>}>(`stores/${store.id}/onboarding`) });
  const [requestingPayout, setRequestingPayout] = useState(false);
  const [payoutAmount, setPayoutAmount] = useState('');
  const [bankAccountId, setBankAccountId] = useState<number | null>(null);
  const [payoutBusy, setPayoutBusy] = useState(false);
  const data = stats.data;
  const values = data?.orders_by_day.slice(-30) || []; const max = Math.max(1, ...values.map(day => day.count));

  async function submitPayout(event: FormEvent) {
    event.preventDefault(); setPayoutBusy(true);
    try {
      await api(`stores/${store.id}/payouts`, 'POST', {
        amount: payoutAmount,
        payout_method: 'bank_transfer',
        bank_account_id: bankAccountId,
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

      {stats.isFetching && !stats.isLoading && <Loading compact overlay />}

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
                  value: money(data.wallet?.withdrawable_balance ?? data.wallet?.available_balance ?? '0.00'),
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
                      label={`Payout amount (Max: ${money(data.wallet?.withdrawable_balance ?? data.wallet?.available_balance ?? '0.00')})`}
                    >
                      <input
                        type="number"
                        min="5.00"
                        max={Number(data.wallet?.withdrawable_balance ?? data.wallet?.available_balance ?? '0')}
                        step="0.01"
                        required
                        value={payoutAmount}
                        onChange={(e) => setPayoutAmount(e.target.value)}
                        placeholder="0.00"
                      />
                    </Field>
                  </div>
                  <div className="treasury-bank-picker">
                    <BankAccounts compact pickerOnly selectedId={bankAccountId} onSelect={setBankAccountId} />
                  </div>
                  <div className="form-row">
                    <button className="button" disabled={payoutBusy || !bankAccountId}>
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
              {orders.isFetching && !orders.isLoading && <Loading compact overlay />}
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
              {payouts.isFetching && !payouts.isLoading && <Loading compact overlay />}
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
                        <th>Created</th>
                        <th>Reference</th>
                        <th>Amount</th>
                        <th>Method</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {payouts.data.map((p) => (
                        <tr key={p.id}>
                          <td><DateStamp value={p.created} dateOnly /></td>
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

function exportRows(products: MerchantProduct[]): void {
  const escape = (value: unknown) =>
    `"${String(value).replace(/^[=+@-]/, "'$&").replaceAll('"', '""')}"`;

  const rows = [
    ['ID', 'Product', 'Price', 'Stock', 'Units sold', 'Published'],
    ...products.map((product) => [
      product.id,
      product.title,
      product.price,
      product.is_digital ? 'Unlimited' : product.available,
      product.product_type === 'affiliate_clickbank' ? 'Not tracked' : product.sales,
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
  const debouncedSearch = useDebouncedValue(search);
  const extraFilters = useCollectionFilters();
  useEffect(() => { setOffset(0); }, [extraFilters.query]);
  const [filter, setFilter] = useState('');
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState<number | null>(null);
  const { notify } = useShop();
  const client = useQueryClient();

  const query = new URLSearchParams({ ...Object.fromEntries(new URLSearchParams(extraFilters.query)), search: debouncedSearch, ordering, limit: '15', offset: String(offset) });
  if (filter) {
    query.set('visibility', filter);
  }

  const products = useQuery({
    queryKey: ['merchant-products', store.id, query.toString()],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[1] === store.id ? previousData : undefined,
    queryFn: () => api<Page<MerchantProduct>>(`stores/${store.id}/products?${query}`),
  });

  const profileQuery = useQuery({
    queryKey: ['store-profile', store.id],
    queryFn: () => api<StoreProfile>(`stores/${store.id}/profile`),
  });
  const pinnedIds = profileQuery.data?.pinned_products || [];

  async function togglePin(product: MerchantProduct) {
    const isPinned = pinnedIds.includes(product.id);
    if (!isPinned && pinnedIds.length >= 3) {
      notify('You can pin at most 3 products on your store page. Unpin a product first.', true);
      return;
    }
    const nextPinned = isPinned
      ? pinnedIds.filter((id) => id !== product.id)
      : [...pinnedIds, product.id];
    setBusy(product.id);
    try {
      await api(`stores/${store.id}/profile`, 'PATCH', { pinned_products: nextPinned });
      await client.invalidateQueries({ queryKey: ['store-profile', store.id] });
      await client.invalidateQueries({ queryKey: ['public-store', store.id] });
      await client.invalidateQueries({ queryKey: ['products'] });
      notify(isPinned ? 'Product unpinned from store page' : 'Product pinned to top of store page');
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setBusy(null);
    }
  }

  async function toggle(product: MerchantProduct) {
    if (product.is_blocked) {
      notify('This product is blocked by platform moderation. Only staff can restore it.', true);
      return;
    }
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

      <CollectionFilters filters={extraFilters} label="product filters" hideSearch fields={[
        { key: 'category', label: 'Category', options: categories.map(category => ({ value: category.key, label: category.name })) },
        { key: 'is_digital', label: 'Delivery type', options: [{ value: 'true', label: 'Digital' }, { value: 'false', label: 'Physical' }] },
        { key: 'stock', label: 'Stock', options: [{ value: 'in', label: 'In stock' }, { value: 'low', label: 'Low stock' }, { value: 'out', label: 'Out of stock' }] },
        { key: 'product_type', label: 'Listing type', options: [{ value: 'standard', label: 'Standard' }, { value: 'affiliate_clickbank', label: 'Partner' }] },
      ]} />
      <button type="button" className="button secondary" onClick={() => {
        extraFilters.reset();
        setSearch('');
        setFilter('');
        setOrdering('-updated');
        setOffset(0);
      }}>Reset all filters</button>
      {products.isFetching && !products.isLoading && <Loading compact overlay />}

      {products.isLoading ? (
        <Loading />
      ) : products.error ? (
        <ErrorState error={products.error} retry={() => products.refetch()} />
      ) : !products.data?.results.length ? (
        <Empty
          title={search || filter || extraFilters.active ? 'Nothing matches just yet' : 'Your first product starts here'}
          text={
            search || filter || extraFilters.active
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
                  <th>Created</th>
                  <th>Updated</th>
                  <th>Category</th>
                  <th>Price</th>
                  <th>Inventory</th>
                  <th>Units sold</th>
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
                    <td><DateStamp value={product.created} /></td>
                    <td><DateStamp value={product.updated} /></td>
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
                      {product.product_type === 'affiliate_clickbank' ? (
                        <span className="muted" title="Partner purchases are completed outside ProAce and are not tracked as sold units.">
                          Not tracked
                        </span>
                      ) : (
                        product.sales.toLocaleString()
                      )}
                    </td>
                    <td>
                      {product.is_blocked ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                          <span
                            className="status status-blocked"
                            title={product.blocked_reason ? `Blocked: ${product.blocked_reason}. Contact support to request restoration.` : 'Blocked by platform moderation'}
                          >
                            Blocked
                          </span>
                          <small className="muted" style={{ fontSize: '9px' }}>Locked by moderation</small>
                        </div>
                      ) : (
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
                      )}
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <button
                          type="button"
                          className="icon-button"
                          style={{
                            color: pinnedIds.includes(product.id) ? 'var(--ink)' : 'var(--muted)',
                            background: pinnedIds.includes(product.id) ? 'var(--soft)' : 'transparent',
                            border: pinnedIds.includes(product.id) ? '1px solid var(--line)' : '1px solid transparent',
                          }}
                          title={pinnedIds.includes(product.id) ? 'Pinned to top of store page (click to unpin)' : 'Pin to top of store page (max 3)'}
                          aria-label={pinnedIds.includes(product.id) ? `Unpin ${product.title}` : `Pin ${product.title}`}
                          disabled={busy === product.id}
                          onClick={() => togglePin(product)}
                        >
                          <Pin size={15} fill={pinnedIds.includes(product.id) ? 'currentColor' : 'none'} />
                        </button>
                        <Link
                          className="icon-button"
                          title="Edit product"
                          aria-label={`Edit ${product.title}`}
                          href={`/merchant/products/${product.id}`}
                        >
                          <ArrowUpRight size={18} />
                        </Link>
                      </div>
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

function isProtectedDigitalPreview(url: string | undefined): boolean {
  return Boolean(url && url.includes('digital-previews/'));
}

function variantAssetAccepts(kind: ProductVariant['digital_file_type']): string | undefined {
  if (kind === 'audio') return 'audio/*';
  if (kind === 'video') return 'video/*';
  if (kind === 'image') return 'image/*';
  return undefined;
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
  const [variantAssetFiles, setVariantAssetFiles] = useState<Record<number, File>>({});
  const [coverPreview, setCoverPreview] = useState<string | null>(null);
  const [showCoverUrlInput, setShowCoverUrlInput] = useState(false);

  const [digitalFile, setDigitalFile] = useState<File | null>(null);
  const [digitalPreviewUrl, setDigitalPreviewUrl] = useState<string | null>(null);
  const [digitalUrlInput, setDigitalUrlInput] = useState<string | null>(null);
  const [digitalWatermark, setDigitalWatermark] = useState<boolean | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [showDigitalUrlInput, setShowDigitalUrlInput] = useState(false);

  const activeDigitalUrl = digitalUrlInput ?? product.data?.digital_file_url ?? '';
  const isImageDigitalAsset = isDigitalImage(digitalFile, activeDigitalUrl);
  const hasDigitalAsset = Boolean(digitalFile || (activeDigitalUrl && activeDigitalUrl.trim().length > 0));
  const effectiveWatermark = isImageDigitalAsset ? (digitalWatermark ?? product.data?.digital_preview_watermark ?? true) : false;
  const autoDigitalCover = (effectiveIsDigital && isImageDigitalAsset) ? (digitalPreviewUrl || (activeDigitalUrl.startsWith('http') || activeDigitalUrl.startsWith('/api') ? activeDigitalUrl : '')) : '';
  const effectiveCoverImage = coverPreview || coverImage || product.data?.image_url || autoDigitalCover || '';
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

  function selectVariantAsset(index: number, file: File | undefined): void {
    if (!file) return;
    if (file.size > 50 * 1024 * 1024) {
      notify('Variant digital files must be 50 MB or smaller.', true);
      return;
    }
    setVariantAssetFiles((current) => ({ ...current, [index]: file }));
  }

  function clearProtectedVariantImages(): void {
    const nextVariants = effectiveVariants.map((variant) => (
      isProtectedDigitalPreview(variant.image_url)
        ? { ...variant, image_url: '' }
        : variant
    ));
    if (nextVariants.some((variant, index) => variant !== effectiveVariants[index])) {
      setVariants(nextVariants);
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
      clearProtectedVariantImages();
    } else {
      setDigitalWatermark(true);
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
    const autoCover = (digital && isImage) ? (digitalPreviewUrl || (activeFileUrl.startsWith('http') || activeFileUrl.startsWith('/api') ? activeFileUrl : '')) : '';
    const fallbackCover = effectiveCoverImage || autoCover || product.data?.image_url || 'https://placehold.co/900x900/1b2921/9bd7b5?text=Product+Preview';
    return {
      title: values.title?.trim() || product.data?.title || 'Untitled product',
      description: values.description?.trim() || product.data?.description || 'Product description coming soon.',
      brand: values.brand?.trim() || store.name,
      category: values.category || product.data?.category || 'General',
      is_digital: digital,
      price: Number.isFinite(price) && price > 0 ? price : Number(product.data?.price || 0),
      sale_price: affiliate
        ? (Number.isFinite(price) && price > 0 ? price : Number(product.data?.price || 0))
        : Number.isFinite(price) && price > 0
          ? (price * (100 - Number(values.discount || 0))) / 100
          : (Number(product.data?.price || 0) * (100 - Number(product.data?.discount || 0))) / 100,
      discount: affiliate ? 0 : Number(values.discount ?? product.data?.discount ?? 0),
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
      flash_sale_end: affiliate
        ? null
        : values.flash_sale_end
          ? new Date(values.flash_sale_end).toISOString()
          : (product.data?.flash_sale_end || null),
      drop_at: affiliate
        ? null
        : values.drop_at
          ? new Date(values.drop_at).toISOString()
          : (product.data?.drop_at || null),
      digital_preview_watermark: digital && isImage && (digitalWatermark ?? (values.digital_preview_watermark === 'on' || true)),
      variants: affiliate
        ? []
        : effectiveVariants
            .filter((v) => v.name && v.name.trim())
            .map((v) => ({
              ...v,
              price_delta: v.price_delta || '0.00',
              available: digital ? 999 : Number(v.available || 0),
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
    setVariants([...effectiveVariants, {
      name: '',
      price_delta: '0.00',
      available: 10,
      digital_file_type: isImageDigitalAsset ? 'image' : 'document',
    }]);
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
    const dropAt = form.drop_at ? new Date(form.drop_at).toISOString() : null;
    const validVariants = affiliate ? [] : effectiveVariants
      .filter(v => v.name && v.name.trim().length > 0)
      .map(v => ({
        ...v,
        name: v.name.trim(),
        price_delta: v.price_delta || '0.00',
        available: digital ? 999 : (typeof v.available === 'number' ? v.available : Number(v.available || 0)),
      }));

    let fileUrl = form.digital_file_url || data?.digital_file_url || '';
    if (digital && !fileUrl && digitalFile) {
      // Use a temporary valid placeholder while we upload the digital file to media storage
      fileUrl = `https://storage.local/pending-asset-${Date.now()}`;
    }
    const isImage = isDigitalImage(digitalFile, fileUrl);

    const payload = {
      ...form,
      product_type: affiliate ? 'affiliate_clickbank' : 'standard',
      affiliate_hoplink: affiliate ? (form.affiliate_hoplink?.trim() || '') : '',
      affiliate_vendor_nickname: affiliate ? (form.affiliate_vendor_nickname?.trim() || '') : '',
      affiliate_button_text: affiliate ? (form.affiliate_button_text?.trim() || 'Buy on Partner Site') : '',
      image_url: coverFile ? '' : (form.image_url || coverImage || data?.image_url || ''),
      available: affiliate ? 999 : (digital ? 0 : Number(form.available)),
      discount: affiliate ? 0 : Number(form.discount || 0),
      flash_sale_end: affiliate ? null : flashEnd,
      drop_at: affiliate ? null : dropAt,
      variants: validVariants,
      weight: (affiliate || digital) ? '0.00' : (form.weight || '1.00'),
      length: (affiliate || digital) ? null : (form.length ? Number(form.length) : null),
      width: (affiliate || digital) ? null : (form.width ? Number(form.width) : null),
      height: (affiliate || digital) ? null : (form.height ? Number(form.height) : null),
      visibility: form.visibility === 'on',
      is_digital: digital,
      digital_file_url: digital ? fileUrl : '',
      digital_preview_watermark: digital && isImage ? (digitalWatermark ?? (form.digital_preview_watermark === 'on' || true)) : false,
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

      // Direct file upload to media storage for cover image
      if (coverFile) {
        const coverForm = new FormData();
        coverForm.append('image', coverFile);
        coverForm.append('is_cover', 'true');
        await api(`stores/${store.id}/products/${targetId}/images`, 'POST', coverForm);
        setCoverFile(null);
      }

      // Direct file upload to media storage for digital download
      if (digital && digitalFile) {
        const assetForm = new FormData();
        assetForm.append('file', digitalFile);
        await api(`stores/${store.id}/products/${targetId}/digital-file`, 'POST', assetForm);
        setDigitalFile(null);
      }

      const pendingVariantIndexes = Object.keys(variantAssetFiles).map(Number);
      if (pendingVariantIndexes.length > 0) {
        const uploadedVariants = [...validVariants];
        for (const index of pendingVariantIndexes) {
          const assetFile = variantAssetFiles[index];
          if (!assetFile || !uploadedVariants[index]) continue;
          const variantForm = new FormData();
          variantForm.append('file', assetFile);
          variantForm.append('asset_type', uploadedVariants[index].digital_file_type || 'document');
          const asset = await api<{ digital_file_url: string; image_url?: string }>(
            `stores/${store.id}/products/${targetId}/variant-file`,
            'POST',
            variantForm,
          );
          uploadedVariants[index] = {
            ...uploadedVariants[index],
            digital_file_url: asset.digital_file_url,
            image_url: asset.image_url || uploadedVariants[index].image_url || '',
          };
        }
        await api<MerchantProduct>(
          `stores/${store.id}/products/${targetId}`,
          'PATCH',
          { variants: uploadedVariants },
        );
        setVariants(uploadedVariants);
        setVariantAssetFiles({});
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
  const productErrorStatus = typeof product.error === 'object' && product.error !== null && 'status' in product.error
    ? (product.error as { status?: unknown }).status
    : undefined;
  const productIsOutsideSelectedStore = productErrorStatus === 404 || product.error?.message === 'No Product matches the given query.';
  if (productIsOutsideSelectedStore) {
    return (
      <Empty
        title="This product is not in the selected store"
        text="Switch to the store that owns this listing, or manage another seller’s product from Backoffice."
        href="/merchant/products"
        label="View selected store products"
      />
    );
  }
  if (product.error) return <ErrorState error={product.error} />;

  const data = product.data;

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

      {data?.is_blocked && (
        <div
          className="analytics-panel"
          style={{
            borderLeft: '4px solid var(--red, #a44240)',
            background: 'var(--soft)',
            marginBottom: '1.5rem',
            padding: '1.25rem',
            borderRadius: '4px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--red, #a44240)', fontWeight: 700, marginBottom: '6px' }}>
            <Ban size={18} />
            <span>Product blocked by platform moderation</span>
          </div>
          <p style={{ margin: '0.25rem 0', color: 'var(--ink)' }}>
            <strong>Reason:</strong> {data.blocked_reason || 'Policy violation'}
          </p>
          <p className="muted" style={{ margin: '0.5rem 0 0', fontSize: '12px', lineHeight: 1.6 }}>
            <strong>Next steps:</strong> You can edit and update this listing below to address the flagged issue. Once compliant with platform policies, contact support or reply to your notification to request a review and restoration. Only authorized platform staff can restore this listing. Existing orders remain valid and must be fulfilled.
          </p>
        </div>
      )}

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
            <span>{(digitalFile.size / (1024 * 1024)).toFixed(2)} MB · Ready to upload</span>
            <span className="upload-preview-badge">Pending save</span>
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
            <span className="upload-preview-badge">Active asset</span>
          </div>
          <div style={{ display: 'flex', gap: '6px' }}>
            <a href={`/api/stores/${store.id}/products/${id}/digital-file`} target="_blank" rel="noopener noreferrer" download className="button secondary compact" title="Test file download">
              <ArrowDownToLine size={13} /> Test
            </a>
            <label className="button secondary compact" style={{ cursor: 'pointer' }}>
              <Upload size={13} /> Replace
              <input type="file" accept=".pdf,.zip,.epub,.mp3,.mp4,.mobi,.rar,.txt,.doc,.docx,.png,.jpg,.jpeg,.webp,.svg,.avif" style={{ display: 'none' }} onChange={handleDigitalFileChange} />
            </label>
          </div>
        </div>
      ) : (
        <label className="upload-dropzone">
          <div className="upload-dropzone-icon"><FileText size={20} /></div>
          <span className="upload-dropzone-text">Click or drag digital file to upload</span>
          <span className="upload-dropzone-sub">PDF, ZIP, EPUB, MP3, MP4, PNG, JPG up to 50 MB · Direct secure upload</span>
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
                clearProtectedVariantImages();
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

  {!isAffiliate && (
    <>
      <h2>Product options &amp; variants</h2>
      <p className="fine-print">
        {effectiveIsDigital
          ? 'Offer different editions, resolutions, or formats (e.g. 4K Wallpaper, Mobile HD, Print-Ready Vector). Each option can adjust the price and map to a distinct preview image.'
          : 'Add a separate option for each color, size, or combination, such as Black / Large. Each option has its own stock and price adjustment.'}
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
                  placeholder={effectiveIsDigital ? 'e.g. 4K Ultra HD Wallpaper' : 'e.g. Black / Large'}
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
              {effectiveIsDigital && (
                <Field label="Variant digital file">
                  <select
                    aria-label={`Variant ${index + 1} digital file type`}
                    value={variant.digital_file_type || 'document'}
                    onChange={(event) => updateVariant(
                      index,
                      'digital_file_type',
                      event.target.value,
                    )}
                  >
                    <option value="image">Image</option>
                    <option value="audio">Audio</option>
                    <option value="video">Video</option>
                    <option value="document">Document, software, or other</option>
                  </select>
                  <input
                    type="file"
                    accept={variantAssetAccepts(variant.digital_file_type || 'document')}
                    onChange={(event) =>
                      selectVariantAsset(index, event.target.files?.[0])
                    }
                  />
                  {variantAssetFiles[index] && (
                    <small className="muted">
                      {variant.digital_file_type === 'image'
                        ? `${variantAssetFiles[index].name} becomes this option's private image download and a watermarked carousel preview.`
                        : `${variantAssetFiles[index].name} becomes this option's downloadable file when you save.`}
                    </small>
                  )}
                  {variant.digital_file_url && (
                    <small className="muted">A file is already mapped to this option.</small>
                  )}
                </Field>
              )}
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
              {effectiveIsDigital ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--muted)', paddingTop: '28px' }}>
                  <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: 'var(--green)' }} />
                  Unlimited digital inventory
                </div>
              ) : (
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
              )}
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
    {effectiveIsDigital && isImageDigitalAsset
      ? 'Your digital artwork file is automatically used as the watermarked storefront cover image. You can optionally upload a custom promotional cover below.'
      : 'Upload a primary cover image for your product. Gallery photos and variant mapping can be managed below after saving.'}
  </p>

  {coverPreview ? (
    <div className="upload-preview-card">
      <ResponsiveMediaImage
        src={coverPreview}
        alt="Cover preview"
        className="upload-preview-thumb"
        sizes="180px"
        width={360}
        height={360}
      />
      <div className="upload-preview-meta">
        <strong>{coverFile?.name || 'Selected cover photo'}</strong>
        <span>
          {coverFile ? `${(coverFile.size / 1024).toFixed(1)} KB` : ''} · Ready to upload
        </span>
        <span className="upload-preview-badge">Pending save</span>
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
    <div
      className="upload-preview-card"
      style={autoDigitalCover && !coverFile && !coverImage && !product.data?.image_url ? { border: '1px solid var(--green)' } : undefined}
    >
      <ProductImage
        src={effectiveCoverImage}
        alt={autoDigitalCover && !coverImage && !product.data?.image_url ? 'Auto-generated cover from digital asset' : 'Current cover photo'}
        className="upload-preview-thumb"
      />
      <div className="upload-preview-meta">
        <strong>
          {autoDigitalCover && !coverFile && !coverImage && !product.data?.image_url
            ? 'Auto-generated from digital asset'
            : 'Cover photo'}
        </strong>
        <span style={{ fontSize: '11px', color: 'var(--muted)', wordBreak: 'break-all' }}>
          {autoDigitalCover && !coverFile && !coverImage && !product.data?.image_url
            ? 'Automatically serving as public preview with PROACE PREVIEW watermark overlay'
            : normalizeImageUrl(effectiveCoverImage)}
        </span>
        <span
          className="upload-preview-badge"
          style={autoDigitalCover && !coverFile && !coverImage && !product.data?.image_url ? { background: 'var(--green-light)', color: 'var(--green)' } : undefined}
        >
          {autoDigitalCover && !coverFile && !coverImage && !product.data?.image_url
            ? 'Watermarked cover preview'
            : 'Active cover'}
        </span>
      </div>
      <label
        className="button secondary compact"
        style={{ cursor: 'pointer' }}
      >
        <Upload size={13} /> {autoDigitalCover && !coverImage && !product.data?.image_url ? 'Upload custom cover' : 'Change'}
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
        PNG, JPG, or WEBP up to 5 MB · High-resolution cover photo
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
    <Field label={isAffiliate ? "Vendor Reference Price (USD)" : "Price (USD)"}>
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
    {isAffiliate ? (
      <div
        className="card-soft"
        style={{
          padding: '12px 14px',
          margin: '12px 0',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          background: 'var(--muted-bg, rgba(0, 0, 0, 0.03))',
        }}
      >
        <p style={{ margin: 0, fontSize: '0.85rem', fontWeight: 600, color: 'var(--foreground)' }}>
          Partner-Controlled Pricing & Promotions
        </p>
        <p className="fine-print" style={{ margin: '4px 0 0', color: 'var(--muted)', fontSize: '0.78rem', lineHeight: 1.4 }}>
          This reference price is for internal catalog records. Shoppers see “Price available on partner site.” The vendor controls the final price, promotions, and availability. ProAce discounts and flash deal timers are unavailable for ClickBank offers.
        </p>
        <input type="hidden" name="discount" value="0" />
      </div>
    ) : (
      <>
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
          {!effectiveIsDigital && (
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
        <Field label="Flash Deal Expiration (Optional)">
          <input
            name="flash_sale_end"
            type="datetime-local"
            defaultValue={
              data?.flash_sale_end ? toLocalDateTimeInput(data.flash_sale_end) : ''
            }
          />
        </Field>
        <Field label="Store Drop / Scheduled Release (Optional)">
          <input
            name="drop_at"
            type="datetime-local"
            defaultValue={
              data?.drop_at ? toLocalDateTimeInput(data.drop_at) : ''
            }
          />
          <small style={{ display: 'block', marginTop: 4, color: 'var(--muted)', fontSize: '12px' }}>
            Schedule a future drop release. The item will be visible in the catalog with a live countdown timer and active viewer counter, but cart addition and purchasing are locked until release.
          </small>
        </Field>
      </>
    )}
    <hr />
    <h3>Availability</h3>
    <label className="check-row" style={data?.is_blocked ? { opacity: 0.7, cursor: 'not-allowed' } : undefined}>
      <input
        type="checkbox"
        name="visibility"
        disabled={data?.is_blocked}
        defaultChecked={data?.visibility || false}
      />
      Publish to the marketplace
    </label>
    {data?.is_blocked && (
      <small className="muted" style={{ display: 'block', marginTop: '-6px', marginBottom: '8px' }}>
        This listing is blocked by platform moderation. Staff/admin review is required to restore it.
      </small>
    )}
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
  const protectsGalleryPreviews = product.is_digital && product.digital_preview_watermark;
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
      notify(`${uploaded} image${uploaded === 1 ? '' : 's'} uploaded successfully`);
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
      notify('Digital product asset uploaded successfully');
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
          <Upload size={17} />{uploading ? 'Uploading…' : 'Upload gallery images'}
          <input type="file" multiple accept="image/jpeg,image/png,image/webp" disabled={uploading} onChange={uploadImages} />
        </label>
      </div>
      {protectsGalleryPreviews && (
        <p className="fine-print">
          Gallery images for this digital artwork are converted into watermarked previews. The original files stay private.
        </p>
      )}
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
                <h3>Digital Product Asset</h3>
                <p style={{ margin: 0, fontSize: '11px', color: 'var(--muted)' }}>
                  {product.digital_file_url ? 'Customers receive instant download access upon purchase.' : 'No digital file uploaded yet.'}
                </p>
              </div>
            </div>
            <div className="digital-asset-card-actions">
              {product.digital_file_url && (
                <a href={`/api/stores/${store.id}/products/${product.id}/digital-file`} target="_blank" rel="noopener noreferrer" download className="button secondary compact">
                  <ArrowDownToLine size={14} /> Test download
                </a>
              )}
              <label className="button secondary compact" style={{ cursor: 'pointer' }}>
                <Upload size={14} /> {digitalUploading ? 'Uploading…' : product.digital_file_url ? 'Replace file' : 'Upload file'}
                <input type="file" accept=".pdf,.zip,.epub,.mp3,.mp4,.mobi,.rar,.txt,.doc,.docx,.png,.jpg,.jpeg,.webp,.svg,.avif" disabled={digitalUploading} style={{ display: 'none' }} onChange={handleDigitalUpload} />
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

function MerchantOrderTable({
  orders,
  storeId,
  focusOrderId,
  onUpdated,
  onOrderDetailsClosed,
  isFiltered,
  onResetFilters,
}: {
  orders: MerchantOrder[];
  storeId?: number;
  focusOrderId?: string;
  onUpdated?: () => void;
  onOrderDetailsClosed?: () => void;
  isFiltered?: boolean;
  onResetFilters?: () => void;
}) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const [detailsOrder, setDetailsOrder] = useState<MerchantOrder | null>(null);
  const [trackingOrder, setTrackingOrder] = useState<MerchantOrder | null>(null);
  const detailsDialogRef = useDialogFocus(Boolean(detailsOrder), () => closeOrderDetails());
  const trackingDialogRef = useDialogFocus(!!trackingOrder, () => setTrackingOrder(null));
  const [trackingNumber, setTrackingNumber] = useState('');
  const [carrier, setCarrier] = useState('USPS');
  const [orderStatus, setOrderStatus] = useState('shipped');
  const [busy, setBusy] = useState(false);
  const [allowEditTracking, setAllowEditTracking] = useState(false);
  const [confirmVerified, setConfirmVerified] = useState(false);
  const { notify } = useShop();

  useEffect(() => {
    if (!focusOrderId) return;
    const targetOrder = orders.find((order) => String(order.id) === focusOrderId);
    if (targetOrder) setDetailsOrder(targetOrder);
  }, [focusOrderId, orders]);

  function closeOrderDetails(): void {
    setDetailsOrder(null);
    onOrderDetailsClosed?.();
  }

  const hasExistingTracking = Boolean(trackingOrder?.tracking_number);
  const isTrackingModified = hasExistingTracking && trackingNumber.trim() !== (trackingOrder?.tracking_number || '').trim();
  const detailItems = Array.isArray(detailsOrder?.items) ? detailsOrder.items : [];
  const detailFields: [string, string][] = detailsOrder ? [
    ['Order status', detailsOrder.order_status || detailsOrder.status],
    ['Placed', activityDate(detailsOrder.created)],
    ['Customer', detailsOrder.customer?.name || 'Guest checkout'],
    ['Email', detailsOrder.customer?.email || ''],
    ['Phone', detailsOrder.customer?.phone || ''],
    ['Products', detailItems.map((item) => `${item.title} × ${item.quantity}`).join(', ')],
    ['Units', String(detailItems.reduce((sum, item) => sum + item.quantity, 0))],
    ['Delivery', detailsOrder.has_physical_items === false ? 'Digital delivery' : 'Physical delivery'],
    ['Carrier', detailsOrder.carrier || ''],
    ['Tracking number', detailsOrder.tracking_number || ''],
    ['Shipping address', Object.values(detailsOrder.shipping_address || {})
      .filter((value): value is string | number => typeof value === 'string' || typeof value === 'number')
      .map(String)
      .filter((value) => value.trim())
      .join(', ')],
  ] : [];

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
    if (isFiltered) {
      return (
        <div className="empty-state">
          <Search size={30} />
          <h2>No matching orders</h2>
          <p>No orders matched your current search or filter criteria.</p>
          {onResetFilters && (
            <button
              type="button"
              className="button secondary"
              style={{ marginTop: '0.75rem' }}
              onClick={onResetFilters}
            >
              Clear filters
            </button>
          )}
        </div>
      );
    }
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
              <th>Created</th>
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
            {orders.map((order) => {
              const orderItems = Array.isArray(order.items) ? order.items : [];
              const isDigital =
                order.has_physical_items === false ||
                (orderItems.length > 0 && orderItems.every((it) => Boolean(it.is_digital)));

              return (
                <tr key={order.id}>
                  <td>
                    <button
                      type="button"
                      className="text-link order-reference-link"
                      title="View order details"
                      aria-label={`View details for order ${order.reference}`}
                      onClick={() => setDetailsOrder(order)}
                    >
                      #{order.reference}
                    </button>
                  </td>
                  <td>
                    <DateStamp value={order.created} dateOnly />
                  </td>
                  <td>
                    {expanded === order.id
                      ? orderItems.map((item) => (
                          <p key={item.product}>
                            {item.title} × {item.quantity}
                          </p>
                        ))
                      : `${orderItems[0]?.title || 'Order'}${
                          orderItems.length > 1 ? ` +${orderItems.length - 1}` : ''
                        }`}
                  </td>
                  <td>
                    {orderItems.reduce((sum, item) => sum + item.quantity, 0)}
                  </td>
                  <td>
                    {isDigital ? (
                      <span
                        className="muted"
                        style={{
                          fontSize: '0.8rem',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        <ArrowDownToLine size={13} color="var(--green)" />
                        Digital delivery
                      </span>
                    ) : order.tracking_number ? (
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
                    {!isDigital && storeId && ['pending', 'confirmed', 'shipped'].includes(order.status) && (
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
              );
            })}
          </tbody>
        </table>
      </div>

      {detailsOrder && (
        <div
          className="dialog-backdrop admin-detail-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeOrderDetails();
          }}
        >
          <section
            ref={detailsDialogRef}
            className="admin-detail-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="merchant-order-detail-title"
          >
            <header className="admin-detail-header">
              <div className="admin-detail-heading">
                <span className="admin-detail-icon" aria-hidden="true"><FileText size={22} /></span>
                <div>
                  <span className="eyebrow green">Order details</span>
                  <h2 id="merchant-order-detail-title">#{detailsOrder.reference}</h2>
                </div>
              </div>
              <button type="button" className="icon-button no-print" aria-label="Close details" onClick={closeOrderDetails}>
                <X size={20} />
              </button>
            </header>
            <div className="admin-detail-body">
              <div className="admin-detail-status">
                <span>Store fulfillment</span>
                <Status value={detailsOrder.status.toLowerCase()} />
              </div>
              <dl className="admin-detail-grid">
                {detailFields.filter(([, value]) => value.trim()).map(([label, value]) => (
                  <div className="admin-detail-field" key={label}>
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
            <footer className="admin-detail-footer no-print">
              <button type="button" className="button secondary" onClick={() => window.print()}>
                <Printer size={16} />
                Print details
              </button>
              <button type="button" className="button" onClick={closeOrderDetails}>Done</button>
            </footer>
          </section>
        </div>
      )}

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

function MerchantOrders({
  store,
  stores = [],
  onSelectStore,
}: {
  store: Store;
  stores?: Store[];
  onSelectStore?: (storeId: number) => void;
}) {
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search);
  const [status, setStatus] = useState('');
  const [timeframe, setTimeframe] = useState('');
  const [carrier, setCarrier] = useState('');
  const [ordering, setOrdering] = useState('-created');
  const [offset, setOffset] = useState(0);
  const client = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const focusOrderId = searchParams.get('order') || '';

  const hasActiveFilters = Boolean(
    search.trim() || status || timeframe || carrier || ordering !== '-created'
  );

  const queryParams = new URLSearchParams({
    limit: '20',
    offset: String(offset),
  });
  if (status) queryParams.set('status', status);
  if (search.trim()) queryParams.set('search', debouncedSearch.trim());
  if (timeframe) queryParams.set('days', timeframe);
  if (carrier) queryParams.set('carrier', carrier);
  if (ordering && ordering !== '-created') queryParams.set('ordering', ordering);
  if (/^\d+$/.test(focusOrderId)) queryParams.set('order_id', focusOrderId);

  const orders = useQuery({
    queryKey: [
      'merchant-orders',
      store.id,
      status,
      search.trim(),
      timeframe,
      carrier,
      ordering,
      offset,
      focusOrderId,
    ],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[1] === store.id
        && previousQuery.queryKey.at(-1) === focusOrderId
        ? previousData
        : undefined,
    queryFn: () =>
      api<Page<MerchantOrder>>(
        `stores/${store.id}/orders?${queryParams.toString()}`
      ),
  });

  function resetFilters() {
    setSearch('');
    setStatus('');
    setTimeframe('');
    setCarrier('');
    setOrdering('-created');
    setOffset(0);
  }

  function clearOrderDeepLink(): void {
    if (!focusOrderId) return;
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete('order');
    nextParams.delete('store');
    const query = nextParams.toString();
    router.replace(`/merchant/orders${query ? `?${query}` : ''}`, { scroll: false });
  }

  return (
    <>
      <div className="merchant-heading">
        <div>
          <h1>Every order, a good beginning.</h1>
          <p>Follow your customers’ finds from your store.</p>
        </div>
        {orders.data?.count !== undefined && (
          <span className="badge" style={{ fontSize: '0.85rem', padding: '0.35rem 0.75rem' }}>
            {orders.data.count} {orders.data.count === 1 ? 'order' : 'orders'}
          </span>
        )}
      </div>

      <div
        className="merchant-toolbar"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '0.75rem',
          marginBottom: '1.25rem',
        }}
      >
        <div className="search-box" style={{ flex: '1 1 260px', minWidth: '220px' }}>
          <Search size={16} />
          <input
            aria-label="Search orders"
            placeholder="Search by order #, customer, email, tracking, item…"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
          />
          {search && (
            <button
              type="button"
              className="icon-button"
              aria-label="Clear search"
              onClick={() => {
                setSearch('');
                setOffset(0);
              }}
            >
              <X size={15} />
            </button>
          )}
        </div>

        {stores.length > 1 && (
          <select
            aria-label="Filter orders by store"
            value={store.id}
            onChange={(event) => {
              onSelectStore?.(Number(event.target.value));
              setOffset(0);
            }}
          >
            {stores.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        )}

        <select
          aria-label="Filter orders by status"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setOffset(0);
          }}
        >
          <option value="">All statuses</option>
          {[
            ['pending', 'Pending'],
            ['confirmed', 'Confirmed'],
            ['shipped', 'Shipped'],
            ['delivered', 'Delivered'],
            ['picked up', 'Picked Up'],
            ['cancelled', 'Cancelled'],
            ['refunded', 'Refunded'],
          ].map(([val, label]) => (
            <option key={val} value={val}>
              {label}
            </option>
          ))}
        </select>

        <select
          aria-label="Filter orders by timeframe"
          value={timeframe}
          onChange={(event) => {
            setTimeframe(event.target.value);
            setOffset(0);
          }}
        >
          <option value="">All time</option>
          <option value="7">Last 7 days</option>
          <option value="30">Last 30 days</option>
          <option value="90">Last 90 days</option>
        </select>

        <select
          aria-label="Filter orders by carrier"
          value={carrier}
          onChange={(event) => {
            setCarrier(event.target.value);
            setOffset(0);
          }}
        >
          <option value="">All carriers</option>
          <option value="USPS">USPS</option>
          <option value="UPS">UPS</option>
          <option value="FedEx">FedEx</option>
          <option value="DHL">DHL Express</option>
        </select>

        <select
          aria-label="Sort orders"
          value={ordering}
          onChange={(event) => {
            setOrdering(event.target.value);
            setOffset(0);
          }}
        >
          <option value="-created">Newest first</option>
          <option value="created">Oldest first</option>
          <option value="-updated">Recently updated</option>
        </select>

        {hasActiveFilters && (
          <button
            type="button"
            className="button secondary"
            style={{ padding: '0.4rem 0.75rem', fontSize: '0.85rem' }}
            onClick={resetFilters}
          >
            <RotateCcw size={14} style={{ marginRight: '4px' }} />
            Reset filters
          </button>
        )}
      </div>

      {orders.isFetching && !orders.isLoading && <Loading compact overlay />}

      {orders.isLoading ? (
        <Loading />
      ) : orders.error ? (
        <ErrorState error={orders.error} retry={() => orders.refetch()} />
      ) : (
        <>
          <MerchantOrderTable
            orders={orders.data?.results || []}
            storeId={store.id}
            focusOrderId={focusOrderId}
            isFiltered={hasActiveFilters}
            onResetFilters={resetFilters}
            onOrderDetailsClosed={clearOrderDeepLink}
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

function RefundDetailDialog({
  refund,
  store,
  onClose,
}: {
  refund: MerchantRefund;
  store: Store;
  onClose: () => void;
}) {
  const dialogRef = useDialogFocus(Boolean(refund), onClose);

  return (
    <div
      className="admin-dialog-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        ref={dialogRef}
        className="admin-detail-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="merchant-refund-detail-title"
      >
        <header className="admin-detail-header">
          <div className="admin-detail-heading">
            <span className="admin-detail-icon" aria-hidden="true">
              <RotateCcw size={22} />
            </span>
            <div>
              <span className="eyebrow green">Refund request</span>
              <h2 id="merchant-refund-detail-title">#{refund.id}</h2>
            </div>
          </div>
          <button
            type="button"
            className="icon-button no-print"
            aria-label="Close details"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </header>

        <div className="admin-detail-body">
          <div className="admin-detail-status">
            <span>Status</span>
            <Status value={refund.status} />
          </div>

          <dl className="admin-detail-grid">
            <div className="admin-detail-field">
              <dt>Order</dt>
              <dd>
                {refund.order ? (
                  <Link
                    href={`/merchant/orders?store=${store.id}&order=${refund.order}`}
                    className="text-link"
                    style={{ fontWeight: 600 }}
                  >
                    #{refund.order_reference || refund.order}
                  </Link>
                ) : (
                  <span>#{refund.order_reference || '—'}</span>
                )}
              </dd>
            </div>

            <div className="admin-detail-field">
              <dt>Customer</dt>
              <dd>
                <div>{refund.customer_email}</div>
                {refund.customer_name && (
                  <small className="muted">{refund.customer_name}</small>
                )}
              </dd>
            </div>

            <div className="admin-detail-field">
              <dt>Store refund amount</dt>
              <dd>
                <strong style={{ color: 'var(--green)', fontSize: '1.05rem' }}>
                  {money(refund.amount)}
                </strong>
                {refund.total_order_refund_amount &&
                  refund.total_order_refund_amount !== refund.amount && (
                    <small className="muted" style={{ display: 'block', fontSize: '0.8rem' }}>
                      (Total order refund: {money(refund.total_order_refund_amount)})
                    </small>
                  )}
              </dd>
            </div>

            <div className="admin-detail-field">
              <dt>Refund method</dt>
              <dd style={{ textTransform: 'capitalize' }}>
                {refund.refund_type.replaceAll('_', ' ')}
              </dd>
            </div>

            <div className="admin-detail-field">
              <dt>Requested</dt>
              <dd>{activityDate(refund.created)}</dd>
            </div>

            <div className="admin-detail-field">
              <dt>Processed</dt>
              <dd>
                {refund.processed_at ? activityDate(refund.processed_at) : 'Pending review'}
              </dd>
            </div>

            <div className="admin-detail-field" style={{ gridColumn: '1 / -1' }}>
              <dt>Customer reason</dt>
              <dd style={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>{refund.reason}</dd>
            </div>

            {refund.processing_reason && (
              <div className="admin-detail-field" style={{ gridColumn: '1 / -1' }}>
                <dt>Review decision note</dt>
                <dd style={{ whiteSpace: 'pre-wrap', color: 'var(--ink)' }}>
                  {refund.processing_reason}
                </dd>
              </div>
            )}
          </dl>

          <div style={{ marginTop: '1.5rem' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '0.75rem' }}>
              Refunded products ({refund.items.length})
            </h3>
            <div className="table-scroll">
              <table className="data-table" style={{ fontSize: '0.875rem' }}>
                <thead>
                  <tr>
                    <th>Item</th>
                    <th style={{ textAlign: 'center' }}>Qty</th>
                    <th style={{ textAlign: 'right' }}>Unit price</th>
                    <th style={{ textAlign: 'right' }}>Line total</th>
                  </tr>
                </thead>
                <tbody>
                  {refund.items.map((item, index) => (
                    <tr key={item.product ? `${item.product}-${index}` : index}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                          <div style={{ width: 40, height: 40, borderRadius: 4, overflow: 'hidden', flexShrink: 0 }}>
                            <ProductImage
                              src={normalizeImageUrl(item.image)}
                              alt={item.title}
                            />
                          </div>
                          <div>
                            {item.product ? (
                              <Link
                                href={`/merchant/products/${item.product}?store=${store.id}`}
                                className="text-link"
                                style={{ fontWeight: 500 }}
                              >
                                {item.title}
                              </Link>
                            ) : (
                              <span>{item.title}</span>
                            )}
                            {item.variant && Object.keys(item.variant).length > 0 && (
                              <div className="muted" style={{ fontSize: '0.8rem' }}>
                                {Object.entries(item.variant)
                                  .map(([k, v]) => `${k}: ${v}`)
                                  .join(', ')}
                              </div>
                            )}
                            {item.is_digital && (
                              <span className="badge" style={{ fontSize: '0.7rem', padding: '1px 5px' }}>
                                Digital
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td style={{ textAlign: 'center' }}>{item.quantity}</td>
                      <td style={{ textAlign: 'right' }}>{money(item.unit_price)}</td>
                      <td style={{ textAlign: 'right', fontWeight: 600 }}>
                        {money(item.line_total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <footer className="admin-detail-footer no-print">
          <button type="button" className="button secondary" onClick={() => window.print()}>
            <Printer size={16} />
            Print details
          </button>
          <button type="button" className="button" onClick={onClose}>
            Done
          </button>
        </footer>
      </section>
    </div>
  );
}

function MerchantRefunds({
  store,
  stores = [],
  onSelectStore,
}: {
  store: Store;
  stores?: Store[];
  onSelectStore?: (storeId: number) => void;
}) {
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search);
  const [status, setStatus] = useState('');
  const [refundType, setRefundType] = useState('');
  const [timeframe, setTimeframe] = useState('');
  const [ordering, setOrdering] = useState('-created');
  const [offset, setOffset] = useState(0);
  const [selectedRefund, setSelectedRefund] = useState<MerchantRefund | null>(null);

  const router = useRouter();
  const searchParams = useSearchParams();
  const focusRefundId = searchParams.get('refund') || '';

  const hasActiveFilters = Boolean(
    search.trim() || status || refundType || timeframe || ordering !== '-created'
  );

  const queryParams = new URLSearchParams({
    limit: '20',
    offset: String(offset),
  });
  if (status) queryParams.set('status', status);
  if (refundType) queryParams.set('refund_type', refundType);
  if (debouncedSearch.trim()) queryParams.set('search', debouncedSearch.trim());
  if (timeframe) queryParams.set('days', timeframe);
  if (ordering && ordering !== '-created') queryParams.set('ordering', ordering);
  if (/^\d+$/.test(focusRefundId)) queryParams.set('refund_id', focusRefundId);

  const refunds = useQuery({
    queryKey: [
      'merchant-refunds',
      store.id,
      status,
      refundType,
      debouncedSearch.trim(),
      timeframe,
      ordering,
      offset,
      focusRefundId,
    ],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[1] === store.id && previousQuery.queryKey.at(-1) === focusRefundId
        ? previousData
        : undefined,
    queryFn: () =>
      api<Page<MerchantRefund>>(
        `stores/${store.id}/refunds?${queryParams.toString()}`
      ),
  });

  useEffect(() => {
    if (!focusRefundId || !refunds.data?.results) return;
    const target = refunds.data.results.find((r) => String(r.id) === focusRefundId);
    if (target) {
      setSelectedRefund(target);
    }
  }, [focusRefundId, refunds.data?.results]);

  function resetFilters() {
    setSearch('');
    setStatus('');
    setRefundType('');
    setTimeframe('');
    setOrdering('-created');
    setOffset(0);
  }

  function handleCloseModal() {
    setSelectedRefund(null);
    if (!focusRefundId) return;
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete('refund');
    const query = nextParams.toString();
    router.replace(`/merchant/refunds${query ? `?${query}` : ''}`, { scroll: false });
  }

  return (
    <>
      <div className="merchant-heading">
        <div>
          <h1>Product refunds</h1>
          <p>Review customer returns, refunded products, and settlement status for your store.</p>
        </div>
        {refunds.data?.count !== undefined && (
          <span className="badge" style={{ fontSize: '0.85rem', padding: '0.35rem 0.75rem' }}>
            {refunds.data.count} {refunds.data.count === 1 ? 'refund' : 'refunds'}
          </span>
        )}
      </div>

      <div
        className="merchant-toolbar"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '0.75rem',
          marginBottom: '1.25rem',
        }}
      >
        <div className="search-box" style={{ flex: '1 1 260px', minWidth: '220px' }}>
          <Search size={16} />
          <input
            aria-label="Search refunds"
            placeholder="Search by refund #, order, customer, product, reason…"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
          />
          {search && (
            <button
              type="button"
              className="icon-button"
              aria-label="Clear search"
              onClick={() => {
                setSearch('');
                setOffset(0);
              }}
            >
              <X size={15} />
            </button>
          )}
        </div>

        {stores.length > 1 && (
          <select
            aria-label="Filter refunds by store"
            value={store.id}
            onChange={(event) => {
              onSelectStore?.(Number(event.target.value));
              setOffset(0);
            }}
          >
            {stores.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        )}

        <select
          aria-label="Filter refunds by status"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setOffset(0);
          }}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="declined">Declined</option>
          <option value="failed">Failed</option>
        </select>

        <select
          aria-label="Filter refunds by method"
          value={refundType}
          onChange={(event) => {
            setRefundType(event.target.value);
            setOffset(0);
          }}
        >
          <option value="">All methods</option>
          <option value="store_credit">Store Credit</option>
          <option value="original_payment">Original Payment</option>
        </select>

        <select
          aria-label="Filter refunds by timeframe"
          value={timeframe}
          onChange={(event) => {
            setTimeframe(event.target.value);
            setOffset(0);
          }}
        >
          <option value="">All time</option>
          <option value="7">Last 7 days</option>
          <option value="30">Last 30 days</option>
          <option value="90">Last 90 days</option>
        </select>

        <select
          aria-label="Sort refunds"
          value={ordering}
          onChange={(event) => {
            setOrdering(event.target.value);
            setOffset(0);
          }}
        >
          <option value="-created">Newest first</option>
          <option value="created">Oldest first</option>
          <option value="-amount">Highest amount</option>
          <option value="amount">Lowest amount</option>
        </select>

        {hasActiveFilters && (
          <button
            type="button"
            className="button secondary"
            style={{ padding: '0.4rem 0.75rem', fontSize: '0.85rem' }}
            onClick={resetFilters}
          >
            <RotateCcw size={14} style={{ marginRight: '4px' }} />
            Reset filters
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
          title={hasActiveFilters ? 'No matching refunds found' : 'No refund requests'}
          text={
            hasActiveFilters
              ? 'No refund requests matched your current search or filters.'
              : 'No customer refund requests currently exist for your store.'
          }
          label={hasActiveFilters ? 'Reset filters' : undefined}
          onAction={hasActiveFilters ? resetFilters : undefined}
        />
      ) : (
        <>
          <div className="table-scroll">
            <table className="data-table" aria-label="Store product refunds">
              <thead>
                <tr>
                  <th>Refund #</th>
                  <th>Product</th>
                  <th>Order</th>
                  <th>Customer</th>
                  <th>Amount</th>
                  <th>Method</th>
                  <th>Status</th>
                  <th>Reason</th>
                  <th>Date</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {refunds.data.results.map((refund) => {
                  const primaryItem = refund.items[0];
                  const extraCount = refund.items.length - 1;

                  return (
                    <tr key={refund.id}>
                      <td>
                        <button
                          type="button"
                          className="text-link"
                          aria-label={`View details for refund ${refund.id}`}
                          onClick={() => setSelectedRefund(refund)}
                          style={{ fontWeight: 600 }}
                        >
                          #{refund.id}
                        </button>
                      </td>
                      <td>
                        {primaryItem ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                            <div style={{ width: 32, height: 32, borderRadius: 4, overflow: 'hidden', flexShrink: 0 }}>
                              <ProductImage
                                src={normalizeImageUrl(primaryItem.image)}
                                alt={primaryItem.title}
                              />
                            </div>
                            <div style={{ minWidth: 0 }}>
                              <span
                                title={primaryItem.title}
                                style={{
                                  display: 'block',
                                  maxWidth: 160,
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                  fontWeight: 500,
                                }}
                              >
                                {primaryItem.title}
                              </span>
                              {extraCount > 0 && (
                                <span className="muted" style={{ fontSize: '0.75rem' }}>
                                  +{extraCount} more {extraCount === 1 ? 'item' : 'items'}
                                </span>
                              )}
                            </div>
                          </div>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td>
                        {refund.order ? (
                          <Link
                            href={`/merchant/orders?store=${store.id}&order=${refund.order}`}
                            className="text-link"
                          >
                            #{refund.order_reference || refund.order}
                          </Link>
                        ) : (
                          <span>#{refund.order_reference || '—'}</span>
                        )}
                      </td>
                      <td>
                        <div style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          <span>{refund.customer_email}</span>
                          {refund.customer_name && (
                            <small className="muted" style={{ display: 'block', fontSize: '0.75rem' }}>
                              {refund.customer_name}
                            </small>
                          )}
                        </div>
                      </td>
                      <td>
                        <strong>{money(refund.amount)}</strong>
                      </td>
                      <td>
                        <span style={{ textTransform: 'capitalize' }}>
                          {refund.refund_type.replaceAll('_', ' ')}
                        </span>
                      </td>
                      <td>
                        <Status value={refund.status} />
                      </td>
                      <td>
                        <span
                          title={refund.reason}
                          style={{
                            maxWidth: 150,
                            display: 'inline-block',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {refund.reason}
                        </span>
                      </td>
                      <td>
                        <DateStamp value={refund.created} dateOnly />
                      </td>
                      <td>
                        <button
                          type="button"
                          className="button secondary compact"
                          onClick={() => setSelectedRefund(refund)}
                        >
                          Details
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <Pagination
            page={Math.floor(offset / 20) + 1}
            totalPages={Math.ceil((refunds.data?.count || 0) / 20)}
            onChange={(page) => setOffset((page - 1) * 20)}
          />
        </>
      )}

      {selectedRefund && (
        <RefundDetailDialog
          refund={selectedRefund}
          store={store}
          onClose={handleCloseModal}
        />
      )}
    </>
  );
}

function MerchantPayments({ store }: { store: Store }) {
  const { user, notify } = useShop();
  const client = useQueryClient();
  const [requestingPayout, setRequestingPayout] = useState(false);
  const [payoutAmount, setPayoutAmount] = useState('');
  const [bankAccountId, setBankAccountId] = useState<number | null>(null);
  const [notes, setNotes] = useState('');
  const [payoutBusy, setPayoutBusy] = useState(false);
  const [activeTab, setActiveTab] = useState<'requests' | 'ledger'>('requests');
  const [paymentDetail, setPaymentDetail] = useState<MerchantPaymentDetail | null>(null);
  const clearPayoutDetail = useNotificationDetail<StorePayout>('payout', 'stores/wallet/payouts?paginated=1', showPayoutDetails);
  const clearLedgerDetail = useNotificationDetail<StoreEarningsLedger>('ledger', `stores/wallet/ledger?store_id=${store.id}`, showLedgerDetails);

  function closePaymentDetail(): void {
    setPaymentDetail(null);
    clearPayoutDetail();
    clearLedgerDetail();
  }

  const payoutFilters = useCollectionFilters();
  const ledgerFilters = useCollectionFilters();
  const filters = activeTab === 'requests' ? payoutFilters : ledgerFilters;
  const paymentDetailDialogRef = useDialogFocus(Boolean(paymentDetail), () => closePaymentDetail());

  const stats = useQuery({
    queryKey: ['dashboard', store.id, '30'],
    queryFn: () => api<Dashboard>(`stores/${store.id}/dashboard?days=30&time_zone=${encodeURIComponent(browserTimeZone())}`),
  });

  const payouts = useQuery({
    queryKey: ['merchant-payouts', store.id, payoutFilters.query],
    queryFn: () => api<Page<StorePayout>>(`stores/${store.id}/payouts?paginated=1&${payoutFilters.query}`),
  });

  const ledger = useQuery({
    queryKey: ['merchant-ledger', store.id, ledgerFilters.query],
    queryFn: () => api<{ count: number; results: StoreEarningsLedger[] }>(`stores/wallet/ledger?store_id=${store.id}&${ledgerFilters.query}`),
  });

  const wallet = stats.data?.wallet;
  const isOfficial = Boolean(store.is_official);
  const canWithdraw = !user?.is_staff && !user?.is_superuser && !user?.is_business_admin;
  const availableBal = Number(wallet?.withdrawable_balance ?? wallet?.available_balance ?? '0');

  function showPayoutDetails(payout: StorePayout): void {
    const rows: [string, string][] = [
      ['Reference', payout.reference],
      ['Store', payout.store_name || store.name],
      ['Amount', money(payout.amount)],
      ['Status', payout.status],
      ['Method', payout.payout_method.replaceAll('_', ' ')],
      ['Requested', activityDate(payout.created)],
    ];
    if (payout.processed_at) rows.push(['Processed', activityDate(payout.processed_at)]);
    if (payout.notes?.trim()) rows.push(['Notes', payout.notes.trim()]);
    for (const [key, value] of Object.entries(payout.account_details || {})) {
      if (value === null || value === undefined || !String(value).trim()) continue;
      const text = String(value);
      const label = key.replaceAll('_', ' ');
      const masked = /last_?4$/i.test(key)
        ? `********${text.slice(-2)}`
        : /account_number|routing_number|iban/i.test(key)
          ? `********${text.replace(/\s/g, '').slice(-4)}`
          : text;
      rows.push([label, masked]);
    }
    setPaymentDetail({ title: `Payout ${payout.reference}`, category: 'Payout', rows });
  }

  function showLedgerDetails(entry: StoreEarningsLedger): void {
    const rows: [string, string][] = [
      ['Entry type', entry.entry_type],
      ['Description', entry.description],
      ['Reference', entry.reference],
      ['Order ID', entry.order ? `#${entry.order}` : ''],
      ['Gross amount', money(entry.gross_amount)],
      ['Fee amount', money(entry.fee_amount)],
      ['Net amount', money(entry.net_amount)],
      ['Status', entry.status],
      ['Available on', entry.available_at ? activityDate(entry.available_at) : ''],
      ['Cleared on', entry.cleared_at ? activityDate(entry.cleared_at) : ''],
      ['Created', activityDate(entry.created)],
    ];
    setPaymentDetail({ title: `Ledger entry ${entry.reference || `#${entry.id}`}`, category: 'Store earnings', rows });
  }

  async function submitPayout(event: FormEvent) {
    event.preventDefault();
    setPayoutBusy(true);
    try {
      await api(`stores/${store.id}/payouts`, 'POST', {
        amount: payoutAmount,
        payout_method: 'bank_transfer',
        bank_account_id: bankAccountId,
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
            value: money(isOfficial ? wallet?.available_balance || '0.00' : availableBal),
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
        <section className="analytics-panel treasury-withdrawal-panel merchant-payout-panel">
          <div className="treasury-withdrawal-heading">
            <div>
              <h2>Request store payout</h2>
              <p>Choose a saved bank account. Requests are reviewed before payment.</p>
            </div>
            <div className="treasury-available-balance">
              <span>Available to withdraw</span>
              <strong>{money(availableBal)}</strong>
            </div>
          </div>
          <form className="treasury-withdrawal-form" onSubmit={submitPayout}>
            <div className="treasury-withdrawal-fields">
              <Field label="Amount (USD)">
                <div className="merchant-payout-amount">
                  <input
                    type="number"
                    min="5.00"
                    max={availableBal}
                    step="0.01"
                    required
                    value={payoutAmount}
                    onChange={event => setPayoutAmount(event.target.value)}
                    placeholder="0.00"
                  />
                  <button
                    type="button"
                    className="button secondary compact"
                    disabled={payoutBusy}
                    onClick={() => setPayoutAmount(availableBal.toFixed(2))}
                  >
                    Max
                  </button>
                </div>
              </Field>
              <Field label="Note (optional)">
                <input
                  value={notes}
                  onChange={event => setNotes(event.target.value)}
                  placeholder="Add a note for the payout reviewer…"
                />
              </Field>
            </div>
            <div className="treasury-bank-picker">
              <BankAccounts compact pickerOnly selectedId={bankAccountId} onSelect={setBankAccountId} />
            </div>
            <div className="form-actions merchant-payout-actions">
              <button className="button compact" disabled={payoutBusy || availableBal < 5 || !bankAccountId}>
                {payoutBusy ? 'Submitting…' : 'Request withdrawal'}
              </button>
              <button
                type="button"
                className="button secondary compact"
                disabled={payoutBusy}
                onClick={() => setRequestingPayout(false)}
              >
                Cancel
              </button>
            </div>
          </form>
        </section>
      )}

      <div style={{ marginTop: 32 }}>
        <div className="merchant-toolbar" style={{ marginBottom: 16 }}>
          <div className="tabs">
            <button
              className={activeTab === 'requests' ? 'active' : ''}
              onClick={() => setActiveTab('requests')}
            >
              Payout Requests ({payouts.data?.count || 0})
            </button>
            <button
              className={activeTab === 'ledger' ? 'active' : ''}
              onClick={() => setActiveTab('ledger')}
            >
              Store Earnings Ledger ({ledger.data?.count || 0})
            </button>
          </div>
        </div>
        <CollectionFilters
          filters={filters}
          label={activeTab === 'requests' ? 'payout requests' : 'earnings ledger'}
          fields={[
            {
              key: 'status', label: 'Status',
              options: (activeTab === 'requests'
                ? ['pending', 'completed', 'rejected']
                : ['pending', 'available', 'completed', 'reversed'])
                .map(value => ({ value, label: value.replaceAll('_', ' ') })),
            },
            activeTab === 'requests' ? {
              key: 'payout_method', label: 'Method',
              options: [
                { value: 'bank_transfer', label: 'Bank transfer' },
                { value: 'stripe_connect', label: 'Stripe Connect' },
              ],
            } : {
              key: 'entry_type', label: 'Entry type',
              options: ['sale', 'payout', 'fee', 'refund'].map(value => ({ value, label: value })),
            },
            ...financialFields,
          ]}
        />
        {typeof (activeTab === 'requests' ? payouts.data?.count : ledger.data?.count) === 'number' && (
          <CollectionCount count={(activeTab === 'requests' ? payouts.data?.count : ledger.data?.count) || 0} />
        )}

        {activeTab === 'requests' ? (
          payouts.isLoading ? (
            <Loading />
          ) : payouts.error ? (
            <ErrorState error={payouts.error} retry={() => payouts.refetch()} />
          ) : !payouts.data?.results.length ? (
            <div className="empty-state">
              <WalletCards size={36} />
              <h2>{payoutFilters.active ? 'No payouts match your filters' : 'No payout requests yet'}</h2>
              <p>
                {payoutFilters.active ? 'Reset filters to see all payout requests.' : isOfficial
                  ? 'Official company store earnings are consolidated into the Platform Treasury. Payouts and transfers are audited at /admin/commission.'
                  : 'When you request withdrawals for cleared sales, they will be tracked here with their status and references.'}
              </p>
              {!payoutFilters.active && !isOfficial && availableBal >= 5 && canWithdraw && (
                <button className="button" onClick={() => setRequestingPayout(true)}>
                  Request your first payout
                </button>
              )}
            </div>
          ) : (
            <>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Created</th>
                      <th>Reference</th>
                      <th>Amount</th>
                      <th>Method</th>
                      <th>Status</th>
                      <th>Processed</th>
                      <th>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payouts.data.results.map(p => (
                      <tr key={p.id}>
                        <td><DateStamp value={p.created} dateOnly /></td>
                        <td>
                          <button
                            type="button"
                            className="text-link order-reference-link"
                            aria-label={`View payout ${p.reference} details`}
                            onClick={() => showPayoutDetails(p)}
                          >
                            {p.reference}
                          </button>
                        </td>
                        <td><strong style={{ color: 'var(--ink)' }}>{money(p.amount)}</strong></td>
                        <td style={{ textTransform: 'capitalize' }}>{p.payout_method.replace('_', ' ')}</td>
                        <td><Status value={p.status} /></td>
                        <td className="muted">{p.processed_at ? <DateStamp value={p.processed_at} dateOnly /> : 'Pending review'}</td>
                        <td className="muted">{p.notes || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <CollectionPagination filters={filters} count={payouts.data?.count || 0} />
            </>
          )
        ) : (
          ledger.isLoading ? (
            <Loading />
          ) : ledger.error ? (
            <ErrorState error={ledger.error} retry={() => ledger.refetch()} />
          ) : !ledger.data?.results?.length ? (
            <div className="empty-state">
              <ShoppingBag size={36} />
              <h2>{ledgerFilters.active ? 'No ledger entries match your filters' : 'No ledger entries yet'}</h2>
              <p>{ledgerFilters.active ? 'Reset filters to see all entries.' : `As orders are placed for ${store.name}, earnings and fees appear here.`}</p>
            </div>
          ) : (
            <>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Created</th>
                      <th>Entry Type</th>
                      <th>Description</th>
                      <th>Gross</th>
                      <th>Fee</th>
                      <th>Net Amount</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ledger.data.results.map(entry => (
                      <tr key={entry.id}>
                        <td><DateStamp value={entry.created} dateOnly /></td>
                        <td>
                          <span className={`status status-${entry.entry_type}`} style={{ textTransform: 'uppercase', fontSize: 8 }}>
                            {entry.entry_type}
                          </span>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="text-link order-reference-link"
                            aria-label={`View ledger entry ${entry.reference || entry.id} details`}
                            onClick={() => showLedgerDetails(entry)}
                          >
                            <strong>{entry.description}</strong>
                            {entry.reference && <small style={{ display: 'block', color: 'var(--muted)', fontSize: 9 }}>Ref: {entry.reference}</small>}
                          </button>
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
              <CollectionPagination filters={filters} count={ledger.data?.count || 0} />
            </>
          )
        )}
      </div>

      {paymentDetail && (
        <div
          className="dialog-backdrop admin-detail-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closePaymentDetail();
          }}
        >
          <section
            ref={paymentDetailDialogRef}
            className="admin-detail-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="merchant-payment-detail-title"
          >
            <header className="admin-detail-header">
              <div className="admin-detail-heading">
                <span className="admin-detail-icon" aria-hidden="true"><FileText size={22} /></span>
                <div>
                  <span className="eyebrow green">{paymentDetail.category} details</span>
                  <h2 id="merchant-payment-detail-title">{paymentDetail.title}</h2>
                </div>
              </div>
              <button
                type="button"
                className="icon-button no-print"
                aria-label="Close payment details"
                onClick={() => closePaymentDetail()}
              >
                <X size={20} />
              </button>
            </header>
            <div className="admin-detail-body">
              <div className="admin-detail-status">
                <span>Current status</span>
                <Status value={paymentDetail.rows.find(([label]) => label === 'Status')?.[1]?.toLowerCase() || 'unknown'} />
              </div>
              <dl className="admin-detail-grid">
                {paymentDetail.rows
                  .filter(([label, value]) => label !== 'Status' && value.trim())
                  .map(([label, value]) => (
                    <div className={`admin-detail-field${['Notes'].includes(label) ? ' admin-detail-field-wide' : ''}`} key={label}>
                      <dt>{label}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
              </dl>
            </div>
            <footer className="admin-detail-footer no-print">
              <button type="button" className="button secondary" onClick={() => window.print()}>
                <Printer size={16} />
                Print details
              </button>
              <button type="button" className="button" onClick={() => closePaymentDetail()}>Done</button>
            </footer>
          </section>
        </div>
      )}

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
  const filters = useCollectionFilters();
  const tab: string = filters.values.state || 'all';
  const search: string = filters.search;
  const offset: number = filters.offset;
  const setOffset = filters.setOffset;
  const [isLive, setIsLive] = useState(true);
  const [busyAction, setBusyAction] = useState<number | null>(null);

  const queryParams = new URLSearchParams({ ...Object.fromEntries(new URLSearchParams(filters.query)),
    store: String(store.id),
    limit: '15',
    offset: String(offset),
  });

  if (tab === 'read') queryParams.set('state', 'read');
  if (tab === 'archived') queryParams.delete('state');
  if (tab === 'unread') queryParams.set('state', 'unread');
  else if (tab === 'orders') queryParams.set('category', 'order');
  else if (tab === 'payouts') queryParams.set('category', 'payout');
  else if (tab === 'archived') queryParams.set('include_archived', 'true');



  const endpoint = tab === 'archived'
    ? `notifications/archived/?${queryParams.toString()}`
    : `notifications?${queryParams.toString()}`;

  const notifications = useQuery({
    queryKey: ['merchant-notifications', store.id, filters.query, offset],
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[1] === store.id ? previousData : undefined,
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

      <CollectionFilters filters={filters} label="store notifications" fields={[
        { key: 'state', label: 'State', options: [{ value: 'unread', label: 'Unread' }, { value: 'read', label: 'Read' }, { value: 'archived', label: 'Archived' }] },
        { key: 'category', label: 'Category', options: ['order', 'refund', 'payout', 'wallet', 'store', 'affiliates', 'account', 'general'].map(value => ({ value, label: value })) },
      ]} />
      {notifications.isFetching && !notifications.isLoading && <Loading compact overlay />}

      {notifications.isLoading ? (
        <Loading />
      ) : notifications.error ? (
        <ErrorState error={notifications.error} retry={() => notifications.refetch()} />
      ) : !items.length ? (
        <div className="empty-state">
          <Bell size={36} />
          <h2>No notifications found</h2>
          <p>
            {filters.active
              ? 'No notifications match your filters. Reset filters to see all notifications.'
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
                    <span className="merchant-notif-time" title={activityDate(item.timestamp)}>
                      {formatRelativeTime(item.timestamp)}
                    </span>
                  </div>
                  <h3 className="merchant-notif-title">{item.verb}</h3>
                  <p className="merchant-notif-desc">
                    {item.description || 'No additional details provided for this event.'}
                  </p>
                  <div className="merchant-notif-footer">
                    {isOrder && (
                      <Link
                        href={Number.isSafeInteger(Number(item.data?.order_id)) && Number(item.data?.order_id) > 0
                          ? `/merchant/orders?store=${store.id}&order=${Number(item.data?.order_id)}`
                          : '/merchant/orders'}
                        className="text-link"
                        style={{ fontSize: 11 }}
                      >
                        {Number.isSafeInteger(Number(item.data?.order_id)) && Number(item.data?.order_id) > 0
                          ? 'Go to order'
                          : 'Go to Orders'} <ArrowRight size={13} />
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


function MerchantTeam({ store }: { store: Store }) {
  const { notify } = useShop();
  const client = useQueryClient();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'store_admin' | 'catalog_manager' | 'fulfillment_specialist'>('catalog_manager');
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [resendingId, setResendingId] = useState<number | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<StoreTeamMember | null>(null);
  const [deleting, setDeleting] = useState(false);

  const inviteDialogRef = useDialogFocus(inviteOpen, () => setInviteOpen(false));
  const deleteDialogRef = useDialogFocus(Boolean(deleteTarget), () => setDeleteTarget(null));

  const filters = useCollectionFilters();
  const team = useQuery({
    queryKey: ['store-team', store.id, filters.query],
    queryFn: () => api<Page<StoreTeamMember>>(`stores/${store.id}/team?paginated=1&${filters.query}`),
  });

  const currentUserRole: StoreTeamRole = store.user_role || 'owner';
  const isOwner = currentUserRole === 'owner';

  async function handleInvite(e: FormEvent) {
    e.preventDefault();
    setInviteError(null);
    setInviting(true);
    try {
      await api<StoreTeamMember>(`stores/${store.id}/team`, 'POST', {
        email: inviteEmail.trim(),
        role: inviteRole,
      });
      await client.invalidateQueries({ queryKey: ['store-team', store.id] });
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

  async function handleResendInvite(member: StoreTeamMember) {
    setResendingId(member.id);
    try {
      await api<{ detail: string }>(`stores/${store.id}/team/${member.id}/resend`, 'POST');
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
      await api<StoreTeamMember>(`stores/${store.id}/team/${memberId}`, 'PATCH', { role: newRole });
      await client.invalidateQueries({ queryKey: ['store-team', store.id] });
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
      await api(`stores/${store.id}/team/${deleteTarget.id}`, 'DELETE');
      await client.invalidateQueries({ queryKey: ['store-team', store.id] });
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
            padding: '4px 10px',
            borderRadius: 999,
            fontSize: '0.8rem',
            fontWeight: 600,
            background: 'rgba(245, 158, 11, 0.15)',
            color: '#d97706',
            border: '1px solid rgba(245, 158, 11, 0.35)',
          }}
        >
          <Shield size={13} />
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
            padding: '4px 10px',
            borderRadius: 999,
            fontSize: '0.8rem',
            fontWeight: 600,
            background: 'rgba(99, 102, 241, 0.15)',
            color: '#6366f1',
            border: '1px solid rgba(99, 102, 241, 0.35)',
          }}
        >
          <ShieldCheck size={13} />
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
            padding: '4px 10px',
            borderRadius: 999,
            fontSize: '0.8rem',
            fontWeight: 600,
            background: 'rgba(14, 165, 233, 0.15)',
            color: '#0284c7',
            border: '1px solid rgba(14, 165, 233, 0.35)',
          }}
        >
          <Package size={13} />
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
          padding: '4px 10px',
          borderRadius: 999,
          fontSize: '0.8rem',
          fontWeight: 600,
          background: 'rgba(16, 185, 129, 0.15)',
          color: '#059669',
          border: '1px solid rgba(16, 185, 129, 0.35)',
        }}
      >
        <Truck size={13} />
        Fulfillment Specialist
      </span>
    );
  }

  return (
    <>
      <div className="merchant-heading">
        <div>
          <h1>Store Team & Staff Roles</h1>
          <p>Assign granular staff permissions to manage products, orders, and tracking without sharing passwords.</p>
        </div>
        <button className="button" onClick={() => setInviteOpen(true)}>
          <UserPlus size={16} />
          Invite team member
        </button>
      </div>

      <div
        className="card"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '1rem',
          marginBottom: '1.5rem',
          padding: '1.25rem',
          background: 'var(--soft)',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <strong style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#6366f1' }}>
            <ShieldCheck size={16} /> Store Admin
          </strong>
          <span style={{ fontSize: '0.82rem', color: 'var(--muted)', lineHeight: 1.4 }}>
            Full operational access to products, orders, returns, and team invites. Cannot transfer ownership or delete store.
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <strong style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#0284c7' }}>
            <Package size={16} /> Catalog Manager
          </strong>
          <span style={{ fontSize: '0.82rem', color: 'var(--muted)', lineHeight: 1.4 }}>
            Can create, edit, and organize products, manage variants, and update stock. No access to orders or financials.
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <strong style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#059669' }}>
            <Truck size={16} /> Fulfillment Specialist
          </strong>
          <span style={{ fontSize: '0.82rem', color: 'var(--muted)', lineHeight: 1.4 }}>
            Can view orders, print packing slips, update tracking, and process refunds. No access to catalog or financials.
          </span>
        </div>
      </div>

      <CollectionFilters
        filters={filters}
        label="team members"
        fields={[
          { key: 'role', label: 'Role', options: [
            { value: 'store_admin', label: 'Store administrator' },
            { value: 'catalog_manager', label: 'Catalog manager' },
            { value: 'fulfillment_specialist', label: 'Fulfillment specialist' },
          ] },
          { key: 'start_date', label: 'Joined from', type: 'date' },
          { key: 'end_date', label: 'Joined until', type: 'date' },
        ]}
      />
      {team.isLoading ? (
        <Loading />
      ) : team.error ? (
        <ErrorState error={team.error} retry={() => team.refetch()} />
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="table-scroll">
            <table className="table" style={{ margin: 0 }}>
              <thead>
                <tr>
                  <th>Team Member</th>
                  <th>Role</th>
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
                          style={{ width: 36, height: 36, borderRadius: '50%', objectFit: 'cover' }}
                          sizes="36px"
                          width={72}
                          height={72}
                        />
                      ) : (
                        <div
                          style={{
                            width: 36,
                            height: 36,
                            borderRadius: '50%',
                            background: 'rgba(245, 158, 11, 0.15)',
                            color: '#d97706',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontWeight: 700,
                            fontSize: '0.88rem',
                            border: '1px solid rgba(245, 158, 11, 0.3)',
                          }}
                        >
                          <Shield size={18} />
                        </div>
                      )}
                      <div>
                        <strong>{store.owner_name || 'Primary Store Owner'}</strong>
                        <div style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
                          {store.owner_email || 'Full ownership & financial controls'}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td>{getRoleBadge('owner')}</td>
                  <td>—</td>
                  <td>Primary Owner</td>
                  <td style={{ textAlign: 'right', fontSize: '0.8rem', color: 'var(--muted)' }}>
                    Non-transferable
                  </td>
                </tr>

                {(team.data?.results || []).map((member) => {
                  const isPending = member.status === 'pending';
                  return (
                    <tr key={member.id}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          {member.avatar_url ? (
                            <ResponsiveMediaImage
                              src={member.avatar_url}
                              alt={member.first_name || member.email}
                              style={{ width: 36, height: 36, borderRadius: '50%', objectFit: 'cover' }}
                              sizes="36px"
                              width={72}
                              height={72}
                            />
                          ) : (
                            <div
                              style={{
                                width: 36,
                                height: 36,
                                borderRadius: '50%',
                                background: isPending ? 'rgba(245, 158, 11, 0.15)' : 'var(--soft)',
                                color: isPending ? 'var(--amber, #d97706)' : 'var(--ink)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontWeight: 700,
                                fontSize: '0.85rem',
                                border: isPending ? '1px solid rgba(245, 158, 11, 0.35)' : '1px solid var(--line)',
                              }}
                            >
                              {isPending ? (
                                <Mail size={16} />
                              ) : (
                                (member.first_name?.[0] || member.email[0]).toUpperCase()
                              )}
                            </div>
                          )}
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
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
                                    gap: 4,
                                    padding: '2px 8px',
                                    borderRadius: 999,
                                    fontSize: '0.72rem',
                                    fontWeight: 600,
                                    background: 'rgba(245, 158, 11, 0.15)',
                                    color: 'var(--amber, #d97706)',
                                    border: '1px solid rgba(245, 158, 11, 0.35)',
                                  }}
                                >
                                  <Clock size={11} />
                                  Pending Registration
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
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                          {isPending && (
                            <button
                              type="button"
                              className="button secondary"
                              style={{
                                fontSize: '0.75rem',
                                padding: '0.25rem 0.55rem',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 4,
                              }}
                              title={`Resend invitation to ${member.email}`}
                              disabled={resendingId === member.id}
                              onClick={() => handleResendInvite(member)}
                            >
                              <Mail size={12} />
                              {resendingId === member.id ? 'Resending...' : 'Resend Invite'}
                            </button>
                          )}
                          {(isOwner || (currentUserRole === 'store_admin' && member.role !== 'store_admin')) && (
                            <select
                              aria-label={`Change role for ${member.email}`}
                              value={member.role}
                              onChange={(e) =>
                                handleRoleChange(
                                  member.id,
                                  e.target.value as 'store_admin' | 'catalog_manager' | 'fulfillment_specialist'
                                )
                              }
                              style={{
                                fontSize: '0.78rem',
                                padding: '0.3rem 0.5rem',
                                borderRadius: 6,
                                border: '1px solid var(--line)',
                                background: 'var(--paper)',
                                color: 'var(--ink)',
                              }}
                            >
                              {isOwner && <option value="store_admin">Store Admin</option>}
                              <option value="catalog_manager">Catalog Manager</option>
                              <option value="fulfillment_specialist">Fulfillment Specialist</option>
                            </select>
                          )}
                          {(isOwner || (currentUserRole === 'store_admin' && member.role !== 'store_admin')) && (
                            <button
                              className="icon-button"
                              title={isPending ? `Revoke invitation for ${member.email}` : `Remove ${member.email}`}
                              aria-label={isPending ? `Revoke invitation for ${member.email}` : `Remove ${member.email}`}
                              style={{ color: 'var(--red)' }}
                              onClick={() => setDeleteTarget(member)}
                            >
                              <Trash2 size={15} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}

                {(team.data?.results || []).length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--muted)' }}>
                      {filters.active ? 'No team members match these filters. Reset filters to see everyone.' : 'No delegated team members yet. Invite a team member to add staff.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <CollectionPagination filters={filters} count={team.data?.count || 0} />

      {/* Invite Member Dialog */}
      {inviteOpen && (
        <div className="dialog-backdrop">
          <section
            ref={inviteDialogRef}
            className="admin-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="invite-title"
          >
            <div className="admin-dialog-head">
              <div>
                <span className="eyebrow green">STORE TEAM INVITATION</span>
                <h2 id="invite-title">Invite Team Member</h2>
              </div>
              <button
                className="icon-button"
                aria-label="Close"
                onClick={() => setInviteOpen(false)}
              >
                <X size={19} />
              </button>
            </div>

            <form className="form-stack" onSubmit={handleInvite}>
              <Field label="User Account Email">
                <input
                  type="email"
                  required
                  placeholder="colleague@example.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                />
                <span style={{ fontSize: '0.78rem', color: 'var(--muted)', marginTop: 4, display: 'block' }}>
                  If they already have an account, they&apos;ll be added immediately. Otherwise, an invitation email with a signup link will be sent.
                </span>
              </Field>

              <Field label="Assigned Role">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {isOwner && (
                    <label
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 10,
                        padding: '10px 14px',
                        borderRadius: 8,
                        border: '1px solid var(--line)',
                        background: inviteRole === 'store_admin' ? 'rgba(99, 102, 241, 0.08)' : 'var(--paper)',
                        cursor: 'pointer',
                      }}
                    >
                      <input
                        type="radio"
                        name="role"
                        value="store_admin"
                        checked={inviteRole === 'store_admin'}
                        onChange={() => setInviteRole('store_admin')}
                        style={{ marginTop: 3 }}
                      />
                      <div>
                        <strong style={{ display: 'block', fontSize: '0.88rem' }}>Store Admin</strong>
                        <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
                          Full operational access across catalog, orders, and team members. Cannot transfer ownership.
                        </span>
                      </div>
                    </label>
                  )}

                  <label
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 10,
                      padding: '10px 14px',
                      borderRadius: 8,
                      border: '1px solid var(--line)',
                      background: inviteRole === 'catalog_manager' ? 'rgba(14, 165, 233, 0.08)' : 'var(--paper)',
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="radio"
                      name="role"
                      value="catalog_manager"
                      checked={inviteRole === 'catalog_manager'}
                      onChange={() => setInviteRole('catalog_manager')}
                      style={{ marginTop: 3 }}
                    />
                    <div>
                      <strong style={{ display: 'block', fontSize: '0.88rem' }}>Catalog Manager</strong>
                      <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
                        Can create and edit products, manage variants, and manage inventory. No access to orders or financials.
                      </span>
                    </div>
                  </label>

                  <label
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 10,
                      padding: '10px 14px',
                      borderRadius: 8,
                      border: '1px solid var(--line)',
                      background: inviteRole === 'fulfillment_specialist' ? 'rgba(16, 185, 129, 0.08)' : 'var(--paper)',
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="radio"
                      name="role"
                      value="fulfillment_specialist"
                      checked={inviteRole === 'fulfillment_specialist'}
                      onChange={() => setInviteRole('fulfillment_specialist')}
                      style={{ marginTop: 3 }}
                    />
                    <div>
                      <strong style={{ display: 'block', fontSize: '0.88rem' }}>Fulfillment Specialist</strong>
                      <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
                        Can view orders, print packing slips, update tracking numbers, and process refunds. No catalog editing.
                      </span>
                    </div>
                  </label>
                </div>
              </Field>

              {inviteError && (
                <div
                  style={{
                    padding: '8px 12px',
                    borderRadius: 6,
                    background: 'rgba(239, 68, 68, 0.1)',
                    color: 'var(--red)',
                    fontSize: '0.82rem',
                  }}
                >
                  {inviteError}
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: '1rem' }}>
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => setInviteOpen(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="button"
                  disabled={inviting || !inviteEmail.trim()}
                >
                  {inviting ? 'Inviting...' : 'Send Invitation'}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}

      {/* Remove Member / Revoke Invitation Confirmation Dialog */}
      {deleteTarget && (
        <div className="dialog-backdrop">
          <section
            ref={deleteDialogRef}
            className="admin-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="remove-title"
          >
            <div className="admin-dialog-head">
              <div>
                <span className="eyebrow" style={{ color: 'var(--red)' }}>
                  {deleteTarget.status === 'pending' ? 'REVOKE INVITATION' : 'REMOVE MEMBER'}
                </span>
                <h2 id="remove-title">
                  {deleteTarget.status === 'pending'
                    ? `Revoke invitation for ${deleteTarget.email}?`
                    : `Remove ${deleteTarget.email}?`}
                </h2>
              </div>
              <button
                className="icon-button"
                aria-label="Close"
                onClick={() => setDeleteTarget(null)}
              >
                <X size={19} />
              </button>
            </div>

            <div style={{ padding: '1rem 0', color: 'var(--muted)', fontSize: '0.9rem', lineHeight: 1.5 }}>
              {deleteTarget.status === 'pending' ? (
                <>
                  Are you sure you want to revoke the team invitation for <strong>{deleteTarget.email}</strong>?
                  Their signup invitation link will be invalidated immediately.
                </>
              ) : (
                <>
                  Are you sure you want to remove <strong>{deleteTarget.email}</strong> from the <strong>{store.name}</strong> team?
                  They will immediately lose access to this store&apos;s workspace and dashboard.
                </>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: '1rem' }}>
              <button
                type="button"
                className="button secondary"
                onClick={() => setDeleteTarget(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button"
                style={{ background: 'var(--red)', color: '#fff' }}
                disabled={deleting}
                onClick={handleRemoveMember}
              >
                {deleting
                  ? deleteTarget.status === 'pending'
                    ? 'Revoking...'
                    : 'Removing...'
                  : deleteTarget.status === 'pending'
                    ? 'Revoke Invitation'
                    : 'Remove Member'}
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}


function MerchantSettings({ store }: { store: Store }) {
  const { notify } = useShop(); const client = useQueryClient(); const [busy, setBusy] = useState(false);
  const profile = useQuery({ queryKey: ['store-profile', store.id], queryFn: () => api<StoreProfile>(`stores/${store.id}/profile`) });
  const address = useQuery({ queryKey: ['store-address', store.id], queryFn: () => api<Record<string, string>>(`stores/${store.id}/pickup-address`) });
  const allProductsStore = useQuery({
    queryKey: ['merchant-products-select', store.id],
    queryFn: () => api<Page<MerchantProduct>>(`stores/${store.id}/products?limit=100`),
  });
  const [pinnedProducts, setPinnedProducts] = useState<number[]>([]);
  useEffect(() => {
    if (profile.data?.pinned_products) {
      setPinnedProducts(profile.data.pinned_products);
    }
  }, [profile.data?.pinned_products]);
  const stripeStatus = useQuery({
    queryKey: ['stripe-connect-status', store.id],
    queryFn: () => api<StripeConnectStatus>(`stores/${store.id}/stripe-status`),
  });
  const onboardingState = typeof window === 'undefined'
    ? null
    : new URLSearchParams(window.location.search).get('stripe_onboarding');
  useEffect(() => {
    if (!onboardingState) return;
    let active = true;
    void stripeStatus.refetch()
      .then(({ data }) => {
        if (!active || onboardingState !== 'return') return;
        if (data?.connected) {
          notify('Stripe payouts are connected.');
        } else {
          notify('Stripe saved your progress. Finish the remaining payout setup to enable payouts.');
        }
      })
      .catch(() => {
        if (active && onboardingState === 'return') {
          notify('We could not refresh Stripe payout status. Please try again shortly.', true);
        }
      })
      .finally(() => {
        if (active) window.history.replaceState(null, '', '/merchant/settings');
      });
    return () => { active = false; };
  }, [onboardingState, notify, stripeStatus.refetch]);
  async function brandingSaved(updatedProfile: StoreProfile): Promise<void> {
    client.setQueryData<StoreProfile>(['store-profile', store.id], updatedProfile);
    await client.invalidateQueries({ queryKey: ['public-store'] });
  }

  async function connectStripe() {
    try {
      const result = await api<StripeConnectResponse>(`stores/${store.id}/connect-stripe`, 'POST');
      if (result.connected) {
        await stripeStatus.refetch();
        notify('Stripe payouts are already connected.');
        return;
      }
      if (result.pending) {
        await stripeStatus.refetch();
        notify('Stripe has your payout details and is reviewing the account.');
        return;
      }
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
        pinned_products: pinnedProducts,
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
        {stripeStatus.isLoading ? null : stripeStatus.data?.connected ? (
          <p role="status" className="success-message">Stripe payouts connected</p>
        ) : stripeStatus.data?.details_submitted && !stripeStatus.data.currently_due.length ? (
          <p role="status">Stripe payout setup is pending verification</p>
        ) : (
          <button type="button" className="button secondary" onClick={connectStripe}>
            {stripeStatus.data?.details_submitted ? 'Complete remaining Stripe details' : 'Connect Stripe payouts'}
          </button>
        )}
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

          <h2>Pinned products on store page</h2>
          <p className="muted" style={{ fontSize: '13px', marginTop: '-8px', marginBottom: '16px' }}>
            Pin up to 3 featured products to appear at the very top of your main storefront listing ({pinnedProducts.length} / 3 pinned).
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '16px', marginBottom: '24px' }}>
            {[0, 1, 2].map((index) => {
              const productId = pinnedProducts[index];
              const product = allProductsStore.data?.results?.find((p) => p.id === productId);
              return (
                <div
                  key={index}
                  style={{
                    border: '1px solid var(--line)',
                    borderRadius: '8px',
                    padding: '14px',
                    background: productId ? 'var(--soft)' : 'var(--paper)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    minHeight: '120px',
                    gap: '10px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Pinned Slot #{index + 1}
                    </span>
                    {productId && (
                      <button
                        type="button"
                        className="text-button"
                        style={{ fontSize: '12px', color: 'var(--alert, #ef4444)' }}
                        onClick={() => {
                          const next = pinnedProducts.filter((_, i) => i !== index);
                          setPinnedProducts(next);
                        }}
                      >
                        Unpin
                      </button>
                    )}
                  </div>
                  {productId ? (
                    product ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <div style={{ width: '48px', height: '48px', borderRadius: '6px', overflow: 'hidden', flexShrink: 0, border: '1px solid var(--line)' }}>
                          <ProductImage src={product.images[0]?.image || product.image_url} alt={product.title} />
                        </div>
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div style={{ fontSize: '13px', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {product.title}
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
                            {money(product.price)}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div style={{ fontSize: '13px', color: 'var(--muted)' }}>Product #{productId}</div>
                    )
                  ) : (
                    <div>
                      <select
                        aria-label={`Select product for pin slot ${index + 1}`}
                        style={{ width: '100%', fontSize: '12px', padding: '8px' }}
                        value=""
                        onChange={(e) => {
                          const chosenId = Number(e.target.value);
                          if (chosenId && !pinnedProducts.includes(chosenId)) {
                            setPinnedProducts([...pinnedProducts, chosenId]);
                          }
                        }}
                      >
                        <option value="">+ Pin a product...</option>
                        {allProductsStore.data?.results
                          ?.filter((p) => !pinnedProducts.includes(p.id))
                          .map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.title} ({money(p.price)})
                            </option>
                          ))}
                      </select>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

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
  const { notify } = useShop();
  const [selectedVariant, setSelectedVariant] = useState<number | null>(null);
  const [selectedGalleryImage, setSelectedGalleryImage] = useState<string | null>(null);
  const [quantity, setQuantity] = useState<number>(1);
  const [preview, setPreview] = useState<PreviewProduct | null>(null);
  const [ready, setReady] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  const handleSharePreview = async () => {
    const url = typeof window !== 'undefined' ? window.location.href : '/merchant/products/preview';
    const shareData = {
      title: preview?.title || 'Product Preview',
      text: `Preview: ${preview?.title || 'Product'} on ProAce`,
      url,
    };

    let shared = false;
    if (typeof navigator !== 'undefined' && navigator.share && navigator.canShare && navigator.canShare(shareData)) {
      try {
        await navigator.share(shareData);
        shared = true;
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
      }
    }

    if (!shared) {
      try {
        if (typeof navigator !== 'undefined' && navigator.clipboard) {
          await navigator.clipboard.writeText(url);
        } else {
          const textarea = document.createElement('textarea');
          textarea.value = url;
          document.body.appendChild(textarea);
          textarea.select();
          document.execCommand('copy');
          document.body.removeChild(textarea);
        }
        setCopied(true);
        notify('Preview link copied to clipboard!');
        setTimeout(() => setCopied(false), 2500);
      } catch {
        notify('Failed to copy preview link', true);
      }
    }
  };

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
  const activeVariant: ProductVariant | undefined = selectedVariant === null
    ? undefined
    : preview.variants[selectedVariant];
  const displayedPrice: number = preview.sale_price + Number(activeVariant?.price_delta || 0);
  const isSoldOut: boolean = !preview.is_digital && (preview.available <= 0 || preview.label === 'sold out');
  const variantStock: number = typeof activeVariant?.available === 'number'
    ? Math.min(preview.available, activeVariant.available)
    : preview.available;
  const effectiveStock: number = preview.is_digital ? 99 : isSoldOut ? 0 : Math.max(0, variantStock);
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
              onClick={handleSharePreview}
              title="Copy preview link"
            >
              {copied ? <Check size={14} /> : <Share2 size={14} />}
              {copied ? 'Link copied' : 'Share preview'}
            </button>
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
                discount={preview.product_type === 'affiliate_clickbank' ? 0 : preview.discount}
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
              <span style={{ color: 'var(--line)' }}>•</span>
              <button
                type="button"
                className="text-button"
                onClick={handleSharePreview}
                title="Copy preview link"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 4, textDecoration: 'none' }}
              >
                {copied ? <Check size={14} style={{ color: 'var(--green)' }} /> : <Share2 size={14} />}
                <span style={{ color: copied ? 'var(--green)' : 'inherit', fontWeight: copied ? 600 : 'normal' }}>
                  {copied ? 'Link copied' : 'Share'}
                </span>
              </button>
            </div>
            <div className="detail-price" style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              {preview.product_type === 'affiliate_clickbank' ? (
                <span className="partner-price-note">Price available on partner site</span>
              ) : (
                <strong>{displayedPrice > 0 ? money(displayedPrice) : 'Price TBD'}</strong>
              )}
              {preview.product_type !== 'affiliate_clickbank' && preview.discount > 0 && (
                <>
                  <del>{money(originalPrice)}</del>
                  <span>You save {money(originalPrice - displayedPrice)}</span>
                </>
              )}
              {preview.product_type !== 'affiliate_clickbank' && preview.drop_at && new Date(preview.drop_at).getTime() > Date.now() && (
                <DropCountdown dropAt={preview.drop_at} />
              )}
              {preview.product_type !== 'affiliate_clickbank' && (!preview.drop_at || new Date(preview.drop_at).getTime() <= Date.now()) && preview.flash_sale_end && (
                <FlashCountdown end={preview.flash_sale_end} />
              )}
            </div>
            <p className="description">{preview.description}</p>
            {preview.variants.length > 0 && (
              <div className="product-variants" style={{ margin: '16px 0' }}>
                <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--ink)', display: 'block', marginBottom: '8px' }}>Option: <strong style={{ color: 'var(--green)' }}>{activeVariant?.name || 'Original edition'}</strong></span>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    aria-pressed={selectedVariant === null}
                    onClick={() => {
                      setSelectedVariant(null);
                      setSelectedGalleryImage(preview.image);
                      setQuantity(1);
                    }}
                    style={{
                      padding: '6px 14px',
                      borderRadius: '8px',
                      border: selectedVariant === null ? '2px solid var(--green)' : '1px solid var(--line)',
                      background: selectedVariant === null ? 'var(--green-light)' : 'var(--paper)',
                      color: selectedVariant === null ? 'var(--green)' : 'var(--ink)',
                      fontWeight: selectedVariant === null ? 600 : 500,
                      fontSize: '13px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    Original edition
                  </button>
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
                      {!preview.is_digital && ((typeof variant.available === 'number' && variant.available <= 0) || isSoldOut) && (
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
              <button
                type="button"
                className={`button secondary ${copied ? 'copied' : ''}`}
                aria-label="Share product preview"
                title={copied ? 'Link copied to clipboard!' : 'Share preview link'}
                onClick={handleSharePreview}
              >
                {copied ? <Check size={20} style={{ color: 'var(--green)' }} /> : <Share2 size={20} />}
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
