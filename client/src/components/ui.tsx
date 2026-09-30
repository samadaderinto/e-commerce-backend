'use client';
import Link from 'next/link';
import { useState, ReactNode } from 'react';
import { AlertCircle, ArrowRight, Heart, ImageOff, Minus, Plus, ShoppingBag, Star } from 'lucide-react';
import { Product } from '@/lib/types';
import { money } from '@/lib/api';
import { useShop } from './providers';

export function ProductImage({ src, alt, className = '' }: { src?: string; alt: string; className?: string }) {
  const [failed, setFailed] = useState(false);
  return src && !failed ? <img className={className} src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} /> : <div className={`image-placeholder ${className}`}><ImageOff size={32} /><span>{alt}</span></div>;
}
export function ProductCard({ product }: { product: Product }) {
  const { saved, toggleSave, add, notify } = useShop();
  const [busy, setBusy] = useState(false);
  const liked = saved.some(item => item.id === product.id);
  return <article className="product-card">
    <div className="product-photo"><Link href={`/products/${product.id}`} aria-label={`View ${product.title}`}><ProductImage src={product.image} alt={product.title} /></Link>
      {product.discount > 0 && <span className="discount">−{product.discount}%</span>}
      <button className={`icon-button save-button ${liked ? 'saved' : ''}`} aria-label={`${liked ? 'Unsave' : 'Save'} ${product.title}`} title={liked ? 'Remove from saved items' : 'Save for later'} onClick={() => toggleSave(product).catch(error => notify(error.message, true))}><Heart size={18} fill={liked ? 'currentColor' : 'none'} /></button>
      <button className="quick-add" disabled={busy || !product.available} onClick={async () => { setBusy(true); try { await add(product); } catch (error) { notify((error as Error).message, true); } finally { setBusy(false); } }}><Plus size={16} />{!product.available ? 'Sold out' : busy ? 'Adding…' : 'Add to bag'}</button>
    </div>
    <div className="product-meta"><span>{product.brand || product.store_name}</span><span><Star size={12} fill="currentColor" />{Number(product.average_rating) > 0 ? Number(product.average_rating).toFixed(1) : 'New'}</span></div>
    <Link className="product-title" href={`/products/${product.id}`}>{product.title}</Link>
    <div className="price"><strong>{money(product.sale_price)}</strong>{product.discount > 0 && <del>{money(product.price)}</del>}</div>
  </article>;
}
export function ProductGrid({ products }: { products: Product[] }) { return <div className="product-grid">{products.map(product => <ProductCard key={product.id} product={product} />)}</div>; }
export function Loading({ cards = false }: { cards?: boolean }) { return cards ? <div className="product-grid" aria-label="Loading products">{Array.from({ length: 8 }, (_, i) => <div key={i} className="skeleton-card"><div className="skeleton" /><div className="skeleton line" /><div className="skeleton line short" /></div>)}</div> : <div className="loading" role="status"><span className="spinner" />Loading…</div>; }
export function ErrorState({ error, retry }: { error: Error; retry?: () => void }) { return <div className="empty-state" role="alert"><AlertCircle size={32} /><h2>Something interrupted your visit</h2><p>{error.message}</p>{retry && <button className="button" onClick={retry}>Try again</button>}</div>; }
export function Empty({ title, text, href = '/shop', label = 'Explore the shop', icon }: { title: string; text: string; href?: string; label?: string; icon?: ReactNode }) { return <div className="empty-state">{icon || <ShoppingBag size={36} strokeWidth={1.3} />}<h2>{title}</h2><p>{text}</p><Link className="button" href={href}>{label}<ArrowRight size={16} /></Link></div>; }
export function Quantity({ value, max, onChange, disabled = false }: { value: number; max: number; onChange: (value: number) => void; disabled?: boolean }) { return <div className="quantity"><button aria-label="Decrease quantity" title="Decrease quantity" disabled={disabled || value <= 1} onClick={() => onChange(value - 1)}><Minus size={14} /></button><span>{value}</span><button aria-label="Increase quantity" title="Increase quantity" disabled={disabled || value >= max} onClick={() => onChange(value + 1)}><Plus size={14} /></button></div>; }
export function Status({ value }: { value: string }) { return <span className={`status status-${value.replaceAll(' ', '-')}`}>{value.replaceAll('_', ' ')}</span>; }
export function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="field"><span>{label}</span>{children}</label>; }
