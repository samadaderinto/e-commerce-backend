'use client';

import { notificationAction } from '@/lib/notification-action';

import { presentNotificationOnce } from '@/lib/notification-presentation';

import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useRef, useState, FormEvent, ReactNode } from 'react';
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Activity, Archive, ArrowRight, ArrowUpRight, Bell, Camera, ChartNoAxesCombined, CheckCheck, ChevronDown, DollarSign, Heart, Inbox, Landmark, LogOut, Menu, Plus, RotateCcw, Search, Settings, ShieldCheck, ShoppingBag, Store as StoreIcon, Truck, UserRound, UsersRound, X } from 'lucide-react';
import { api, categories } from '@/lib/api';
import type { NotificationCounts, NotificationItem, Page, Store, User } from '@/lib/types';
import { fetchPushDeviceStatus, getFirebaseMessaging, pushDeviceChangeEvent, registerPushDevice, unregisterPushDevice } from '@/lib/firebase-messaging';
import { useShop } from './providers';
import { ThemeToggle } from './theme';
import { business, contactLinks } from '@/lib/business';
import { ResponsiveMediaImage } from './ui';
import { VisualSearchModal } from './visual-search-modal';

export function Shell({ children }: { children: ReactNode }) {
  const { user, cart, sessionLoading } = useShop();
  const path = usePathname();
  const params = useSearchParams();
  const merchant = path.startsWith('/merchant');
  const [search, setSearch] = useState('');
  const [visualSearchOpen, setVisualSearchOpen] = useState(false);
  const [menu, setMenu] = useState(false);
  const router = useRouter();
  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const target: string = `/shop${search.trim() ? `?search=${encodeURIComponent(search.trim())}` : ''}`;
    if (path === '/shop') {
      window.history.pushState(null, '', target);
    } else {
      router.push(target);
    }
    setMenu(false);
  }
  const backoffice = !!(user?.is_staff || user?.is_superuser || user?.is_business_admin);
  const previewMode = backoffice && (params.get('preview') === '1' || (path === '/shop' && Boolean(params.get('store')))) && (path === '/shop' || path.startsWith('/products/'));
  const consumerRoute = !previewMode && (
    path === '/' ||
    /^\/(cart|checkout|saved|orders|shop|products|stores|login)(\/|$)/.test(path) ||
    /^\/account\/(orders|wallet|addresses)(\/|$)/.test(path)
  );
  useEffect(() => {
    if (user?.must_change_password && path !== '/change-password') router.replace('/change-password');
    else if (backoffice && consumerRoute && !user?.must_change_password) router.replace('/admin');
  }, [user?.must_change_password, backoffice, consumerRoute, path, router]);
  if (sessionLoading) return <div className="container section" role="status">Loading your workspace…</div>;
  if (user?.must_change_password) return <MandatoryPasswordChange />;
  if (backoffice) {
    const links = [
      { href: '/admin', label: 'Overview', icon: ChartNoAxesCombined },
      { href: '/admin/orders', label: 'Orders', icon: Truck },
      { href: '/admin/coupons', label: 'Coupons', icon: Archive },
      { href: '/admin/taxes', label: 'Taxes', icon: Landmark },
      { href: '/admin/refunds', label: 'Refunds', icon: RotateCcw },
      { href: '/admin/stores', label: 'Stores', icon: StoreIcon },
      { href: '/admin/payouts', label: 'Payouts', icon: DollarSign },
      { href: '/admin/users', label: 'Users', icon: UserRound },
      { href: '/admin/affiliates', label: 'Affiliates', icon: UsersRound },
      ...((user?.is_superuser || user?.is_business_admin)
        ? [{ href: '/admin/commission', label: 'Commission', icon: DollarSign }]
        : []),
      ...((user?.is_superuser || user?.is_business_admin)
        ? [{ href: '/admin/staff', label: 'Staff', icon: UsersRound }]
        : []),
    ];
    return (
      <>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <header className="header backoffice-header">
          <div className="header-inner">
            <Link className="wordmark" href="/admin">
              proace<span>®</span>
            </Link>
            <span className="backoffice-label">Backoffice</span>
            <div className="backoffice-tools">
              <ThemeToggle />
              <AccountMenu />
              <NotificationCenter />
            </div>
          </div>
          <nav className="backoffice-nav" aria-label="Back-office navigation">
            {links.map(({ href, label, icon: Icon }) => {
              const active =
                href === '/admin' ? path === href : path === href || path.startsWith(`${href}/`);
              return (
                <Link key={href} href={href} aria-current={active ? 'page' : undefined}>
                  <Icon size={17} />
                  <span>{label}</span>
                </Link>
              );
            })}
            {user?.is_superuser && (
              <a
                href={process.env.NEXT_PUBLIC_GRAFANA_URL || 'http://127.0.0.1:3002'}
                target="_blank"
                rel="noreferrer"
                title="Open Grafana Live Telemetry & Metrics (Technical admin sign-in required)"
              >
                <Activity size={17} />
                <span>Live Metrics</span>
                <ArrowUpRight size={14} />
              </a>
            )}
          </nav>
        </header>
        <main id="main">
          {consumerRoute ? <div className="container section">Opening dashboard…</div> : children}
        </main>
      </>
    );
  }

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="announcement">
        <span>Good finds. Great days.</span>
        <span>
          Physical delivery: US only · Digital: worldwide <ArrowUpRight size={13} />
        </span>
        <Link href="/merchant">
          Sell on ProAce <ArrowUpRight size={13} />
        </Link>
      </div>

      <header className="header">
        <div className="header-inner">
          <button
            className="icon-button mobile-menu"
            aria-label="Open navigation"
            onClick={() => setMenu(!menu)}
          >
            {menu ? <X /> : <Menu />}
          </button>
          <Link href="/" className="wordmark" aria-label="ProAce home">
            proace<span>®</span>
          </Link>
          <form className="search-box" onSubmit={submit}>
            <Search size={19} />
            <input
              aria-label="Search products"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="What are you looking for?"
            />
            <button
              type="button"
              className="search-camera-btn"
              onClick={() => setVisualSearchOpen(true)}
              title="AI Visual Lens • Shop The Look"
              aria-label="Search by image or shop the look"
            >
              <Camera size={18} />
            </button>
            <button type="submit" aria-label="Search">
              <ArrowUpRight size={19} />
            </button>
          </form>
          <div className="header-actions">
            <ThemeToggle />
            {(user?.is_staff || user?.is_superuser) && (
              <Link
                href="/admin"
                className="icon-button"
                aria-label="Platform dashboard"
                title="Platform dashboard"
              >
                <ChartNoAxesCombined size={21} />
              </Link>
            )}
            {(user?.is_superuser || user?.is_business_admin) && (
              <Link
                href="/admin/staff"
                className="icon-button"
                aria-label="Manage staff"
                title="Manage staff"
              >
                <UsersRound size={21} />
              </Link>
            )}
            <AccountMenu />
            {user && <NotificationCenter />}
            {!user?.is_staff && !user?.is_superuser && !user?.is_business_admin && (
              <>
                <Link
                  href="/saved"
                  className="icon-button"
                  aria-label="Saved items"
                  title="Saved items"
                >
                  <Heart size={21} />
                </Link>
                <Link
                  href="/cart"
                  className="bag-link"
                  aria-label={`Shopping bag, ${cart.items.reduce((n, row) => n + row.quantity, 0)} items`}
                >
                  <ShoppingBag size={21} />
                  <span className="bag-text">Bag</span>
                  <b>{cart.items.reduce((n, row) => n + row.quantity, 0)}</b>
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {!merchant && (
        <nav className="category-nav" aria-label="Main navigation">
          <div className="container">
            <Link className="all-categories" href="/shop">
              <Menu size={16} />
              All categories
              <ChevronDown size={14} />
            </Link>
            {categories.slice(0, 5).map((category) => (
              <Link key={category.key} href={`/shop?category=${category.key}`}>
                {category.name}
              </Link>
            ))}
            <Link className="deals-link" href="/shop?deals=true">
              Everyday deals <span />
            </Link>
          </div>
        </nav>
      )}

      {menu && (
        <div className="mobile-drawer">
          <form className="search-box" onSubmit={submit}>
            <Search size={18} />
            <input
              aria-label="Mobile search products"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search the shop"
            />
            <button aria-label="Submit search">
              <ArrowUpRight size={18} />
            </button>
          </form>
          <Link onClick={() => setMenu(false)} href="/shop">
            Shop everything
          </Link>
          {categories.map((category) => (
            <Link
              onClick={() => setMenu(false)}
              key={category.key}
              href={`/shop?category=${category.key}`}
            >
              {category.name}
            </Link>
          ))}
          <Link onClick={() => setMenu(false)} href="/settings">
            App settings
          </Link>
          <Link onClick={() => setMenu(false)} href="/merchant">
            Seller workspace
          </Link>
          {(user?.is_staff || user?.is_superuser) && (
            <Link onClick={() => setMenu(false)} href="/admin">
              Platform dashboard
            </Link>
          )}
          {(user?.is_superuser || user?.is_business_admin) && (
            <Link onClick={() => setMenu(false)} href="/admin/staff">
              Manage staff
            </Link>
          )}
        </div>
      )}

      <main id="main">{children}</main>

      {!merchant && (
        <>
          <div className="benefits container">
            <div>
              <Truck />
              <span>
                <strong>US physical delivery</strong>
                <small>Physical goods currently ship only within the US</small>
              </span>
            </div>
            <div>
              <ShieldCheck />
              <span>
                <strong>Digital goods worldwide</strong>
                <small>Eligible downloads are available globally</small>
              </span>
            </div>
            <div>
              <RotateCcw />
              <span>
                <strong>Here to help</strong>
                <small>{business.supportSchedule}</small>
              </span>
            </div>
          </div>

          <footer>
            <div className="container footer-grid">
              <div>
                <Link href="/" className="wordmark">
                  proace<span>®</span>
                </Link>
                <p>
                  {business.publicName}
                  <br />A US marketplace based in {business.location}, with digital products
                  available worldwide.
                </p>
                <a href={contactLinks.supportEmail}>{business.supportEmail}</a>
                <span>Phone: {business.mainPhone}</span>
                <a href={contactLinks.whatsapp} target="_blank" rel="noreferrer">
                  WhatsApp: {business.whatsapp}
                </a>
              </div>
              <div>
                <h3>Discover</h3>
                <Link href="/shop">Shop all</Link>
                <Link href="/shop?deals=true">Everyday deals</Link>
                <Link href="/saved">Saved items</Link>
              </div>
              <div>
                <h3>Your ProAce</h3>
                <Link href="/account">Your account</Link>
                <Link href="/settings">App settings</Link>
                <Link href="/account/orders">Your orders</Link>
                <Link href="/merchant">Become a seller</Link>
              </div>
              <div>
                <h3>Good to know</h3>
                <Link href="/help">Help & delivery</Link>
                <Link href="/privacy">Privacy policy</Link>
                <Link href="/terms">Terms & returns</Link>
              </div>
            </div>
            <div className="container footer-bottom">
              <span>
                © {new Date().getFullYear()} {business.legalName}. All rights reserved.
              </span>
              <span>US physical delivery · Worldwide digital · USD $</span>
            </div>
          </footer>
        </>
      )}
      <VisualSearchModal
        isOpen={visualSearchOpen}
        onClose={() => setVisualSearchOpen(false)}
      />
    </>
  );
}

