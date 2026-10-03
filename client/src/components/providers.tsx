'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, X, AlertCircle } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import type { Cart, CartLine, Product, User } from '@/lib/types';
import { unregisterPushDevice } from '@/lib/firebase-messaging';

type Context = {
  user?: User; sessionLoading: boolean; cart: Cart; cartLoading: boolean; cartError: Error | null; saved: Product[];
  notify: (message: string, error?: boolean) => void;
  add: (product: Product, quantity?: number) => Promise<void>;
  setQuantity: (product: Product, quantity: number) => Promise<void>;
  toggleSave: (product: Product) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};
const ShopContext = createContext<Context | null>(null);

function ShopProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const session = useQuery({ queryKey: ['me'], queryFn: () => api<User>('me'), retry: false, staleTime: 60000 });
  const user = session.data;
  const [guest, setGuest] = useState<CartLine[]>([]);
  const [guestSaved, setGuestSaved] = useState<Product[]>([]);
  const [ready, setReady] = useState(false);
  const [notice, setNotice] = useState<{ message: string; error?: boolean } | null>(null);
  const notify = (message: string, error = false) => setNotice({ message, error });
  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem('proace-cart') || '[]');
      if (Array.isArray(stored)) setGuest(stored.filter(item => item?.product?.id && item.quantity > 0));
      const saved = JSON.parse(localStorage.getItem('proace-saved') || '[]');
      if (Array.isArray(saved)) setGuestSaved(saved.filter(item => item?.id));
    } catch { /* Ignore invalid local preferences. */ }
    setReady(true);
  }, []);
  useEffect(() => { if (ready) localStorage.setItem('proace-cart', JSON.stringify(guest)); }, [guest, ready]);
  useEffect(() => { if (ready) localStorage.setItem('proace-saved', JSON.stringify(guestSaved)); }, [guestSaved, ready]);
  useEffect(() => { if (!notice) return; const timeout = setTimeout(() => setNotice(null), 4500); return () => clearTimeout(timeout); }, [notice]);
  const cartQuery = useQuery({ queryKey: ['cart', user?.id], queryFn: () => api<Cart>('cart'), enabled: !!user, retry: false });
  const savedQuery = useQuery({ queryKey: ['saved', user?.id], queryFn: () => api<Product[]>('wishlist'), enabled: !!user });
  const subtotal = guest.reduce((sum, row) => sum + Number(row.product.sale_price) * row.quantity, 0);
  const shipping = subtotal >= 100000 || !guest.length || guest.every(row => row.product.is_digital) ? 0 : 2500;
  const guestCart = { items: guest, subtotal: String(subtotal), shipping: String(shipping), total: String(subtotal + shipping) };
  const cart = user ? cartQuery.data || { items: [], subtotal: '0', shipping: '0', total: '0' } : guestCart;

  async function add(product: Product, quantity = 1) {
    if (user && product.is_own_store) throw new Error("You cannot buy products from any store you own.");
    if (user) {
      const result = await api<Cart>('cart', 'POST', { product: product.id, quantity });
      client.setQueryData(['cart', user.id], result);
    } else {
      const existing = guest.find(row => row.product.id === product.id);
      const next = (existing?.quantity || 0) + quantity;
      if (next > product.available) throw new Error(`Only ${product.available} available.`);
      setGuest(rows => [...rows.filter(row => row.product.id !== product.id), { product, quantity: next, total: String(Number(product.sale_price) * next), purchasable: true }]);
    }
    notify('Added to your bag');
  }
  async function setQuantity(product: Product, quantity: number) {
    if (user) {
      const result = await api<Cart>('cart', quantity === 0 ? 'DELETE' : 'PATCH', { product: product.id, quantity });
      client.setQueryData(['cart', user.id], result);
    } else {
      if (quantity > product.available) throw new Error(`Only ${product.available} available.`);
      setGuest(rows => quantity === 0 ? rows.filter(row => row.product.id !== product.id) : rows.map(row => row.product.id === product.id ? { ...row, quantity } : row));
    }
  }
  const saved = user ? savedQuery.data || [] : guestSaved;
  async function toggleSave(product: Product) {
    const exists = saved.some(item => item.id === product.id);
    if (user) {
      await api('wishlist', exists ? 'DELETE' : 'POST', { product: product.id });
      await client.invalidateQueries({ queryKey: ['saved'] });
    } else setGuestSaved(rows => exists ? rows.filter(item => item.id !== product.id) : [...rows, product]);
    notify(exists ? 'Removed from saved items' : 'Saved for later');
  }
  async function login(email: string, password: string) {
    const result = await api<{ user: User }>('auth/login', 'POST', { email, password });
    client.setQueryData(['me'], result.user);
    const remaining: CartLine[] = [];
    for (const row of guest) {
      try { await api('cart', 'POST', { product: row.product.id, quantity: row.quantity }); }
      catch { remaining.push(row); }
    }
    setGuest(remaining);
    for (const product of guestSaved) await api('wishlist', 'POST', { product: product.id }).catch(() => null);
    setGuestSaved([]);
    await client.invalidateQueries();
    await client.invalidateQueries({ queryKey: ['saved'] });
    notify(remaining.length ? 'Signed in. Some guest items could not be added because they are unavailable or belong to your own store.' : `Welcome back, ${result.user.first_name}`);
  }
  async function logout() {
    let pushCleanupFailed = false;
    try { await unregisterPushDevice(); }
    catch { pushCleanupFailed = true; }
    await api('auth/logout', 'POST', {});
    client.clear();
    client.setQueryData(['me'], null);
    setGuest([]); setGuestSaved([]);
    notify(pushCleanupFailed
      ? 'You have been signed out, but browser push could not be disabled. The inbox will remain account-scoped.'
      : 'You have been signed out');
  }
  return <ShopContext.Provider value={{ user, sessionLoading: session.isLoading, cart, cartLoading: session.isLoading || (!!user && cartQuery.isLoading), cartError: cartQuery.error, saved, notify, add, setQuantity, toggleSave, login, logout }}>
    {children}
    {notice && <div className={`toast ${notice.error ? 'error' : ''}`} role="status">{notice.error ? <AlertCircle size={20} /> : <Check size={20} />}<span>{notice.message}</span><button aria-label="Dismiss notification" onClick={() => setNotice(null)}><X size={16} /></button></div>}
  </ShopContext.Provider>;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 1, refetchOnWindowFocus: false, staleTime: 15000 } } }));
  return <QueryClientProvider client={client}><ShopProvider>{children}</ShopProvider></QueryClientProvider>;
}
export function useShop() { const context = useContext(ShopContext); if (!context) throw new Error('ShopProvider missing'); return context; }
