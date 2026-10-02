'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useRef, useState, FormEvent, ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Archive, ArrowUpRight, Bell, CheckCheck, ChevronDown, Heart, Inbox, Menu, Search, ShoppingBag, UserRound, X, Truck, ShieldCheck, RotateCcw, UsersRound } from 'lucide-react';
import { api, categories } from '@/lib/api';
import type { NotificationCounts, NotificationItem, Page, User } from '@/lib/types';
import { getFirebaseMessaging, registerPushDevice, unregisterPushDevice } from '@/lib/firebase-messaging';
import { useShop } from './providers';
import { onMessage } from 'firebase/messaging';

export function Shell({ children }: { children: ReactNode }) {
  const { user, cart } = useShop();
  const path = usePathname();
  const merchant = path.startsWith('/merchant');
  const [search, setSearch] = useState('');
  const [menu, setMenu] = useState(false);
  const router = useRouter();
  function submit(event: FormEvent) { event.preventDefault(); router.push(`/shop${search.trim() ? `?search=${encodeURIComponent(search.trim())}` : ''}`); setMenu(false); }
  return <>
    <a className="skip-link" href="#main">Skip to content</a>
    <div className="announcement"><span>Good finds. Great days.</span><span>Free delivery on orders over ₦100,000 <ArrowUpRight size={13} /></span><Link href="/merchant">Sell on Proace <ArrowUpRight size={13} /></Link></div>
    <header className="header"><div className="header-inner">
      <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMenu(!menu)}>{menu ? <X /> : <Menu />}</button>
      <Link href="/" className="wordmark" aria-label="Proace home">proace<span>®</span></Link>
      <form className="search-box" onSubmit={submit}><Search size={19} /><input aria-label="Search products" value={search} onChange={event => setSearch(event.target.value)} placeholder="What are you looking for?" /><button type="submit" aria-label="Search"><ArrowUpRight size={19} /></button></form>
      <div className="header-actions">{user?.is_superuser && <Link href="/admin/staff" className="icon-button" aria-label="Manage staff" title="Manage staff"><UsersRound size={21} /></Link>}<Link href="/account" className="account-link"><UserRound size={21} /><span>{user ? `Hi, ${user.first_name}` : 'Sign in'}</span></Link>{user && <NotificationCenter />}<Link href="/saved" className="icon-button" aria-label="Saved items" title="Saved items"><Heart size={21} /></Link><Link href="/cart" className="bag-link" aria-label={`Shopping bag, ${cart.items.reduce((n, row) => n + row.quantity, 0)} items`}><ShoppingBag size={21} /><span className="bag-text">Bag</span><b>{cart.items.reduce((n, row) => n + row.quantity, 0)}</b></Link></div>
    </div></header>
    {!merchant && <nav className="category-nav" aria-label="Main navigation"><div className="container"><Link className="all-categories" href="/shop"><Menu size={16} />All categories<ChevronDown size={14} /></Link>{categories.slice(0, 5).map(category => <Link key={category.key} href={`/shop?category=${category.key}`}>{category.name}</Link>)}<Link className="deals-link" href="/shop?deals=true">Everyday deals <span /></Link></div></nav>}
    {menu && <div className="mobile-drawer"><form className="search-box" onSubmit={submit}><Search size={18} /><input aria-label="Mobile search products" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search the shop" /><button aria-label="Submit search"><ArrowUpRight size={18} /></button></form><Link onClick={() => setMenu(false)} href="/shop">Shop everything</Link>{categories.map(category => <Link onClick={() => setMenu(false)} key={category.key} href={`/shop?category=${category.key}`}>{category.name}</Link>)}<Link onClick={() => setMenu(false)} href="/merchant">Seller workspace</Link>{user?.is_superuser && <Link onClick={() => setMenu(false)} href="/admin/staff">Manage staff</Link>}</div>}
    <main id="main">{children}</main>
    {!merchant && <><div className="benefits container"><div><Truck /><span><strong>Delivered to your door</strong><small>Free shipping over ₦100,000</small></span></div><div><ShieldCheck /><span><strong>Shop with confidence</strong><small>Secure accounts. Trusted sellers.</small></span></div><div><RotateCcw /><span><strong>Here to help</strong><small>Support when you need it</small></span></div></div>
      <footer><div className="container footer-grid"><div><Link href="/" className="wordmark">proace<span>®</span></Link><p>A little discovery. A lot to love.<br />Your everyday marketplace.</p></div><div><h3>Discover</h3><Link href="/shop">Shop all</Link><Link href="/shop?deals=true">Everyday deals</Link><Link href="/saved">Saved items</Link></div><div><h3>Your Proace</h3><Link href="/account">Your account</Link><Link href="/account/orders">Your orders</Link><Link href="/merchant">Become a seller</Link></div><div><h3>Good to know</h3><Link href="/help">Help & delivery</Link><Link href="/privacy">Privacy policy</Link><Link href="/terms">Terms & returns</Link></div></div><div className="container footer-bottom"><span>© {new Date().getFullYear()} Proace. All rights reserved.</span><span>Nigeria · English · NGN ₦</span></div></footer></>}
  </>;
}

