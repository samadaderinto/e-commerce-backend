'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FormEvent, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDownToLine, ArrowLeft, ArrowRight, ArrowUpRight, ChartNoAxesCombined, Check, ChevronLeft, ChevronRight, CircleHelp, Clock, Eye, LayoutDashboard, Package, Plus, Search, Settings, ShoppingBag, Store as StoreIcon, Truck, Upload, WalletCards, X } from 'lucide-react';
import { api, categories, money } from '@/lib/api';
import type { Dashboard, MerchantProduct, Page, Store, StorePayout, TrackingEvent } from '@/lib/types';
import { useShop } from './providers';
import { Gate } from './account';
import { Empty, ErrorState, Field, Loading, ProductImage, Status, VerifiedBadge } from './ui';

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


export function MerchantPage({ segments }: { segments: string[] }) {
  const { user } = useShop();
  const [storeId, setStoreId] = useState<number | null>(null);
  const stores = useQuery({ queryKey: ['stores', user?.id], queryFn: () => api<Page<Store>>('stores?limit=100'), enabled: !!user });
  const store = stores.data?.results.find(store => store.id === storeId) || stores.data?.results[0];
  const section = segments[0] || 'overview';
  const links = [['overview', 'Overview', LayoutDashboard], ['products', 'Products', Package], ['orders', 'Orders', ShoppingBag], ['settings', 'Store settings', Settings]] as const;
  return <Gate next="/merchant"><div className="merchant-shell"><aside className="merchant-sidebar"><Link className="merchant-brand" href="/merchant"><span><StoreIcon size={20} /></span><div>Seller workspace<small>MAKE GOOD THINGS HAPPEN</small></div></Link>{store && <label className="store-select"><span>YOUR STORE</span><select aria-label="Select store" value={store.id} onChange={event => setStoreId(Number(event.target.value))}>{stores.data?.results.map(store => <option key={store.id} value={store.id}>{store.name}</option>)}</select></label>}<nav>{links.map(([key, name, Icon]) => <Link key={key} className={section === key ? 'active' : ''} href={key === 'overview' ? '/merchant' : `/merchant/${key}`}><Icon size={19} />{name}{key === 'products' && <ChevronRight size={14} />}</Link>)}</nav><div className="merchant-sidebar-bottom"><Link href="/merchant/new-store"><Plus size={18} />Open another store</Link><Link href="/help"><CircleHelp size={18} />Help & support</Link><Link href="/"><ArrowUpRight size={18} />Back to marketplace</Link><div className="merchant-person"><span>{user?.first_name?.[0]}</span><div><strong>{user?.first_name} {user?.last_name}</strong><small>Store owner</small></div></div></div></aside><div className="merchant-main"><div className="merchant-topline"><span>Workspace <ChevronRight size={12} />{section.replaceAll('-', ' ')}</span><Link href={store ? `/shop?store=${store.id}` : '/shop'}><Eye size={16} />View storefront <ArrowUpRight size={14} /></Link></div>{stores.isLoading ? <Loading /> : stores.error ? <ErrorState error={stores.error} retry={() => stores.refetch()} /> : !store || section === 'new-store' ? <OnboardStore /> : store.status === 'blocked' ? <Empty title="Your store is unavailable" text="Contact support about your store status before making further changes." href="/help" label="Visit help centre" /> : section === 'products' && segments[1] ? <ProductEditor key={`${store.id}-${segments[1]}`} store={store} id={segments[1]} /> : section === 'products' ? <MerchantProducts store={store} /> : section === 'orders' ? <MerchantOrders store={store} /> : section === 'settings' ? <MerchantSettings store={store} /> : <MerchantDashboard store={store} />}</div></div></Gate>;
}

function OnboardStore() {
  const { user, notify } = useShop(); const client = useQueryClient(); const router = useRouter(); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(''); const data = Object.fromEntries(new FormData(event.currentTarget));
    try { await api('stores', 'POST', { name: data.name, profile: { email: data.email, bio: data.bio }, address: { address: data.address, city: data.city, state: data.state, country: data.country, zip: data.zip } }); await client.invalidateQueries({ queryKey: ['stores'] }); notify('Your store is ready. Time for your first product.'); router.push('/merchant/products/new'); }
    catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  return <section className="onboarding"><span className="eyebrow green">YOUR NEXT CHAPTER</span><h1>A home for your business.</h1><p className="muted">Introduce your store. Add your products. Meet your customers.</p><div className="onboarding-steps"><span className="active"><b>1</b>Store details</span><ChevronRight size={16} /><span><b>2</b>Your first product</span><ChevronRight size={16} /><span><b>3</b>Open for business</span></div><form className="form-stack" onSubmit={submit}><h2>Let’s make it official</h2><div className="form-row"><Field label="Store name"><input name="name" required maxLength={40} placeholder="Something memorable" /></Field><Field label="Contact email"><input type="email" name="email" required defaultValue={user?.email} /></Field></div><Field label="About your store"><textarea name="bio" placeholder="A little about what makes your store yours" /></Field><h3>Pickup address</h3><Field label="Street address"><input name="address" required /></Field><div className="form-row"><Field label="City"><input name="city" required /></Field><Field label="State / region"><input name="state" required maxLength={30} /></Field></div><div className="form-row"><Field label="Country"><input name="country" required /></Field><Field label="Postal code"><input name="zip" required maxLength={10} /></Field></div>{error && <p className="form-error">{error}</p>}<button className="button" disabled={busy}>{busy ? 'Creating your store…' : 'Create my store'}<ArrowRight size={17} /></button></form></section>;
}

