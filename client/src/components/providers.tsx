'use client';

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useRef,
  ReactNode,
} from 'react';
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { Check, X, AlertCircle } from 'lucide-react';
import { ThemeProvider } from './theme';
import { api, ApiError, cancelPendingApiRequests } from '@/lib/api';
import { clearSignedInSession } from '@/lib/session-cache';
import type { Cart, CartLine, Product, User } from '@/lib/types';
import type { SocialCredential } from '@/lib/social-auth';
import { VisualSearchProvider } from './visual-search-context';

type SocialLoginPayload = SocialCredential & { referral_code?: string };
import { presentNotificationOnce } from '@/lib/notification-presentation';
import { unregisterPushDevice } from '@/lib/firebase-messaging';

type Context = {
  user?: User;
  sessionLoading: boolean;
  cart: Cart;
  cartLoading: boolean;
  cartError: Error | null;
  saved: Product[];
  savedLoading: boolean;
  savedError: Error | null;
  refreshSaved: () => Promise<void>;
  notify: (message: string, error?: boolean) => void;
  add: (product: Product, quantity?: number) => Promise<void>;
  setQuantity: (product: Product, quantity: number) => Promise<void>;
  toggleSave: (product: Product) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  socialLogin: (provider: 'google' | 'apple', payload: SocialLoginPayload) => Promise<User>;
  logout: () => Promise<void>;
};

const ShopContext = createContext<Context | null>(null);

