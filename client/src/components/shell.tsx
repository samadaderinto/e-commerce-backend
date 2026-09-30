'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState, FormEvent, ReactNode } from 'react';
import { ArrowUpRight, ChevronDown, Heart, Menu, Search, ShoppingBag, UserRound, X, Truck, ShieldCheck, RotateCcw } from 'lucide-react';
import { categories } from '@/lib/api';
import { useShop } from './providers';

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
      <div className="header-actions"><Link href="/account" className="account-link"><UserRound size={21} /><span>{user ? `Hi, ${user.first_name}` : 'Sign in'}</span></Link><Link href="/saved" className="icon-button" aria-label="Saved items" title="Saved items"><Heart size={21} /></Link><Link href="/cart" className="bag-link" aria-label={`Shopping bag, ${cart.items.reduce((n, row) => n + row.quantity, 0)} items`}><ShoppingBag size={21} /><span className="bag-text">Bag</span><b>{cart.items.reduce((n, row) => n + row.quantity, 0)}</b></Link></div>
    </div></header>
    {!merchant && <nav className="category-nav" aria-label="Main navigation"><div className="container"><Link className="all-categories" href="/shop"><Menu size={16} />All categories<ChevronDown size={14} /></Link>{categories.slice(0, 5).map(category => <Link key={category.key} href={`/shop?category=${category.key}`}>{category.name}</Link>)}<Link className="deals-link" href="/shop?deals=true">Everyday deals <span /></Link></div></nav>}
    {menu && <div className="mobile-drawer"><form className="search-box" onSubmit={submit}><Search size={18} /><input aria-label="Mobile search products" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search the shop" /><button aria-label="Submit search"><ArrowUpRight size={18} /></button></form><Link onClick={() => setMenu(false)} href="/shop">Shop everything</Link>{categories.map(category => <Link onClick={() => setMenu(false)} key={category.key} href={`/shop?category=${category.key}`}>{category.name}</Link>)}<Link onClick={() => setMenu(false)} href="/merchant">Seller workspace</Link></div>}
    <main id="main">{children}</main>
    {!merchant && <><div className="benefits container"><div><Truck /><span><strong>Delivered to your door</strong><small>Free shipping over ₦100,000</small></span></div><div><ShieldCheck /><span><strong>Shop with confidence</strong><small>Secure accounts. Trusted sellers.</small></span></div><div><RotateCcw /><span><strong>Here to help</strong><small>Support when you need it</small></span></div></div>
      <footer><div className="container footer-grid"><div><Link href="/" className="wordmark">proace<span>®</span></Link><p>A little discovery. A lot to love.<br />Your everyday marketplace.</p></div><div><h3>Discover</h3><Link href="/shop">Shop all</Link><Link href="/shop?deals=true">Everyday deals</Link><Link href="/saved">Saved items</Link></div><div><h3>Your Proace</h3><Link href="/account">Your account</Link><Link href="/account/orders">Your orders</Link><Link href="/merchant">Become a seller</Link></div><div><h3>Good to know</h3><Link href="/help">Help & delivery</Link><Link href="/privacy">Privacy policy</Link><Link href="/terms">Terms & returns</Link></div></div><div className="container footer-bottom"><span>© {new Date().getFullYear()} Proace. All rights reserved.</span><span>Nigeria · English · NGN ₦</span></div></footer></>}
  </>;
}