function NotificationCenter() {
  const { user, notify } = useShop();
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<'inbox' | 'archived'>('inbox');
  const [pushStatus, setPushStatus] = useState<'checking' | 'ready' | 'enabled' | 'blocked' | 'unsupported'>('checking');
  const [pushBusy, setPushBusy] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const notifyRef = useRef(notify);
  const client = useQueryClient();
  const counts = useQuery({ queryKey: ['notifications', 'counts'], queryFn: () => api<NotificationCounts>('notifications/counts'), refetchInterval: open ? false : 45000 });
  const list = useQuery({ queryKey: ['notifications', view], queryFn: () => api<Page<NotificationItem>>(view === 'archived' ? 'notifications/archived' : 'notifications?limit=8'), enabled: open });
  const refresh = async () => { await Promise.all([client.invalidateQueries({ queryKey: ['notifications'] }), client.invalidateQueries({ queryKey: ['notifications', 'counts'] })]); };
  const action = useMutation({ mutationFn: ({ id, path }: { id?: number; path: string }) => api(id ? `notifications/${id}/${path}` : `notifications/${path}`, 'POST', {}), onSuccess: refresh, onError: error => notify((error as Error).message, true) });
  useEffect(() => { notifyRef.current = notify; }, [notify]);
  useEffect(() => {
    let active = true;
    let unsubscribe: (() => void) | undefined;

    async function subscribeToPush() {
      try {
        const messaging = await getFirebaseMessaging();
        if (!active) return;
        if (!messaging) {
          setPushStatus('unsupported');
          return;
        }
        setPushStatus(Notification.permission === 'denied'
          ? 'blocked'
          : localStorage.getItem('proace-fcm-token')
            && localStorage.getItem('proace-fcm-owner') === String(user?.id)
            && Notification.permission === 'granted'
            ? 'enabled'
            : 'ready');
        unsubscribe = onMessage(messaging, payload => {
          if (payload.data?.recipient_id !== String(client.getQueryData<User>(['me'])?.id)) return;
          void refresh();
          if (payload.data.title) notifyRef.current(payload.data.title);
        });
      } catch (error) {
        if (active) {
          setPushStatus(
            'Notification' in window && Notification.permission === 'denied'
              ? 'blocked'
              : 'ready',
          );
          notifyRef.current((error as Error).message, true);
        }
      }
    }

    void subscribeToPush();
    return () => {
      active = false;
      unsubscribe?.();
    };
  }, [client, user?.id]);
  async function togglePush() {
    if (!user) return;
    setPushBusy(true);
    try {
      if (pushStatus === 'enabled') {
        await unregisterPushDevice();
        setPushStatus('ready');
        notify('Browser push notifications disabled');
      } else {
        await registerPushDevice(user.id);
        setPushStatus('enabled');
        notify('Browser push notifications enabled');
      }
    } catch (error) {
      notify((error as Error).message, true);
      if ('Notification' in window && Notification.permission === 'denied') setPushStatus('blocked');
    } finally {
      setPushBusy(false);
    }
  }
  useEffect(() => { function close(event: MouseEvent) { if (panel.current && !panel.current.contains(event.target as Node)) setOpen(false); } if (open) document.addEventListener('mousedown', close); return () => document.removeEventListener('mousedown', close); }, [open]);
  const unread = counts.data?.unread || 0;
  const items = list.data?.results || [];
  return <div className="notification-center" ref={panel}>
    <button className={`icon-button notification-trigger ${open ? 'active' : ''}`} aria-label={`${unread} unread notifications`} aria-expanded={open} onClick={() => setOpen(value => !value)} title="Notifications"><Bell size={20} />{unread > 0 && <b>{unread > 9 ? '9+' : unread}</b>}</button>
    {open && <section className="notification-panel" aria-label="Notifications">
      <div className="notification-head"><div><h2>Notifications</h2><span>{unread ? `${unread} unread` : 'All caught up'}</span></div><button className="icon-button" aria-label="Close notifications" onClick={() => setOpen(false)}><X size={17} /></button></div>
      <div className="notification-tabs"><button className={view === 'inbox' ? 'active' : ''} onClick={() => setView('inbox')}>Inbox</button><button className={view === 'archived' ? 'active' : ''} onClick={() => setView('archived')}>Archived</button></div>
      {(pushStatus === 'ready' || pushStatus === 'enabled') && <button className="notification-push" disabled={pushBusy} aria-pressed={pushStatus === 'enabled'} onClick={() => void togglePush()}>{pushBusy ? 'Updating browser alerts…' : pushStatus === 'enabled' ? 'Turn off browser alerts' : 'Enable browser alerts'}</button>}
      {pushStatus === 'blocked' && <p className="notification-push-status">Browser alerts are blocked in your browser settings.</p>}
      {view === 'inbox' && <button className="notification-read-all" disabled={!unread || action.isPending} onClick={() => action.mutate({ path: 'mark-all-read' })}><CheckCheck size={15} />Mark all read</button>}
      <div className="notification-list">{list.isLoading ? <div className="notification-empty">Loading notifications…</div> : list.error ? <div className="notification-empty error">Couldn’t load notifications.</div> : items.length ? items.map(item => <article className={`notification-item ${item.unread ? 'unread' : ''}`} key={item.id}>
        <span className={`notification-dot ${item.level}`} />
        <div><h3>{item.verb}</h3>{item.description && <p>{item.description}</p>}<small>{timeAgo(item.timestamp)}</small></div>
        <div className="notification-actions">{view === 'archived' ? <button title="Restore" aria-label="Restore notification" disabled={action.isPending} onClick={() => action.mutate({ id: item.id, path: 'restore' })}><Inbox size={15} /></button> : <><button title={item.unread ? 'Mark read' : 'Mark unread'} aria-label={item.unread ? 'Mark read' : 'Mark unread'} disabled={action.isPending} onClick={() => action.mutate({ id: item.id, path: item.unread ? 'mark-read' : 'mark-unread' })}><CheckCheck size={15} /></button><button title="Archive" aria-label="Archive notification" disabled={action.isPending} onClick={() => action.mutate({ id: item.id, path: 'archive' })}><Archive size={15} /></button></>}</div>
      </article>) : <div className="notification-empty"><Inbox size={23} /><span>{view === 'archived' ? 'No archived notifications.' : 'No notifications yet.'}</span></div>}</div>
    </section>}
  </div>;
}

function timeAgo(value: string) {
  const seconds = Math.max(1, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return 'Just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