function ShopProvider({ children }: { children: ReactNode }) {
  const pendingAdds = useRef(new Set<number>());
  const client = useQueryClient();
  const session = useQuery({
    queryKey: ['me'],
    queryFn: async (): Promise<User | null> => {
      try {
        return await api<User>('me');
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    retry: false,
    staleTime: 60000,
  });
  const user = session.data ?? undefined;
  const consumer = !!user && !user.is_staff && !user.is_superuser && !user.is_business_admin;
  const [guest, setGuest] = useState<CartLine[]>([]);
  const [guestSaved, setGuestSaved] = useState<Product[]>([]);
  const [ready, setReady] = useState(false);
  const [notice, setNotice] = useState<{ message: string; error?: boolean } | null>(null);

  const notify = (message: string, error = false) => setNotice({ message, error });

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem('proace-cart') || '[]');
      if (Array.isArray(stored)) {
        setGuest(
          stored
            .filter((item) => (
              item?.product?.id &&
              item.quantity > 0 &&
              item.product.product_type !== 'affiliate_clickbank'
            ))
            .map((item) => (item.product.is_digital ? { ...item, quantity: 1 } : item))
        );
      }
      const saved = JSON.parse(localStorage.getItem('proace-saved') || '[]');
      if (Array.isArray(saved)) {
        setGuestSaved(saved.filter((item) => item?.id));
      }
    } catch {
      /* Ignore invalid local preferences. */
    }
    setReady(true);
  }, []);

  useEffect(() => {
    if (ready) {
      try {
        localStorage.setItem('proace-cart', JSON.stringify(guest));
      } catch {
        // Optional persistence must not discard the in-memory shopping session.
      }
    }
  }, [guest, ready]);

  useEffect(() => {
    if (ready) {
      try {
        localStorage.setItem('proace-saved', JSON.stringify(guestSaved));
      } catch {
        // Storage can be blocked or full; saved items remain usable in memory.
      }
    }
  }, [guestSaved, ready]);

  useEffect(() => {
    if (!notice) return;
    const timeout = setTimeout(() => setNotice(null), 4500);
    return () => clearTimeout(timeout);
  }, [notice]);

  const cartQuery = useQuery({
    queryKey: ['cart', user?.id],
    queryFn: () => api<Cart>('cart'),
    enabled: consumer,
    retry: false,
  });

  const savedQuery = useQuery({
    queryKey: ['saved', user?.id],
    queryFn: () => api<Product[]>('wishlist'),
    enabled: consumer,
  });

  const subtotal = guest.reduce(
    (sum, row) => sum + Number(row.product.sale_price) * row.quantity,
    0
  );
  const shipping: string | null = guest.some((row) => !row.product.is_digital)
    ? null
    : '0';
  const guestCart: Cart = {
    items: guest,
    subtotal: String(subtotal),
    shipping,
    total: String(subtotal),
  };
  const cart = user
    ? cartQuery.data || { items: [], subtotal: '0', shipping: '0', total: '0' }
    : guestCart;

  useEffect(() => {
    if (!user?.id || user.must_change_password) return;
    let stream: EventSource;
    let reconnect: number | undefined;
    let backoff = 3000;
    let pending: number | undefined;

    const refresh = () => {
      if (pending !== undefined) return;
      pending = window.setTimeout(() => {
        pending = undefined;
        void Promise.all([
          client.invalidateQueries({ queryKey: ['notifications'] }),
          client.invalidateQueries({ queryKey: ['merchant-notifications'] }),
          client.invalidateQueries({ queryKey: ['merchant-notifications-count'] }),
        ]);
      }, 100);
    };

    const seen = new Set<number>();
    const receive = (message: MessageEvent) => {
      try {
        const event: {
          event?: string;
          title?: string;
          notification_id?: number;
        } = JSON.parse(message.data);
        refresh();
        if (event.event === 'notification.created' && event.title && event.notification_id && !seen.has(event.notification_id)) {
          seen.add(event.notification_id);
          if (seen.size > 200) {
            seen.delete(seen.values().next().value!);
          }
          presentNotificationOnce(user.id, event.notification_id, event.title, notify);
        }
      } catch {
        /* Ignore malformed events; reconnect resynchronizes durable state. */
      }
    };

    const connect = () => {
      stream = new EventSource('/api/notifications/stream');
      stream.addEventListener('ready', () => {
        backoff = 3000;
        refresh();
      });
      stream.addEventListener('resync', refresh);
      stream.addEventListener('state', receive);
      stream.onerror = () => {
        if (stream.readyState === EventSource.CLOSED) {
          stream.close();
          reconnect = window.setTimeout(connect, backoff);
          backoff = Math.min(backoff * 2, 30000);
        }
      };
    };

    connect();
    const fallback = window.setInterval(() => {
      if (stream.readyState !== EventSource.OPEN) {
        refresh();
      }
    }, 30000);

    return () => {
      stream.close();
      window.clearTimeout(pending);
      window.clearTimeout(reconnect);
      window.clearInterval(fallback);
    };
  }, [user?.id, user?.must_change_password, client]);

  async function add(product: Product, quantity = 1): Promise<void> {
    if (product.product_type === 'affiliate_clickbank') {
      throw new Error('This partner listing uses the vendor checkout. Open its official partner link.');
    }
    if (user && !consumer) {
      throw new Error('Administrative accounts cannot shop.');
    }
    if (user && product.is_own_store) {
      throw new Error('You cannot buy products from any store you own.');
    }
    product = {
      ...product,
      selected_variant: product.selected_variant || '',
    };
    if (pendingAdds.current.has(product.id)) return;
    if (!Number.isSafeInteger(quantity) || quantity < 1) {
      throw new Error('Choose a positive whole quantity.');
    }

    const current =
      cart.items.find(
        (row) =>
          row.product.id === product.id &&
          (row.product.selected_variant || '') === (product.selected_variant || '')
      )?.quantity || 0;

    if (!product.is_digital && current + quantity > product.available) {
      throw new Error(`Only ${product.available} available.`);
    }

    pendingAdds.current.add(product.id);
    try {
      if (user) {
        const result = await api<Cart>('cart', 'POST', {
          product: product.id,
          variant: product.selected_variant || '',
          quantity,
        });
        client.setQueryData(['cart', user.id], result);
      } else {
        setGuest((rows) => {
          const existing = rows.find(
            (row) =>
              row.product.id === product.id &&
              (row.product.selected_variant || '') === (product.selected_variant || '')
          );
          const next = product.is_digital
            ? 1
            : Math.min(product.available, (existing?.quantity || 0) + quantity);

          return [
            ...rows.filter(
              (row) =>
                row.product.id !== product.id ||
                (row.product.selected_variant || '') !== (product.selected_variant || '')
            ),
            {
              product,
              quantity: next,
              total: String(Number(product.sale_price) * next),
              purchasable: true,
            },
          ];
        });
      }
      notify('Added to your bag');
    } finally {
      pendingAdds.current.delete(product.id);
    }
  }

  async function setQuantity(product: Product, quantity: number) {
    if (product.is_digital && quantity > 0) {
      quantity = 1;
    }
    if (user) {
      const result = await api<Cart>(
        'cart',
        quantity === 0 ? 'DELETE' : 'PATCH',
        {
          product: product.id,
          variant: product.selected_variant || '',
          quantity,
        }
      );
      client.setQueryData(['cart', user.id], result);
    } else {
      if (!product.is_digital && quantity > product.available) {
        throw new Error(`Only ${product.available} available.`);
      }
      setGuest((rows) =>
        quantity === 0
          ? rows.filter(
              (row) =>
                row.product.id !== product.id ||
                (row.product.selected_variant || '') !== (product.selected_variant || '')
            )
          : rows.map((row) =>
              row.product.id === product.id &&
              (row.product.selected_variant || '') === (product.selected_variant || '')
                ? { ...row, quantity }
                : row
            )
      );
    }
  }

  const saved = user
    ? [
        ...(savedQuery.data || []),
        ...guestSaved.filter(
          (item) => !(savedQuery.data || []).some((savedItem) => savedItem.id === item.id)
        ),
      ]
    : guestSaved;

  async function refreshSaved(): Promise<void> {
    if (consumer) await savedQuery.refetch();
  }

  async function toggleSave(product: Product) {
    if (user && !consumer) {
      throw new Error('Administrative accounts cannot save items.');
    }
    const exists = saved.some((item) => item.id === product.id);
    if (user) {
      await api('wishlist', exists ? 'DELETE' : 'POST', { product: product.id });
      setGuestSaved((rows) => rows.filter((item) => item.id !== product.id));
      await client.invalidateQueries({ queryKey: ['saved'] });
    } else {
      setGuestSaved((rows) =>
        exists ? rows.filter((item) => item.id !== product.id) : [...rows, product]
      );
    }
    notify(exists ? 'Removed from saved items' : 'Saved for later');
  }

  async function syncGuestSession(
    user: User
  ): Promise<{ remainingCart: CartLine[]; remainingSaved: Product[] }> {
    await client.cancelQueries();
    client.clear();
    client.setQueryData(['me'], user);
    if (user.is_staff || user.is_superuser || user.is_business_admin) {
      setGuest([]);
      setGuestSaved([]);
      await client.invalidateQueries({ queryKey: ['stores'] });
      return { remainingCart: [], remainingSaved: [] };
    }

    const remaining: CartLine[] = [];
    for (const row of guest) {
      try {
        await api('cart', 'POST', {
          product: row.product.id,
          variant: row.product.selected_variant || '',
          quantity: row.quantity,
        });
      } catch {
        remaining.push(row);
      }
    }
    setGuest(remaining);

    const remainingSaved: Product[] = [];
    for (const product of guestSaved) {
      try {
        await api('wishlist', 'POST', { product: product.id });
      } catch {
        remainingSaved.push(product);
      }
    }
    setGuestSaved(remainingSaved);
    await client.invalidateQueries();
    await client.invalidateQueries({ queryKey: ['saved'] });
    return { remainingCart: remaining, remainingSaved };
  }

  function signInMergeMessage(
    remainingCart: CartLine[],
    remainingSaved: Product[],
    welcome: string
  ): string {
    const messages = [welcome];
    if (remainingCart.length) {
      messages.push(
        'Some guest cart items could not be added because they are unavailable or belong to your own store. Sign out to review them and retry.'
      );
    }
    if (remainingSaved.length) {
      messages.push('Some saved items could not sync and remain available in Saved items to retry.');
    }
    return messages.join(' ');
  }

  async function login(email: string, password: string) {
    const result = await api<{ user: User }>('auth/login', 'POST', { email, password });
    const { remainingCart, remainingSaved } = await syncGuestSession(result.user);
    notify(
      signInMergeMessage(
        remainingCart,
        remainingSaved,
        `Welcome back, ${result.user.first_name}`
      ),
      remainingSaved.length > 0
    );
  }

  async function socialLogin(
    provider: 'google' | 'apple',
    payload: SocialLoginPayload
  ): Promise<User> {
    const result = await api<{ user: User; is_new_user?: boolean; provider?: string }>(
      `auth/${provider}`,
      'POST',
      payload
    );
    const { remainingCart, remainingSaved } = await syncGuestSession(result.user);
    notify(
      signInMergeMessage(
        remainingCart,
        remainingSaved,
        result.is_new_user
          ? `Welcome to ProAce, ${result.user.first_name}!`
          : `Welcome back, ${result.user.first_name}`
      ),
      remainingSaved.length > 0
    );
    return result.user;
  }

  async function logout() {
    let pushCleanupFailed = false;
    let revocationFailed = false;
    cancelPendingApiRequests();
    await clearSignedInSession(client);
    try {
      await unregisterPushDevice();
    } catch {
      pushCleanupFailed = true;
    }
    try {
      await api('auth/logout', 'POST', {});
    } catch {
      revocationFailed = true;
    }
    const messages = ['You have been signed out on this device.'];
    if (pushCleanupFailed) {
      messages.push('Browser push could not be disabled. The inbox will remain account-scoped.');
    }
    if (revocationFailed) {
      messages.push('The server could not confirm session revocation. Change your password to revoke outstanding sessions.');
    }
    notify(messages.join(' '), revocationFailed);
  }

  return (
    <ShopContext.Provider
      value={{
        user,
        sessionLoading: session.isLoading,
        cart,
        cartLoading: session.isLoading || (!!user && cartQuery.isLoading),
        cartError: cartQuery.error,
        saved,
        savedLoading: !ready || session.isLoading || (consumer && savedQuery.isLoading),
        savedError: consumer ? savedQuery.error : null,
        refreshSaved,
        notify,
        add,
        setQuantity,
        toggleSave,
        login,
        socialLogin,
        logout,
      }}
    >
      {children}
      {notice && (
        <div className={`toast ${notice.error ? 'error' : ''}`} role="status">
          {notice.error ? <AlertCircle size={20} /> : <Check size={20} />}
          <span>{notice.message}</span>
          <button aria-label="Dismiss notification" onClick={() => setNotice(null)}>
            <X size={16} />
          </button>
        </div>
      )}
    </ShopContext.Provider>
  );
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: (count, error) =>
              !(error instanceof ApiError && error.status < 500) && count < 1,
            refetchOnWindowFocus: false,
            staleTime: 15000,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <ShopProvider>
          <VisualSearchProvider>{children}</VisualSearchProvider>
        </ShopProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export function useShop() {
  const context = useContext(ShopContext);
  if (!context) {
    throw new Error('ShopProvider missing');
  }
  return context;
}
