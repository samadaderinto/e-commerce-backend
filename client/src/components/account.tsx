'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, ReactNode, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ArrowRight, Check, ChevronRight, Eye, EyeOff, Heart, LockKeyhole, LogOut, MapPin, Package, Plus, RotateCcw, ShoppingBag, Store, Trash2, UserRound, WalletCards } from 'lucide-react';
import { api, money } from '@/lib/api';
import type { Address, Order, User, UserWallet } from '@/lib/types';
import { useShop } from './providers';
import { Empty, ErrorState, Field, Loading, ProductImage, Status } from './ui';

export function Gate({ children, next = '/account' }: { children: ReactNode; next?: string }) {
  const { user, sessionLoading } = useShop();
  if (sessionLoading) return <Loading />;
  if (!user) return <Empty title="Make yourself at home" text="Sign in to keep your orders, addresses and good finds together." href={`/login?next=${encodeURIComponent(next)}`} label="Sign in" icon={<UserRound size={38} />} />;
  return <>{children}</>;
}

export function AuthPage({ mode }: { mode: string }) {
  const { login, user, notify } = useShop();
  const router = useRouter();
  const params = useSearchParams();
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const isRegister = mode === 'register';
  const isForgot = mode === 'forgot-password';
  const isReset = mode === 'reset-password';
  const verify = useQuery({ queryKey: ['verify', params.get('token')], queryFn: () => api<{detail: string}>('auth/verify', 'POST', { token: params.get('token') }), enabled: mode === 'verify-email', retry: false, staleTime: Infinity });
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const data = Object.fromEntries(new FormData(event.currentTarget)) as Record<string, string>;
    try {
      if (isRegister) { const result = await api<{detail: string}>('auth/register', 'POST', data); setMessage(result.detail); }
      else if (isForgot) { const result = await api<{detail: string}>('auth/forgot', 'POST', data); setMessage(result.detail); }
      else if (isReset) { const result = await api<{detail: string}>('auth/reset', 'POST', { ...data, uid: params.get('uid'), token: params.get('token') }); setMessage(result.detail); }
      else { await login(data.email, data.password); const next = params.get('next') || '/account'; router.push(next.startsWith('/') && !next.startsWith('//') && !next.includes('\\') ? next : '/account'); }
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  return <div className="auth-page container"><div className="auth-story"><span className="eyebrow">YOUR EVERYDAY, A LITTLE BETTER.</span><h2>Good things<br />start here.</h2><p>A place for your favourite finds.<br />And the ones you haven&apos;t found yet.</p><div className="auth-photo"><img src="https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=85" alt="A minimal watch on a light background" /></div><span className="wordmark">proace<span>®</span></span></div><div className="auth-form-wrap">
    {mode === 'verify-email' ? <><div className="auth-icon"><Check /></div><h1>Email verification</h1>{verify.isLoading ? <Loading /> : verify.error ? <p className="form-error">{verify.error.message}</p> : <p>{verify.data?.detail}</p>}<Link className="button" href="/login">Continue to sign in <ArrowRight size={17} /></Link></> : message ? <><div className="auth-icon"><Check /></div><h1>{isReset ? 'A fresh start' : 'Check your inbox'}</h1><p>{message}</p><Link className="button" href="/login">Back to sign in <ArrowRight size={17} /></Link></> : <><span className="eyebrow green">{isRegister ? 'JOIN THE GOOD FINDS' : isForgot || isReset ? 'LET’S GET YOU BACK IN' : 'GOOD TO SEE YOU AGAIN'}</span><h1>{isRegister ? 'Make it yours.' : isForgot ? 'Forgot your password?' : isReset ? 'Set a new password' : 'Welcome back.'}</h1><p>{isRegister ? 'Create an account for a little more ProAce.' : isForgot ? 'We’ll send a reset link to your email address.' : isReset ? 'Choose a strong password for your account.' : 'Sign in to your everyday marketplace.'}</p><form onSubmit={submit} className="form-stack">{isRegister && <div className="form-row"><Field label="First name"><input name="first_name" required autoComplete="given-name" maxLength={30} /></Field><Field label="Last name"><input name="last_name" required autoComplete="family-name" maxLength={30} /></Field></div>}{!isReset && <Field label="Email address"><input name="email" type="email" required autoComplete="email" placeholder="you@example.com" /></Field>}{isRegister && <Field label="Phone number"><input name="phone1" type="tel" autoComplete="tel" required placeholder="+1 301 325 1550" /></Field>}{!isForgot && <Field label="Password"><div className="password-input"><input name="password" type={show ? 'text' : 'password'} required minLength={isRegister || isReset ? 8 : 1} maxLength={128} autoComplete={isRegister || isReset ? 'new-password' : 'current-password'} placeholder={isRegister ? 'At least 8 characters' : 'Your password'} /><button type="button" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}>{show ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></Field>}{!isRegister && !isForgot && !isReset && <Link href="/forgot-password" className="forgot-link">Forgot password?</Link>}{error && <p className="form-error" role="alert">{error}</p>}<button className="button" disabled={busy}>{busy ? 'One moment…' : isRegister ? 'Create account' : isForgot ? 'Send reset link' : isReset ? 'Update password' : 'Sign in'}<ArrowRight size={17} /></button></form><p className="auth-switch">{isRegister ? 'Already have an account?' : 'New around here?'} <Link href={isRegister ? '/login' : '/register'}>{isRegister ? 'Sign in' : 'Create an account'}</Link></p><p className="fine-print">By continuing, you agree to our <Link href="/terms">Terms</Link> and <Link href="/privacy">Privacy Policy</Link>.</p></>}
    </div></div>;
}

export function AddressForm({ onSaved, onCancel }: { onSaved: (address: Address) => void; onCancel?: () => void }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const client = useQueryClient();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try { const address = await api<Address>('addresses', 'POST', { ...data, is_default: data.is_default === 'on' }); await client.invalidateQueries({ queryKey: ['addresses'] }); onSaved(address); }
    catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  return <form className="form-stack address-form" onSubmit={submit}><h3>Add a delivery address</h3><Field label="Street address"><input name="address" autoComplete="street-address" required placeholder="House number and street name" /></Field><div className="form-row"><Field label="City"><input name="city" autoComplete="address-level2" required /></Field><Field label="State / region"><input name="state" autoComplete="address-level1" required maxLength={30} /></Field></div><div className="form-row"><Field label="Country"><input name="country" autoComplete="country-name" required maxLength={30} /></Field><Field label="Postal code"><input name="zip" autoComplete="postal-code" required maxLength={10} /></Field></div><label className="check-row"><input type="checkbox" name="is_default" defaultChecked />Make this my default address</label>{error && <p className="form-error">{error}</p>}<div className="form-actions"><button className="button" disabled={busy}>{busy ? 'Saving…' : 'Save address'}</button>{onCancel && <button type="button" className="button secondary" onClick={onCancel}>Cancel</button>}</div></form>;
}

export function AccountPage({ section = 'overview' }: { section?: string }) {
  const { user, logout, notify } = useShop(); const router = useRouter(); const client = useQueryClient();
  const [adding, setAdding] = useState(false); const [busy, setBusy] = useState(false);
  const orders = useQuery({ queryKey: ['orders', user?.id], queryFn: () => api<Order[]>('orders'), enabled: !!user });
  const addresses = useQuery({ queryKey: ['addresses', user?.id], queryFn: () => api<Address[]>('addresses'), enabled: !!user });
  const wallet = useQuery({ queryKey: ['wallet', user?.id], queryFn: () => api<UserWallet>('wallet'), enabled: !!user });
  const links = [['overview', 'Overview', UserRound], ['orders', 'My orders', Package], ['wallet', 'ProAce Wallet', WalletCards], ['addresses', 'Address book', MapPin], ['profile', 'Personal details', UserRound]] as const;
  async function save(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); try { const updated = await api<User>('me', 'PATCH', Object.fromEntries(new FormData(event.currentTarget))); client.setQueryData(['me'], updated); notify('Your details have been updated'); } catch (error) { notify((error as Error).message, true); } finally { setBusy(false); } }
  return <Gate><div className="container account-page"><div className="breadcrumb"><Link href="/">Home</Link><ChevronRight size={12} /><span>My account</span></div><div className="account-layout"><aside className="account-sidebar"><div className="account-avatar">{user?.first_name?.[0] || 'P'}</div><h2>{user?.first_name} {user?.last_name}</h2><p>{user?.email}</p><nav>{links.map(([key, name, Icon]) => <Link className={section === key ? 'active' : ''} key={key} href={key === 'overview' ? '/account' : `/account/${key}`}><Icon size={19} />{name}</Link>)}<Link href="/saved"><Heart size={19} />Saved items</Link><Link href="/merchant"><Store size={19} />Seller workspace<ArrowRight size={15} /></Link><button onClick={async () => { try { await logout(); router.push('/'); } catch (error) { notify((error as Error).message, true); } }}><LogOut size={19} />Sign out</button></nav></aside><div className="account-content">
    {section === 'overview' ? <><span className="eyebrow green">YOUR LITTLE CORNER OF PROACE</span><h1>Hello, {user?.first_name}.</h1><p className="muted">All your good finds, in one place.</p><div className="account-stat-grid"><Link href="/account/orders"><Package /><strong>{orders.data?.length || 0}</strong><span>Orders</span><ArrowRight size={17} /></Link><Link href="/account/wallet"><WalletCards /><strong>{money(wallet.data?.balance || '0.00')}</strong><span>Wallet balance</span><ArrowRight size={17} /></Link><Link href="/account/addresses"><MapPin /><strong>{addresses.data?.length || 0}</strong><span>Saved addresses</span><ArrowRight size={17} /></Link></div><div className="section-heading"><h2>Recent orders</h2><Link className="text-link" href="/account/orders">View all <ArrowRight size={16} /></Link></div><OrderList orders={orders.data?.slice(0, 3)} loading={orders.isLoading} error={orders.error} /></> : section === 'orders' ? <><h1>My orders</h1><p className="muted">Keep an eye on your latest finds.</p><OrderList orders={orders.data} loading={orders.isLoading} error={orders.error} /></> : section === 'wallet' ? <div><span className="eyebrow green">STORE CREDIT & BALANCES</span><h1>ProAce Wallet</h1><p className="muted">Use your available balance for instant 1-click purchases and immediate refund store credit.</p><div className="account-stat-grid" style={{ gridTemplateColumns: '1fr' }}><div className="stat-item stat-0" style={{ padding: '1.5rem', background: '#f6fbf8', borderRadius: '12px', border: '1px solid #c9ebd8' }}><div><span style={{ fontWeight: 600 }}>Available Store Balance</span><WalletCards size={24} color="#1b7340" /></div><strong style={{ fontSize: '2.25rem', color: '#1b7340', margin: '0.5rem 0' }}>{money(wallet.data?.balance || '0.00')}</strong><small>Automatically available at checkout to pay for any product.</small></div></div><div className="section-heading" style={{ marginTop: '2rem' }}><h2>Recent wallet activity</h2></div>{wallet.isLoading ? <Loading /> : wallet.error ? <ErrorState error={wallet.error} /> : !wallet.data?.transactions?.length ? <Empty title="No transactions yet" text="When you receive store credit or pay with your wallet, activity appears here." /> : <div className="table-scroll"><table><thead><tr><th>Date</th><th>Type</th><th>Source</th><th>Description</th><th>Amount</th></tr></thead><tbody>{wallet.data.transactions.map(tx => <tr key={tx.id}><td>{new Date(tx.created).toLocaleDateString()}</td><td><span className={tx.transaction_type === 'credit' ? 'status active' : 'status'}>{tx.transaction_type.toUpperCase()}</span></td><td>{tx.source}</td><td>{tx.description}</td><td style={{ fontWeight: 600, color: tx.transaction_type === 'credit' ? '#1b7340' : '#111' }}>{tx.transaction_type === 'credit' ? `+${money(tx.amount)}` : `-${money(tx.amount)}`}</td></tr>)}</tbody></table></div>}</div> : section === 'addresses' ? <><div className="section-heading"><h1>Address book</h1><button className="button" onClick={() => setAdding(true)}><Plus size={17} />Add address</button></div>{adding && <AddressForm onSaved={() => { setAdding(false); notify('Address saved'); }} onCancel={() => setAdding(false)} />}{addresses.isLoading ? <Loading /> : addresses.error ? <ErrorState error={addresses.error} /> : !addresses.data?.length && !adding ? <div className="empty-state"><MapPin size={35} /><h2>Where should we send your finds?</h2><p>Add your first address to make checkout a little easier.</p></div> : <div className="address-grid">{addresses.data?.map(address => <article className="address-card" key={address.id}><div><MapPin size={18} />{address.is_default && <span className="status">Default address</span>}<button className="icon-button" aria-label={`Delete ${address.address}`} onClick={async () => { try { await api('addresses', 'DELETE', { id: address.id }); await client.invalidateQueries({ queryKey: ['addresses'] }); notify('Address removed'); } catch (error) { notify((error as Error).message, true); } }}><Trash2 size={16} /></button></div><strong>{address.address}</strong><p>{address.city}, {address.state}<br />{address.country}, {address.zip}</p></article>)}</div>}</> : <><h1>Personal details</h1><p className="muted">A little about you.</p><form className="form-stack profile-form" onSubmit={save}><div className="form-row"><Field label="First name"><input name="first_name" defaultValue={user?.first_name} required maxLength={30} /></Field><Field label="Last name"><input name="last_name" defaultValue={user?.last_name} required maxLength={30} /></Field></div><Field label="Email address"><input value={user?.email || ''} disabled /></Field><Field label="Phone number"><input type="tel" name="phone1" defaultValue={user?.phone1} required /></Field><button className="button" disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</button><Link className="text-link" href="/forgot-password">Change your password <ArrowRight size={16} /></Link></form></>}
    </div></div></div></Gate>;
}