function MerchantDashboard({ store }: { store: Store }) {
  const [days, setDays] = useState('30'); const { user, notify } = useShop(); const client = useQueryClient();
  const stats = useQuery({ queryKey: ['dashboard', store.id, days], queryFn: () => api<Dashboard>(`stores/${store.id}/dashboard?days=${days}`) });
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

  return (
    <>
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
              style={{
                fontSize: '10px',
                fontWeight: 700,
                textTransform: 'uppercase',
                padding: '2px 8px',
                borderRadius: '10px',
                background: isOfficial
                  ? '#fef3c7'
                  : (store.seller_tier?.tier === 'legendary'
                      ? '#ffe4e6'
                      : store.seller_tier?.tier === 'mega'
                        ? '#e0f2fe'
                        : store.seller_tier?.tier === 'power'
                          ? '#d1fae5'
                          : store.seller_tier?.tier === 'accelerator'
                            ? '#ede9fe'
                            : store.seller_tier?.tier === 'booster'
                              ? '#f1f5f9'
                              : '#e0f2fe'),
                color: isOfficial
                  ? '#b45309'
                  : (store.seller_tier?.tier === 'booster'
                      ? '#475569'
                      : store.seller_tier?.badge_hex || '#1d9bf0'),
                border: store.seller_tier?.tier === 'legendary' ? '1px solid #fecdd3' : 'none'
              }}
            >
              {isOfficial ? 'Official Partner Store (Gold)' : (store.seller_tier?.name ? `${store.seller_tier.name} Seller` : 'Starter')}
            </span>
          </p>
        </div>
        <div className="form-actions">
          <button className="button secondary" onClick={() => setRequestingPayout(true)}>
            <WalletCards size={17} />
            Request payout
          </button>
          <Link className="button" href="/merchant/products/new">
            <Plus size={17} />
            Add product
          </Link>
        </div>
      </div>

      {!isOfficial && store.seller_tier?.next_tier && store.seller_tier.next_threshold && (
        <div
          style={{
            background: '#f8fafc',
            border: '1px solid var(--line)',
            borderRadius: '8px',
            padding: '12px 18px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
            flexWrap: 'wrap'
          }}
        >
          <div>
            <strong style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              Seller Level: <VerifiedBadge tierData={store.seller_tier} size={15} /> {store.seller_tier.name}
            </strong>
            <small className="muted" style={{ fontSize: '11px' }}>
              Total Sales: {money(store.seller_tier.current_sales || 0)} · Reach {money(store.seller_tier.next_threshold)} to unlock <strong>{store.seller_tier.next_tier}</strong> badge
            </small>
          </div>
          <div style={{ minWidth: '170px', flex: '1', maxWidth: '300px' }}>
            <div style={{ height: '7px', background: '#e2e8f0', borderRadius: '4px', overflow: 'hidden' }}>
              <div
                style={{
                  height: '100%',
                  background: store.seller_tier.badge_hex || 'var(--green)',
                  width: `${Math.min(100, Math.round(((store.seller_tier.current_sales || 0) / store.seller_tier.next_threshold) * 100))}%`
                }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9px', color: 'var(--muted)', marginTop: '4px' }}>
              <span>{money(store.seller_tier.current_sales || 0)}</span>
              <span>Next: {store.seller_tier.next_tier} ({money(store.seller_tier.next_threshold)})</span>
            </div>
          </div>
        </div>
      )}<div className="dashboard-period"><h2>Your store at a glance</h2><select aria-label="Dashboard period" value={days} onChange={event => setDays(event.target.value)}><option value="7">Last 7 days</option><option value="30">Last 30 days</option><option value="90">Last 90 days</option></select></div>{stats.isLoading ? <Loading /> : stats.error ? <ErrorState error={stats.error} retry={() => stats.refetch()} /> : data && <>
    <div className="stats-grid">{[
      {label: 'Available for Payout', value: money(data.wallet?.available_balance || '0.00'), icon: WalletCards, note: 'Cleared sales past 7-day refund window'},
      {label: 'In Review (Escrow)', value: money(data.wallet?.in_review || '0.00'), icon: Clock, note: 'Orders within 7-day refund period'},
      {label: isOfficial ? 'Gross Sales (100% Retained)' : 'Gross Sales (Item Value)', value: money(data.wallet?.gross_sales || data.sales.estimated_item_value), icon: ChartNoAxesCombined, note: isOfficial ? 'Total sales with 0% platform fee' : 'Total item sales before 4% platform fee'},
      {label: isOfficial ? 'Platform Fee (0%)' : `Platform Commission (${data.wallet?.platform_fee_percent || '4'}%)`, value: isOfficial ? '$0.00' : money(data.wallet?.platform_fee_deducted || '0.00'), icon: ShoppingBag, note: isOfficial ? 'Official company store exemption (0% fee)' : 'Marketplace hosting & payment processing'}
    ].map(({label, value, icon: Icon, note}, index) => <div key={label} className={`stat-item stat-${index}`}><div><span>{label}</span><Icon size={19} /></div><strong>{value}</strong><small>{note}</small></div>)}</div>
    {requestingPayout && <div className="setup-notice" style={{ flexDirection: 'column', alignItems: 'stretch' }}><h3>Request Merchant Payout</h3><p className="muted">Withdraw available cleared funds directly to your bank account.</p><form className="form-stack" onSubmit={submitPayout}><div className="form-row"><Field label={`Payout amount (Max: ${money(data.wallet?.available_balance || '0.00')})`}><input type="number" min="5.00" max={Number(data.wallet?.available_balance || '0')} step="0.01" required value={payoutAmount} onChange={e => setPayoutAmount(e.target.value)} placeholder="0.00" /></Field><Field label="Bank Name"><input required value={bankName} onChange={e => setBankName(e.target.value)} placeholder="e.g. JPMorgan Chase" /></Field></div><Field label="Account Number / IBAN"><input required value={accountNumber} onChange={e => setAccountNumber(e.target.value)} placeholder="e.g. 1234567890" /></Field><div className="form-row"><button className="button" disabled={payoutBusy}>{payoutBusy ? 'Submitting…' : 'Submit withdrawal request'}</button><button type="button" className="button secondary" onClick={() => setRequestingPayout(false)}>Cancel</button></div></form></div>}
    {checklist.data && !checklist.data.complete && <div className="setup-notice"><span className="setup-check"><StoreIcon size={23} /></span><div><strong>Your store is taking shape.</strong><p>{Object.values(checklist.data.steps).filter(Boolean).length} of {Object.values(checklist.data.steps).length} setup steps complete.</p></div><Link className="text-link" href={checklist.data.steps.product_added ? '/merchant/settings' : '/merchant/products/new'}>Continue setup <ArrowRight size={16} /></Link></div>}
    <div className="dashboard-columns"><section className="analytics-panel"><div className="section-heading"><div><h2>Order activity</h2><p>{data.orders.total} orders in the last {days} days</p></div><span className="chart-legend"><i />Orders</span></div><div className="bar-chart" role="img" aria-label={`Order activity: ${data.orders.total} orders in ${days} days`}><div className="chart-y"><span>{max}</span><span>{max / 2}</span><span>0</span></div><div className="chart-bars">{values.map((day, index) => <div className="chart-column" key={day.date} title={`${day.date}: ${day.count} orders`}><span style={{ height: `${day.count / max * 100}%`, minHeight: day.count ? 5 : 1 }} /><small>{index === 0 || index === values.length - 1 || (index % 7 === 0 && index < values.length - 3) ? new Date(day.date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : ''}</small></div>)}</div></div></section><section className="stock-panel"><div className="section-heading"><h2>Needs a little attention</h2><span className="stock-number">{data.inventory.low_stock + data.inventory.out_of_stock}</span></div><p className="muted">Keep your best finds in stock.</p>{data.low_stock_products.length ? data.low_stock_products.slice(0, 4).map(product => <Link className="stock-row" href={`/merchant/products/${product.id}`} key={product.id}><span><Package size={19} /></span><div><strong>{product.title}</strong><small>{product.available ? `${product.available} units left` : 'Out of stock'}</small></div><ArrowUpRight size={16} /></Link>) : <div className="all-good"><Check size={26} /><strong>Looking good.</strong><p>Your inventory is in a healthy place.</p></div>}<Link className="text-link" href="/merchant/products">Manage inventory <ArrowRight size={16} /></Link></section></div>
    <section className="merchant-section"><div className="section-heading"><h2>Recent orders</h2><Link className="text-link" href="/merchant/orders">View all orders <ArrowRight size={16} /></Link></div>{orders.isLoading ? <Loading /> : orders.error ? <ErrorState error={orders.error} /> : <MerchantOrderTable orders={orders.data?.results || []} />}</section>
    <section className="merchant-section"><div className="section-heading"><h2>Payout history</h2><span className="muted">{payouts.data?.length || 0} payout requests</span></div>{payouts.isLoading ? <Loading /> : payouts.error ? <ErrorState error={payouts.error} /> : !payouts.data?.length ? <p className="muted">No payouts requested yet.</p> : <div className="table-scroll"><table><thead><tr><th>Date</th><th>Reference</th><th>Amount</th><th>Method</th><th>Status</th></tr></thead><tbody>{payouts.data.map(p => <tr key={p.id}><td>{new Date(p.created).toLocaleDateString()}</td><td><strong>{p.reference}</strong></td><td>{money(p.amount)}</td><td>{p.payout_method}</td><td><Status value={p.status} /></td></tr>)}</tbody></table></div>}</section>
    <div className="dashboard-footnote">{isOfficial ? 'Company official store: 100% of sales are retained with zero platform commission fee.' : 'Net sales are calculated at 96% after the 4% platform fee. Funds clear from review to your available payout balance after the 7-day customer refund window expires.'}</div>
  </>}</>
  );
}

function exportRows(products: MerchantProduct[]) {
  const escape = (value: unknown) => `"${String(value).replace(/^[=+@-]/, "'$&").replaceAll('"', '""')}"`;
  const rows = [['ID', 'Product', 'Price', 'Stock', 'Published'], ...products.map(product => [product.id, product.title, product.price, product.available, product.visibility])];
  const url = URL.createObjectURL(new Blob([rows.map(row => row.map(escape).join(',')).join('\r\n')], { type: 'text/csv;charset=utf-8;' }));
  const link = document.createElement('a'); link.href = url; link.download = 'proace-products.csv'; link.click(); URL.revokeObjectURL(url);
}

function MerchantProducts({ store }: { store: Store }) {
  const [search, setSearch] = useState(''); const [filter, setFilter] = useState(''); const [offset, setOffset] = useState(0); const [busy, setBusy] = useState<number | null>(null); const { notify } = useShop(); const client = useQueryClient();
  const query = new URLSearchParams({ search, limit: '15', offset: String(offset) }); if (filter) query.set('visibility', filter);
  const products = useQuery({ queryKey: ['merchant-products', store.id, query.toString()], queryFn: () => api<Page<MerchantProduct>>(`stores/${store.id}/products?${query}`) });
  async function toggle(product: MerchantProduct) { setBusy(product.id); try { await api(`stores/${store.id}/products/${product.id}`, 'PATCH', { visibility: !product.visibility }); await client.invalidateQueries({ queryKey: ['merchant-products'] }); await client.invalidateQueries({ queryKey: ['dashboard'] }); await client.invalidateQueries({ queryKey: ['products'] }); notify(product.visibility ? 'Product unpublished' : 'Your product is live'); } catch (error) { notify((error as Error).message, true); } finally { setBusy(null); } }
  return <><div className="merchant-heading"><div><h1>Your products</h1><p>A collection worth discovering.</p></div><div className="form-actions"><button className="button secondary" title="Export current page" disabled={!products.data?.results.length} onClick={() => exportRows(products.data!.results)}><ArrowDownToLine size={17} />Export page</button><Link className="button" href="/merchant/products/new"><Plus size={17} />Add product</Link></div></div><div className="merchant-toolbar"><div className="tabs">{[['', 'All products'], ['true', 'Published'], ['false', 'Drafts']].map(([value, label]) => <button className={filter === value ? 'active' : ''} key={value} onClick={() => { setFilter(value); setOffset(0); }}>{label}</button>)}</div><div className="search-box"><Search size={17} /><input aria-label="Search your products" placeholder="Search products…" value={search} onChange={event => { setSearch(event.target.value); setOffset(0); }} /></div></div>{products.isLoading ? <Loading /> : products.error ? <ErrorState error={products.error} retry={() => products.refetch()} /> : !products.data?.results.length ? <Empty title={search ? 'Nothing matches just yet' : 'Your first product starts here'} text={search ? 'Try another search or change the filter.' : 'Add your first listing and give your customers something to discover.'} href="/merchant/products/new" label="Add product" /> : <><div className="table-scroll"><table><thead><tr><th>Product</th><th>Category</th><th>Price</th><th>Inventory</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{products.data.results.map(product => <tr key={product.id}><td><Link className="table-product" href={`/merchant/products/${product.id}`}><ProductImage src={product.images[0]?.image || product.image_url} alt={product.title} /><span><strong>{product.title}</strong><small style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>#{String(product.id).padStart(5, '0')} · {product.brand || store.name}<VerifiedBadge tier={store.is_official ? 'official' : 'starter'} tierData={store.seller_tier} size={12} /></small></span></Link></td><td>{categories.find(category => category.key === product.category)?.name || product.category}</td><td className="table-price">{money(product.price)}</td><td><span className={product.available <= 5 ? 'low-stock' : ''}>{product.available} in stock</span></td><td><button className={`publish-toggle ${product.visibility ? 'on' : ''}`} disabled={busy === product.id} role="switch" aria-checked={product.visibility} aria-label={`Publish ${product.title}`} onClick={() => toggle(product)}><span />{product.visibility ? 'Published' : 'Draft'}</button></td><td><Link className="icon-button" title="Edit product" aria-label={`Edit ${product.title}`} href={`/merchant/products/${product.id}`}><ArrowUpRight size={18} /></Link></td></tr>)}</tbody></table></div><div className="table-pagination"><span>Showing {offset + 1}–{Math.min(offset + 15, products.data.count)} of {products.data.count} products</span><div><button className="icon-button" aria-label="Previous page" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 15))}><ChevronLeft size={18} /></button><button className="icon-button" aria-label="Next page" disabled={offset + 15 >= products.data.count} onClick={() => setOffset(value => value + 15)}><ChevronRight size={18} /></button></div></div></>}</>;
}

function ProductEditor({ store, id }: { store: Store; id: string }) {
  const isNew = id === 'new'; const client = useQueryClient(); const router = useRouter(); const { notify } = useShop(); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const product = useQuery({ queryKey: ['merchant-product', store.id, id], queryFn: () => api<MerchantProduct>(`stores/${store.id}/products/${id}`), enabled: !isNew });
  const [isDigital, setIsDigital] = useState<boolean | null>(null);
  const effectiveIsDigital = isDigital ?? product.data?.is_digital ?? false;

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(''); const form = Object.fromEntries(new FormData(event.currentTarget)) as Record<string, string>;
    const digital = form.is_digital === 'on';
    const data = {
      ...form,
      available: Number(form.available),
      discount: Number(form.discount),
      weight: digital ? '0.00' : (form.weight || '1.00'),
      visibility: form.visibility === 'on',
      is_digital: digital,
      tags: form.tags.split(',').map(value => value.trim()).filter(Boolean),
    };
    try {
      const result = await api<MerchantProduct>(`stores/${store.id}/products${isNew ? '' : `/${id}`}`, isNew ? 'POST' : 'PATCH', data);
      await client.invalidateQueries({ queryKey: ['merchant-products'] });
      await client.invalidateQueries({ queryKey: ['dashboard'] });
      await client.invalidateQueries({ queryKey: ['merchant-product'] });
      await client.invalidateQueries({ queryKey: ['products'] });
      notify(isNew ? 'Your product has been created' : 'Product updated');
      if (isNew) router.replace(`/merchant/products/${result.id}`);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!isNew && product.isLoading) return <Loading />; if (product.error) return <ErrorState error={product.error} />; const data = product.data;
  return <><Link className="text-link" href="/merchant/products"><ArrowLeft size={16} />All products</Link><div className="merchant-heading"><div><h1>{isNew ? 'Something new to discover.' : 'The details make it yours.'}</h1><p>{isNew ? 'Give your next best-seller a good start.' : `Editing ${data?.title}`}</p></div>{data?.visibility && <Link className="button secondary" href={`/products/${id}`}><Eye size={16} />View listing</Link>}</div><form className="product-editor" onSubmit={save}><section className="form-stack"><h2>Product information</h2><Field label="Product title"><input name="title" defaultValue={data?.title} required maxLength={225} placeholder="A clear, descriptive name" /></Field><Field label="Description"><textarea name="description" defaultValue={data?.description} required rows={5} placeholder="What makes this product a good find?" /></Field><div className="form-row"><Field label="Brand"><input name="brand" maxLength={80} defaultValue={data?.brand} /></Field><Field label="Category"><select name="category" defaultValue={data?.category || ''} required><option value="" disabled>Select a category</option>{categories.map(category => <option value={category.key} key={category.key}>{category.name}</option>)}</select></Field></div><label className="check-row"><input type="checkbox" name="is_digital" checked={effectiveIsDigital} onChange={e => setIsDigital(e.target.checked)} />Digital download / e-book (available worldwide, 0 lbs weight)</label>{effectiveIsDigital ? <Field label="Download URL"><input name="digital_file_url" type="url" maxLength={1000} defaultValue={data?.digital_file_url} placeholder="https://…" required /></Field> : <div className="form-row"><Field label="Shipping weight (lbs)"><input name="weight" type="number" min="0.01" max="999.99" step="0.01" defaultValue={data?.weight || '1.00'} required placeholder="e.g. 1.25" /></Field></div>}<p className="fine-print">{effectiveIsDigital ? 'Digital products are fulfilled automatically worldwide with $0.00 shipping.' : 'Physical products are shipped within the US with live USPS rate calculation.'}</p><Field label="Tags"><input name="tags" defaultValue={data?.tags?.join(', ')} placeholder="Audio, wireless, everyday" /></Field><h2>Product photography</h2><Field label="Image URL"><input name="image_url" type="url" maxLength={1000} defaultValue={data?.image_url} placeholder="https://…" /></Field>{data?.image_url && <div className="editor-image"><ProductImage src={data.image_url} alt={data.title} /></div>}</section><aside className="editor-aside"><section><h2>Pricing & stock</h2><Field label="Price (USD)"><input name="price" type="number" min="0.01" step="0.01" required defaultValue={data?.price} /></Field><div className="form-row"><Field label="Discount (%)"><input type="number" name="discount" min="0" max="60" step="1" required defaultValue={data?.discount || 0} /></Field><Field label="Stock quantity"><input name="available" type="number" min="0" step="1" required defaultValue={data?.available || 0} /></Field></div><hr /><h3>Availability</h3><label className="check-row"><input type="checkbox" name="visibility" defaultChecked={data?.visibility || false} />Publish to the marketplace</label>{error && <p className="form-error">{error}</p>}<button className="button" disabled={busy}>{busy ? 'Saving…' : isNew ? 'Create product' : 'Save changes'}<Check size={17} /></button><Link className="button secondary" href="/merchant/products">Back to products</Link></section></aside></form>{!isNew && <ProductAssets store={store} product={data!} />}</>;
}

function ProductAssets({ store, product }: { store: Store; product: MerchantProduct }) {
  const { notify } = useShop(); const client = useQueryClient(); const [uploading, setUploading] = useState(false);
  const base = `stores/${store.id}/products/${product.id}`;
  const specs = useQuery({ queryKey: ['specs', product.id], queryFn: () => api<Record<string, string>>(`${base}/specifications`) });
  return <section className="merchant-section"><div className="section-heading"><h2>Image gallery</h2><label className="button secondary upload-label"><Upload size={17} />{uploading ? 'Uploading…' : 'Upload image'}<input type="file" accept="image/jpeg,image/png,image/webp" disabled={uploading} onChange={async event => { const file = event.target.files?.[0]; if (!file) return; if (file.size > 5 * 1024 * 1024) { notify('Images must be 5 MB or smaller.', true); return; } setUploading(true); const form = new FormData(); form.append('image', file); try { await api(`${base}/images`, 'POST', form); await client.invalidateQueries({ queryKey: ['merchant-product'] }); notify('Image uploaded'); } catch (error) { notify((error as Error).message, true); } finally { setUploading(false); event.target.value = ''; } }} /></label></div><div className="asset-gallery">{product.images.map(image => <div key={image.id}><ProductImage src={image.image} alt={product.title} /><button className="icon-button" aria-label="Delete image" onClick={async () => { try { await api(`${base}/images/${image.id}`, 'DELETE'); await client.invalidateQueries({ queryKey: ['merchant-product'] }); } catch (error) { notify((error as Error).message, true); } }}><X size={16} /></button></div>)}</div><details className="spec-editor"><summary>Product specifications</summary>{specs.isLoading ? <Loading /> : specs.error ? <ErrorState error={specs.error} /> : <form className="form-stack" onSubmit={async event => { event.preventDefault(); const payload = Object.fromEntries(new FormData(event.currentTarget)); try { await api(`${base}/specifications`, 'PUT', payload); notify('Specifications saved'); await specs.refetch(); } catch (error) { notify((error as Error).message, true); } }}><div className="form-row"><Field label="SKU / serial number"><input name="serial" maxLength={25} required defaultValue={specs.data?.serial} /></Field><Field label="Colour"><input name="color" maxLength={25} required defaultValue={specs.data?.color} /></Field></div><Field label="Attributes"><input name="attributes" maxLength={250} required defaultValue={specs.data?.attributes} /></Field><div className="form-row">{['height', 'width', 'breadth', 'weight'].map(field => <Field label={field.charAt(0).toUpperCase() + field.slice(1)} key={field}><input type="number" name={field} min="0.01" max="99.99" step="0.01" required defaultValue={specs.data?.[field]} /></Field>)}</div><button className="button">Save specifications</button></form>}</details></section>;
}

function MerchantOrderTable({ orders, storeId, onUpdated }: { orders: MerchantOrder[]; storeId?: number; onUpdated?: () => void }) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const [trackingOrder, setTrackingOrder] = useState<MerchantOrder | null>(null);
  const [trackingNumber, setTrackingNumber] = useState('');
  const [carrier, setCarrier] = useState('USPS');
  const [orderStatus, setOrderStatus] = useState('shipped');
  const [busy, setBusy] = useState(false);
  const { notify } = useShop();

  async function submitTracking(event: FormEvent) {
    event.preventDefault();
    if (!storeId || !trackingOrder) return;
    setBusy(true);
    try {
      await api(`stores/${storeId}/orders/${trackingOrder.id}/tracking`, 'POST', {
        tracking_number: trackingNumber,
        carrier,
        status: orderStatus,
      });
      notify(`Order #${trackingOrder.reference} updated to ${orderStatus}`);
      setTrackingOrder(null);
      setTrackingNumber('');
      onUpdated?.();
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  if (!orders.length) return <div className="empty-state"><ShoppingBag size={30} /><h2>The first of many.</h2><p>Your customer orders will appear here.</p></div>;
  return <>
    <div className="table-scroll"><table><thead><tr><th>Order</th><th>Date</th><th>Products</th><th>Units</th><th>Tracking</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{orders.map(order => <tr key={order.id}><td><strong>{order.reference}</strong></td><td>{new Date(order.created).toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric'})}</td><td>{expanded === order.id ? order.items.map(item => <p key={item.product}>{item.title} × {item.quantity}</p>) : `${order.items[0]?.title || 'Order'}${order.items.length > 1 ? ` +${order.items.length - 1}` : ''}`}</td><td>{order.items.reduce((sum, item) => sum + item.quantity, 0)}</td><td>{order.tracking_number ? <small style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Truck size={13} color="#0066cc" />{order.carrier || 'USPS'}: {order.tracking_number}</small> : <span className="muted" style={{ fontSize: '0.8rem' }}>No tracking</span>}</td><td><Status value={order.status} /></td><td style={{ whiteSpace: 'nowrap' }}><button className="icon-button" aria-label={`View items for ${order.reference}`} title="View order items" onClick={() => setExpanded(expanded === order.id ? null : order.id)}><Eye size={17} /></button>{storeId && ['pending', 'confirmed', 'shipped'].includes(order.status) && <button className="button secondary" style={{ padding: '0.25rem 0.6rem', fontSize: '0.78rem', marginLeft: '0.4rem' }} onClick={() => { setTrackingOrder(order); setTrackingNumber(order.tracking_number || ''); setCarrier(order.carrier || 'USPS'); setOrderStatus(order.status === 'pending' ? 'shipped' : order.status); }}><Truck size={13} />Ship / Track</button>}</td></tr>)}</tbody></table></div>
    {trackingOrder && <div className="admin-dialog-backdrop" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget) setTrackingOrder(null); }}><section className="admin-dialog" role="dialog" aria-modal="true" aria-labelledby="tracking-title"><div className="admin-dialog-head"><div><span className="eyebrow green">FULFILLMENT & TRACKING</span><h2 id="tracking-title">Update Order #{trackingOrder.reference}</h2></div><button className="icon-button" aria-label="Close" onClick={() => setTrackingOrder(null)}><X size={19} /></button></div><form className="form-stack" onSubmit={submitTracking}><div className="form-row"><Field label="Shipping Carrier"><select value={carrier} onChange={e => setCarrier(e.target.value)}><option value="USPS">USPS (United States Postal Service)</option><option value="UPS">UPS</option><option value="FedEx">FedEx</option><option value="DHL">DHL</option></select></Field><Field label="Order Status"><select value={orderStatus} onChange={e => setOrderStatus(e.target.value)}><option value="confirmed">Confirmed</option><option value="shipped">Shipped</option><option value="delivered">Delivered</option></select></Field></div><Field label="USPS Tracking Number"><input required value={trackingNumber} onChange={e => setTrackingNumber(e.target.value)} placeholder="e.g. 9400 1000 0000 0000 0000 00" /></Field><div className="form-actions"><button type="button" className="button secondary" onClick={() => setTrackingOrder(null)}>Cancel</button><button className="button" disabled={busy}>{busy ? 'Updating…' : 'Save tracking & notify customer'}</button></div></form></section></div>}
  </>;
}

function MerchantOrders({ store }: { store: Store }) {
  const [status, setStatus] = useState(''); const [offset, setOffset] = useState(0); const client = useQueryClient();
  const orders = useQuery({ queryKey: ['merchant-orders', store.id, status, offset], queryFn: () => api<Page<MerchantOrder>>(`stores/${store.id}/orders?status=${status}&limit=20&offset=${offset}`) });
  return <><div className="merchant-heading"><div><h1>Every order, a good beginning.</h1><p>Follow your customers’ finds from your store.</p></div><select aria-label="Filter orders by status" value={status} onChange={event => { setStatus(event.target.value); setOffset(0); }}><option value="">All statuses</option>{['pending', 'confirmed', 'shipped', 'delivered', 'cancelled', 'refunded'].map(value => <option key={value} value={value}>{value.charAt(0).toUpperCase() + value.slice(1)}</option>)}</select></div>{orders.isLoading ? <Loading /> : orders.error ? <ErrorState error={orders.error} retry={() => orders.refetch()} /> : <><MerchantOrderTable orders={orders.data?.results || []} storeId={store.id} onUpdated={() => { client.invalidateQueries({ queryKey: ['merchant-orders', store.id] }); client.invalidateQueries({ queryKey: ['merchant-recent', store.id] }); client.invalidateQueries({ queryKey: ['dashboard', store.id] }); }} /><div className="table-pagination"><span>{orders.data?.count || 0} orders</span><div><button className="icon-button" disabled={!offset} aria-label="Previous orders" onClick={() => setOffset(offset - 20)}><ChevronLeft size={18} /></button><button className="icon-button" disabled={offset + 20 >= (orders.data?.count || 0)} aria-label="Next orders" onClick={() => setOffset(offset + 20)}><ChevronRight size={18} /></button></div></div></>}</>;
}


function MerchantSettings({ store }: { store: Store }) {
  const { notify } = useShop(); const client = useQueryClient(); const [busy, setBusy] = useState(false);
  const profile = useQuery({ queryKey: ['store-profile', store.id], queryFn: () => api<Record<string, string>>(`stores/${store.id}/profile`) });
  const address = useQuery({ queryKey: ['store-address', store.id], queryFn: () => api<Record<string, string>>(`stores/${store.id}/pickup-address`) });
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [bannerUrl, setBannerUrl] = useState<string | null>(null);

  const effectiveAvatar = avatarUrl ?? profile.data?.avatar_url ?? '';
  const effectiveBanner = bannerUrl ?? profile.data?.banner_url ?? '';

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await api(`stores/${store.id}`, 'PATCH', { name: data.name });
      await api(`stores/${store.id}/profile`, 'PATCH', {
        email: data.email,
        bio: data.bio,
        avatar_url: data.avatar_url,
        banner_url: data.banner_url,
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
      </div>
      {profile.isLoading || address.isLoading ? (
        <Loading />
      ) : profile.error || address.error ? (
        <ErrorState error={(profile.error || address.error)!} />
      ) : (
        <form className="form-stack settings-form" onSubmit={submit}>
          <h2>Store branding (X.com style)</h2>
          <div className="form-row">
            <Field label="Profile picture / Logo URL (Circular avatar)">
              <input
                name="avatar_url"
                type="url"
                placeholder="https://…/logo.png"
                defaultValue={profile.data?.avatar_url}
                onChange={e => setAvatarUrl(e.target.value)}
              />
            </Field>
            <Field label="Header / Cover banner URL (Wide banner)">
              <input
                name="banner_url"
                type="url"
                placeholder="https://…/banner.jpg"
                defaultValue={profile.data?.banner_url}
                onChange={e => setBannerUrl(e.target.value)}
              />
            </Field>
          </div>

          {(effectiveAvatar || effectiveBanner) && (
            <div style={{ borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--line)', background: '#fafbf8', marginBottom: '15px' }}>
              <div style={{ height: '110px', background: effectiveBanner ? `url(${effectiveBanner}) center/cover no-repeat` : 'linear-gradient(135deg, #1d9bf0, #173d2c)', position: 'relative' }} />
              <div style={{ padding: '0 20px 16px', display: 'flex', alignItems: 'flex-end', gap: '15px', marginTop: '-35px' }}>
                <div style={{ width: '70px', height: '70px', borderRadius: '50%', border: '3px solid white', overflow: 'hidden', background: '#eef2ea', display: 'grid', placeItems: 'center', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
                  {effectiveAvatar ? <img src={effectiveAvatar} alt={store.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : <span style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--green)' }}>{store.name?.[0]}</span>}
                </div>
                <div style={{ paddingBottom: '4px' }}>
                  <strong style={{ fontSize: '15px', display: 'flex', alignItems: 'center', gap: 6 }}>
                    {store.name}
                    <VerifiedBadge
                      tier={store.is_official ? 'official' : 'starter'}
                      tierData={store.seller_tier}
                      size={17}
                    />
                  </strong>
                  <small className="muted">@{store.username || 'store'}</small>
                </div>
              </div>
            </div>
          )}

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