function NotificationCenter() {
  const { user, notify } = useShop();
  const [open, setOpen] = useState(false);
  const [pushStatus, setPushStatus] = useState<
    'checking' | 'ready' | 'enabled' | 'blocked' | 'unsupported' | 'unavailable'
  >('checking');
  const [pushBusy, setPushBusy] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const notifyRef = useRef(notify);
  const client = useQueryClient();
  const counts = useQuery({
    queryKey: ['notifications', 'counts', user?.id],
    queryFn: () => api<NotificationCounts>('notifications/counts'),
    refetchInterval: open ? false : 45000,
  });

  const list = useQuery({
    queryKey: ['notifications', 'popup-global', user?.id],
    queryFn: () => api<Page<NotificationItem>>('notifications?limit=8&ordering=-timestamp'),
    enabled: open,
  });

  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['notifications'] }),
      client.invalidateQueries({ queryKey: ['notifications', 'counts'] }),
      client.invalidateQueries({ queryKey: ['notifications', 'filters'] }),
    ]);
  };

  const action = useMutation({
    mutationFn: ({ id, path }: { id?: number; path: string }) =>
      api(id ? `notifications/${id}/${path}` : `notifications/${path}`, 'POST', {}),
    onSuccess: refresh,
    onError: (error) => notify((error as Error).message, true),
  });

  useEffect(() => {
    notifyRef.current = notify;
  }, [notify]);
  useEffect(() => {
    function syncPushStatus(): void {
      if (!('Notification' in window)) {
        setPushStatus('unsupported');
        return;
      }
      if (Notification.permission === 'denied') {
        setPushStatus('blocked');
        return;
      }
      try {
        const enabled = Notification.permission === 'granted'
          && localStorage.getItem('proace-fcm-token') !== null
          && localStorage.getItem('proace-fcm-owner') === String(user?.id);
        setPushStatus(enabled ? 'enabled' : 'ready');
      } catch {
        setPushStatus('ready');
      }
    }

    window.addEventListener(pushDeviceChangeEvent, syncPushStatus);
    window.addEventListener('storage', syncPushStatus);
    return () => {
      window.removeEventListener(pushDeviceChangeEvent, syncPushStatus);
      window.removeEventListener('storage', syncPushStatus);
    };
  }, [user?.id]);
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
        const storedToken = localStorage.getItem('proace-fcm-token');
        const storedOwner = localStorage.getItem('proace-fcm-owner');
        if (
          user?.id && Notification.permission === 'granted'
          && storedToken
          && storedOwner === String(user.id)
        ) {
          try {
            const dbStatus = await fetchPushDeviceStatus(storedToken);
            if (dbStatus.registered) {
              setPushStatus('enabled');
            } else {
              await registerPushDevice(user.id);
              if (!active) return;
              setPushStatus('enabled');
            }
          } catch {
            setPushStatus('enabled');
          }
        } else {
          setPushStatus(Notification.permission === 'denied' ? 'blocked' : 'ready');
        }
        const { onMessage } = await import('firebase/messaging');
        if (!active) return;
        unsubscribe = onMessage(messaging, payload => {
          if (payload.data?.recipient_id !== String(client.getQueryData<User>(['me'])?.id)) return;
          void refresh();
          const recipient = client.getQueryData<User>(['me']);
          if (recipient && payload.data.title && payload.data.notification_id) {
            presentNotificationOnce(
              recipient.id,
              payload.data.notification_id,
              payload.data.title,
              notifyRef.current,
            );
          }
        });
      } catch (error) {
        if (active) {
          setPushStatus(
            'Notification' in window && Notification.permission === 'denied'
              ? 'blocked'
              : 'unavailable',
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
  useEffect(() => {
    function close(event: MouseEvent) {
      if (panel.current && !panel.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener('mousedown', close);
    }
    return () => document.removeEventListener('mousedown', close);
  }, [open]);

  const unread = counts.data?.unread || 0;
  const items = list.data?.results || [];

  return (
    <div className="notification-center" ref={panel}>
      <button
        className={`icon-button notification-trigger ${open ? 'active' : ''}`}
        aria-label={`${unread} unread notifications`}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        title="Notifications"
      >
        <Bell size={20} />
        {unread > 0 && <b>{unread > 9 ? '9+' : unread}</b>}
      </button>

      {open && (
        <section className="notification-panel" aria-label="Notifications">
          <div className="notification-head">
            <div>
              <h2>Notifications</h2>
              <span>{unread ? `${unread} unread` : 'All caught up'}</span>
            </div>
            <button
              className="icon-button"
              aria-label="Close notifications"
              onClick={() => setOpen(false)}
            >
              <X size={17} />
            </button>
          </div>

          {(pushStatus === 'ready' || pushStatus === 'enabled') && (
            <button
              className="notification-push"
              disabled={pushBusy}
              aria-pressed={pushStatus === 'enabled'}
              onClick={() => void togglePush()}
            >
              <Bell size={16} aria-hidden="true" />
              <span className="notification-push-copy">
                <strong>Browser alerts</strong>
                <small>
                  {pushBusy
                    ? 'Updating this device…'
                    : pushStatus === 'enabled'
                      ? 'Enabled on this device'
                      : 'Get alerts when you are away'}
                </small>
              </span>
              <span className="notification-push-action">
                {pushBusy ? 'Saving…' : pushStatus === 'enabled' ? 'Turn off' : 'Enable'}
              </span>
            </button>
          )}

          {pushStatus === 'blocked' && (
            <p className="notification-push-status" role="status">
              Browser alerts are blocked in your browser settings.
            </p>
          )}

          {pushStatus === 'unsupported' && (
            <p className="notification-push-status" role="status">
              Browser alerts are unavailable on this device.
            </p>
          )}

          {pushStatus === 'unavailable' && (
            <p className="notification-push-status" role="status">
              Browser alerts could not be checked. Open App Settings to retry setup.
            </p>
          )}

          <button
            className="notification-read-all"
            disabled={!unread || action.isPending}
            onClick={() => action.mutate({ path: 'mark-all-read' })}
          >
            <CheckCheck size={15} />
            Mark all read
          </button>

          <div className="notification-list">
            {list.isLoading ? (
              <div className="notification-empty">Loading notifications…</div>
            ) : list.error ? (
              <div className="notification-empty error">Couldn’t load notifications.</div>
            ) : items.length ? (
              items.map((item) => (
                <article
                  className={`notification-item ${item.unread ? 'unread' : ''}`}
                  key={item.id}
                >
                  <span className={`notification-dot ${item.level}`} />
                  <div className="notification-content">
                    <h3>{item.verb}</h3>
                    {item.description && <p>{item.description}</p>}
                    <div className="notification-meta-tags">
                      {item.category && item.category !== 'general' && (
                        <span className="notification-tag">{item.category}</span>
                      )}
                      {item.store && (
                        <span className="notification-tag store">{item.store.name}</span>
                      )}
                      <small>{timeAgo(item.timestamp)}</small>
                    </div>
                    {notificationAction(item) && (
                      <Link
                        className="text-link notification-order-link"
                        href={notificationAction(item)!.href}
                        onClick={() => setOpen(false)}
                      >
                        {notificationAction(item)!.label} <ArrowRight size={13} />
                      </Link>
                    )}
                  </div>
                  <div className="notification-actions">
                    <button
                      title={item.unread ? 'Mark read' : 'Mark unread'}
                      aria-label={item.unread ? 'Mark read' : 'Mark unread'}
                      disabled={action.isPending}
                      onClick={() =>
                        action.mutate({
                          id: item.id,
                          path: item.unread ? 'mark-read' : 'mark-unread',
                        })
                      }
                    >
                      <CheckCheck size={15} />
                    </button>
                  </div>
                </article>
              ))
            ) : (
              <div className="notification-empty">
                <Inbox size={23} />
                <span>No notifications yet.</span>
              </div>
            )}
          </div>

          <div className="notification-footer">
            <Link href="/notifications" onClick={() => setOpen(false)}>
              See all notifications <ArrowRight size={13} />
            </Link>
          </div>
        </section>
      )}
    </div>
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
  return `${days}d ago`;
}

function AccountMenu() {
  const { user, logout, notify } = useShop();
  const [open, setOpen] = useState(false);
  const [storesCollapsed, setStoresCollapsed] = useState(false);

  const panelRef = useRef<HTMLDivElement>(null);
  const storeListRef = useRef<HTMLDivElement>(null);
  const storeSentinelRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const stores = useInfiniteQuery({
    queryKey: ['stores', 'selector', user?.id],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => api<Page<Store>>(`stores?limit=6&offset=${pageParam}${user?.is_staff || user?.is_superuser || user?.is_business_admin ? '&official=true' : ''}`),
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((n, p) => n + (p.results?.length || 0), 0);
      if (!last.next || (last.count !== undefined && loaded >= last.count)) {
        return undefined;
      }
      return loaded;
    },
    enabled: !!user && open && !user.must_change_password,
    refetchInterval: open ? 30000 : false,
  });
  const allStores = stores.data?.pages.flatMap(page => page.results) || [];
  const storeCount = stores.data?.pages[0]?.count || 0;
  const storeLimitReached = !user?.is_superuser && !user?.is_business_admin && storeCount >= 10;

  const hasNextPage = stores.hasNextPage;
  const isFetchingNextPage = stores.isFetchingNextPage;
  const fetchNextPage = stores.fetchNextPage;

  useEffect(() => {
    const sentinel = storeSentinelRef.current;
    const root = storeListRef.current;
    if (!open || storesCollapsed || !sentinel || !root || !hasNextPage || isFetchingNextPage) return;

    let cancelled = false;
    const observer = new IntersectionObserver(
      entries => {
        const [entry] = entries;
        if (entry?.isIntersecting && !cancelled) {
          void fetchNextPage();
        }
      },
      { root, rootMargin: '0px 0px 30px 0px' }
    );

    observer.observe(sentinel);
    return () => {
      cancelled = true;
      observer.disconnect();
    };
  }, [open, storesCollapsed, hasNextPage, isFetchingNextPage, fetchNextPage]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  if (!user) {
    return (
      <Link href="/account" className="account-link">
        <UserRound size={21} />
        <span>Sign in</span>
      </Link>
    );
  }

  function handleSwitchStore(storeId: number) {
    if (user) {
      try {
        localStorage.setItem(`proace-active-store-${user.id}`, String(storeId));
      } catch {
        /* Storage fallback */
      }
    }
    setOpen(false);
    router.push('/merchant');
  }

  async function handleSignOut() {
    setOpen(false);
    try {
      await logout();
      router.push('/');
    } catch (error) {
      notify((error as Error).message, true);
    }
  }

  return (
    <div className="account-menu-container" ref={panelRef}>
      <button
        type="button"
        className={`account-link account-trigger ${open ? 'active' : ''}`}
        aria-label={`Account and store menu for ${user.first_name}`}
        aria-expanded={open}
        onClick={() => setOpen(value => !value)}
      >
        {user.avatar_url ? (
          <ResponsiveMediaImage
            src={user.avatar_url}
            alt={user.first_name}
            style={{ width: 22, height: 22, borderRadius: '50%', objectFit: 'cover' }}
            sizes="22px"
            width={44}
            height={44}
          />
        ) : (
          <UserRound size={21} />
        )}
        <span>Hi, {user.first_name}</span>
        <ChevronDown size={14} className={`account-chevron ${open ? 'open' : ''}`} />
      </button>

      {open && (
        <section className="account-dropdown-panel" aria-label="Account and store switcher">
          <div className="account-dropdown-header">
            <div className="account-dropdown-avatar">
              {user.avatar_url ? (
                <ResponsiveMediaImage
                  src={user.avatar_url}
                  alt={user.first_name}
                  style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }}
                  sizes="48px"
                  width={96}
                  height={96}
                />
              ) : (
                user.first_name?.[0]?.toUpperCase() || <UserRound size={18} />
              )}
            </div>
            <div className="account-dropdown-user-info">
              <strong>{user.first_name} {user.last_name || ''}</strong>
              <span className="account-dropdown-email">{user.email}</span>
              <div className="account-dropdown-badges">
                {(user.is_superuser || user.is_business_admin) ? (
                  <span className="account-badge admin">Root Admin</span>
                ) : user.is_staff ? (
                  <span className="account-badge staff">Staff Account</span>
                ) : (
                  <span className="account-badge customer">Verified Account</span>
                )}
              </div>
            </div>
          </div>

          <div className="account-dropdown-body">
            {/* YOUR STORES */}
            <div className="account-dropdown-section">
              <button
                type="button"
                className="account-dropdown-section-title toggleable"
                onClick={() => setStoresCollapsed(c => !c)}
                aria-expanded={!storesCollapsed}
                aria-label={storesCollapsed ? 'Expand your stores' : 'Collapse your stores'}
              >
                <span className="title-left">
                  <ChevronDown size={13} className={`stores-chevron ${storesCollapsed ? 'collapsed' : ''}`} />
                  <span>Your Stores</span>
                </span>
                {allStores.length > 0 && (
                  <span className="account-dropdown-count">{storeCount}</span>
                )}
              </button>

              {!storesCollapsed && (
                <>
                  {stores.isLoading ? (
                    <div className="account-dropdown-loading">Loading your stores…</div>
                  ) : allStores.length > 0 ? (
                    <>
                      <div
                        ref={storeListRef}
                        className="account-dropdown-stores-list"
                        onScroll={event => {
                          const target = event.currentTarget;
                          if (
                            hasNextPage &&
                            !isFetchingNextPage &&
                            !stores.isFetchNextPageError &&
                            target.scrollHeight > target.clientHeight &&
                            target.scrollHeight - target.scrollTop <= target.clientHeight + 40
                          ) {
                            void fetchNextPage();
                          }
                        }}
                      >
                        {allStores.map(store => (
                          <button
                            key={store.id}
                            type="button"
                            className="account-store-item"
                            onClick={() => handleSwitchStore(store.id)}
                          >
                            <div className="account-store-icon">
                              <StoreIcon size={15} />
                            </div>
                            <div className="account-store-details">
                              <strong>{store.name}</strong>
                              <small>@{store.username}</small>
                            </div>
                            <span className={`account-store-status ${store.status}`}>
                              {store.status}
                            </span>
                            <ArrowRight size={13} className="account-store-arrow" />
                          </button>
                        ))}
                        <div ref={storeSentinelRef} aria-hidden="true" style={{ height: 1 }} />
                        {stores.isFetchingNextPage && (
                          <div role="status" className="account-dropdown-loading">
                            Loading more stores…
                          </div>
                        )}
                        {stores.isFetchNextPageError && (
                          <button
                            type="button"
                            className="account-dropdown-action-link"
                            onClick={() => void fetchNextPage()}
                          >
                            Retry loading stores
                          </button>
                        )}
                      </div>

                      <div className="account-dropdown-section-footer">
                        {storeLimitReached ? (
                          <span className="account-dropdown-limit-note">10-store limit reached</span>
                        ) : (!user.is_staff || user.is_superuser || user.is_business_admin) ? (
                          <Link
                            href="/merchant/new-store"
                            className="account-dropdown-action-link add-store-btn"
                            onClick={() => setOpen(false)}
                          >
                            <Plus size={14} /> Open another store
                          </Link>
                        ) : null}
                      </div>
                    </>
                  ) : (
                    <div className="account-dropdown-empty-store">
                      <div className="empty-store-card">
                        <div className="empty-store-icon">
                          <StoreIcon size={18} />
                        </div>
                        <div className="empty-store-text">
                          <strong>No store yet</strong>
                          <p>Start selling physical & digital products.</p>
                        </div>
                      </div>
                      {(!user.is_staff || user.is_superuser || user.is_business_admin) && <Link
                        href="/merchant/new-store"
                        className="button empty-store-create-btn"
                        onClick={() => setOpen(false)}
                      >
                        <Plus size={14} /> Create your first store
                      </Link>}
                    </div>
                  )}
                </>
              )}
            </div>

            {/* TEAM & SUB-ACCOUNTS (Admin & Staff) */}
            {(user.is_superuser || user.is_staff) && (
              <div className="account-dropdown-section">
                <div className="account-dropdown-section-title">
                  <span>Team & Sub-Accounts</span>
                </div>
                <div className="account-dropdown-links">
                  {(user.is_superuser || user.is_business_admin) && (
                    <Link
                      href="/admin/staff"
                      className="account-dropdown-nav-link"
                      onClick={() => setOpen(false)}
                    >
                      <UsersRound size={16} />
                      <div>
                        <strong>Manage Staff & Sub-Accounts</strong>
                        <small>Permissions, roles & team members</small>
                      </div>
                    </Link>
                  )}
                  <Link
                    href="/admin"
                    className="account-dropdown-nav-link"
                    onClick={() => setOpen(false)}
                  >
                    <ChartNoAxesCombined size={16} />
                    <div>
                      <strong>Platform Dashboard</strong>
                      <small>System orders, analytics & metrics</small>
                    </div>
                  </Link>
                </div>
              </div>
            )}

            {/* PERSONAL ACCOUNT */}
            <div className="account-dropdown-section">
              <div className="account-dropdown-section-title">
                <span>Account & Settings</span>
              </div>
              <div className="account-dropdown-links">
                <Link
                  href={user.is_staff || user.is_superuser || user.is_business_admin ? '/account/profile' : '/account'}
                  className="account-dropdown-nav-link"
                  onClick={() => setOpen(false)}
                >
                  <UserRound size={16} />
                  <span>My Account</span>
                </Link>
                {!user.is_staff && !user.is_superuser && !user.is_business_admin && (
                  <Link href="/account/orders" className="account-dropdown-nav-link" onClick={() => setOpen(false)}>
                    <ShoppingBag size={16} />
                    <span>My Orders</span>
                  </Link>
                )}
                {!user.is_staff && !user.is_superuser && !user.is_business_admin && (
                  <Link href="/saved" className="account-dropdown-nav-link" onClick={() => setOpen(false)}>
                    <Heart size={16} />
                    <span>Saved Items</span>
                  </Link>
                )}
                <Link href="/settings" className="account-dropdown-nav-link" onClick={() => setOpen(false)}>
                  <Settings size={16} />
                  <span>App Settings</span>
                </Link>
              </div>
            </div>
          </div>

          {/* FOOTER */}
          <div className="account-dropdown-footer">
            <button
              type="button"
              className="account-dropdown-signout"
              onClick={handleSignOut}
            >
              <LogOut size={15} />
              <span>Sign out</span>
            </button>
          </div>
        </section>
      )}

    </div>
  );
}


export function MandatoryPasswordChange() {
  const client = useQueryClient();
  const router = useRouter();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [showPasswords, setShowPasswords] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const data = Object.fromEntries(new FormData(event.currentTarget));
      if (data.password !== data.confirm_password) { setError('New passwords do not match.'); return; }
      const result = await api<{user: User}>('password/change', 'POST', { current_password: data.current_password, password: data.password });
      client.setQueryData(['me'], result.user);
      router.replace('/admin');
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  return <main id="main" className="workspace-password-page">
    <div className="workspace-password-brand"><span className="wordmark">proace<span>®</span></span><ThemeToggle /></div>
    <section className="workspace-password-card" aria-labelledby="workspace-password-title">
      <div className="workspace-password-icon"><ShieldCheck size={28} /></div>
      <span className="eyebrow green">SECURE YOUR WORKSPACE</span>
      <h1 id="workspace-password-title">Make this account yours</h1>
      <p>Replace your temporary password to continue to your admin or staff workspace.</p>
      <form className="form-stack" onSubmit={submit}>
        <label>Current or temporary password<input name="current_password" type={showPasswords ? 'text' : 'password'} required autoComplete="current-password" /></label>
        <label>New password<input name="password" type={showPasswords ? 'text' : 'password'} required minLength={8} maxLength={128} autoComplete="new-password" aria-describedby="workspace-password-hint" /></label>
        <small id="workspace-password-hint">Use at least 8 characters. Choose a password you don’t use elsewhere.</small>
        <label>Confirm new password<input name="confirm_password" type={showPasswords ? 'text' : 'password'} required minLength={8} maxLength={128} autoComplete="new-password" /></label>
        <label className="workspace-password-show"><input type="checkbox" checked={showPasswords} onChange={event => setShowPasswords(event.target.checked)} />Show passwords</label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="button" disabled={busy}>{busy ? 'Updating password…' : 'Save password & continue'}<ArrowRight size={17} /></button>
      </form>
      <p className="workspace-password-note"><ShieldCheck size={15} />Your new password protects access to your workspace.</p>
    </section>
  </main>;
}