function OrderList({ orders, loading, error }: { orders?: Order[]; loading: boolean; error: Error | null }) {
  if (loading) return <Loading />; if (error) return <ErrorState error={error} />; if (!orders?.length) return <Empty title="Your first find is waiting" text="When you place an order, you can follow it right here." />;
  return <div className="order-list">{orders.map(order => <Link href={`/orders/${order.id}`} className="order-row" key={order.id}><ProductImage src={order.items[0]?.image} alt={order.items[0]?.title || 'Order'} /><div><strong>{order.reference}</strong><p>{order.items[0]?.title || 'Your order'}{order.items.length > 1 ? ` + ${order.items.length - 1} more` : ''}</p><small>{new Date(order.created).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}</small></div><Status value={order.status} /><strong>{money(order.total)}</strong><ChevronRight size={18} /></Link>)}</div>;
}

export function OrderPage({ id }: { id: string }) {
  const { user, notify } = useShop(); const params = useSearchParams(); const client = useQueryClient();
  const order = useQuery({ queryKey: ['order', id, user?.id], queryFn: () => api<Order>(`orders/${id}`), enabled: !!user });
  const [requestingRefund, setRequestingRefund] = useState(false);
  const [reason, setReason] = useState('');
  const [refundType, setRefundType] = useState('store_credit');
  const [busy, setBusy] = useState(false);

  const data = order.data;
  const isAllDigital = data?.items?.every(item => item.is_digital) ?? false;
  const hasPhysical = data?.items?.some(item => !item.is_digital) ?? false;
  const createdTime = data ? new Date(data.created).getTime() : 0;
  const daysElapsed = (Date.now() - createdTime) / (1000 * 60 * 60 * 24);
  const isWithin7Days = daysElapsed <= 7;
  const canRequestRefund = hasPhysical && isWithin7Days && !['refunded', 'refund_requested', 'cancelled'].includes(data?.status || '');

  async function submitRefund(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try {
      await api(`orders/${id}/refund`, 'POST', { reason: reason || 'Customer requested return', refund_type: refundType });
      await client.invalidateQueries({ queryKey: ['order', id] });
      await client.invalidateQueries({ queryKey: ['orders'] });
      await client.invalidateQueries({ queryKey: ['wallet'] });
      notify('Refund request submitted. We will review your return within 1–2 business days.');
      setRequestingRefund(false);
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  return <Gate next={`/orders/${id}`}><div className="container order-detail"><Link className="text-link" href="/account/orders"><ArrowLeft size={16} />All orders</Link>{order.isLoading ? <Loading /> : order.error ? <ErrorState error={order.error} /> : data && <><div className="order-success"><div className="success-icon"><Check size={30} /></div><span className="eyebrow green">{params.has('placed') ? 'A GOOD FIND, INDEED' : 'YOUR ORDER'}</span><h1>{params.has('placed') ? 'It’s on the list.' : data.reference}</h1><p>{params.has('placed') ? `Your order ${data.reference} is confirmed. Thank you for shopping with ProAce.` : `Placed on ${new Date(data.created).toLocaleDateString()}`}</p><Status value={data.status} /></div><div className="order-progress">{['confirmed', 'shipped', 'delivered'].map((step, index) => <div key={step} className={['confirmed', 'shipped', 'delivered'].indexOf(data.status) >= index ? 'done' : ''}><span><Check size={15} /></span><strong>{step}</strong></div>)}</div><div className="checkout-layout"><section><h2>Your finds</h2>{data.items.map((item, index) => <div className="order-item" key={index}><ProductImage src={item.image} alt={item.title} /><div><Link href={`/products/${item.product}`}>{item.title}</Link><p>Quantity: {item.quantity}</p>{item.is_digital ? <div className="digital-badge"><small>Digital download (Non-refundable once downloaded)</small>{item.download_url && <a className="text-link" href={item.download_url} target="_blank" rel="noreferrer">Download file <ArrowRight size={14} /></a>}</div> : null}</div><strong>{money(Number(item.unit_price) * item.quantity)}</strong></div>)}</section><aside className="order-summary"><h2>Order details</h2><h4>Deliver to</h4><p>{data.address.address}<br />{data.address.city}, {data.address.state}<br />{data.address.country} {data.address.zip}</p><h4>Payment status</h4><p>{data.payment_type === 'user_wallet' ? 'ProAce Wallet Balance (Paid)' : data.payment_type === 'stripe_wallet' ? 'Cards, Stripe & Wallet (Paid)' : data.payment_type === 'card' ? 'Card (Paid)' : 'Online Payment (Paid)'}</p><div className="summary-total"><span>Total</span><strong>{money(data.total)}</strong></div>{canRequestRefund && !requestingRefund && <button className="button secondary" onClick={() => setRequestingRefund(true)}><RotateCcw size={16} />Request a return / refund</button>}{requestingRefund && <form className="form-stack" onSubmit={submitRefund} style={{ marginTop: '1rem' }}><h4>Request refund (7-day window)</h4><Field label="Refund Destination"><select value={refundType} onChange={e => setRefundType(e.target.value)}><option value="store_credit">Instant ProAce Store Credit (Wallet)</option><option value="original_payment">Original Payment Method (Card / Bank)</option></select></Field><Field label="Reason for return"><textarea value={reason} onChange={e => setReason(e.target.value)} required rows={3} placeholder="Please provide details..." /></Field><div className="form-row"><button className="button" disabled={busy}>{busy ? 'Submitting…' : 'Submit request'}</button><button type="button" className="button secondary" onClick={() => setRequestingRefund(false)}>Cancel</button></div></form>}{hasPhysical && !isWithin7Days && <p className="fine-print">The 7-day return window for this order has closed.</p>}{isAllDigital && <p className="fine-print">Digital products are non-refundable. For file issues, contact support@proace.com.</p>}<Link className="button" href="/shop">Keep discovering <ArrowRight size={16} /></Link></aside></div></>}</div></Gate>;
}

