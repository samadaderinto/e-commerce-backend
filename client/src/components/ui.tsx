"use client";
import Link from "next/link";
import { useState, useEffect, ReactNode } from "react";
import {
  AlertCircle,
  ArrowRight,
  Heart,
  ImageOff,
  Minus,
  Plus,
  ShoppingBag,
  Star,
} from "lucide-react";
import { Product, SellerTier } from "@/lib/types";
import { money } from "@/lib/api";
import { useShop } from "./providers";

export type TierLevel = 'official' | 'starter' | 'booster' | 'accelerator' | 'power' | 'mega' | 'legendary';

export const tierConfig: Record<TierLevel, { color: string; label: string; title: string }> = {
  official: {
    color: '#e5a93c', // Golden
    label: 'Official Store',
    title: 'Verified Official Partner Store (Gold Badge)',
  },
  starter: {
    color: '#1d9bf0', // Blue
    label: 'Starter Seller',
    title: 'Verified Starter Seller (Blue Badge)',
  },
  booster: {
    color: '#94a3b8', // Silver / Slate
    label: 'Booster Seller',
    title: 'Verified Booster Seller ($5,000+ Sales - Silver Badge)',
  },
  accelerator: {
    color: '#8b5cf6', // Electric Violet
    label: 'Accelerator Seller',
    title: 'Verified Accelerator Seller ($25,000+ Sales - Purple Badge)',
  },
  power: {
    color: '#10b981', // Emerald Green
    label: 'Power Seller',
    title: 'Verified Power Seller ($100,000+ Sales - Emerald Badge)',
  },
  mega: {
    color: '#0ea5e9', // Diamond Cyan
    label: 'Mega Seller',
    title: 'Verified Mega Seller ($500,000+ Sales - Diamond Badge)',
  },
  legendary: {
    color: '#ff0055', // Cosmic Ruby Flame
    label: 'Legendary Seller',
    title: 'Verified Legendary Seller ($1,000,000+ Sales - Cosmic Badge)',
  },
};

export function VerifiedBadge({
  tier = 'starter',
  tierData,
  size = 15,
  className = "",
}: {
  tier?: TierLevel;
  tierData?: SellerTier;
  size?: number;
  className?: string;
}) {
  const activeTier: TierLevel = (tierData?.tier as TierLevel) || tier;
  const config = tierConfig[activeTier] || tierConfig.starter;
  const color = tierData?.badge_hex || config.color;

  return (
    <span
      className={`verified-badge tier-${activeTier} ${className}`}
      title={tierData ? `Verified ${tierData.name} · ProAce Seller Network` : config.title}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        verticalAlign: "middle",
        color: color,
        flexShrink: 0,
      }}
    >
      {activeTier === 'legendary' ? (
        <svg
          width={size}
          height={size}
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          style={{ filter: "drop-shadow(0 0 3px rgba(255, 0, 85, 0.55))" }}
          aria-label={tierData ? `Verified ${tierData.name}` : config.label}
        >
          <defs>
            <linearGradient id="legendaryGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#ff007a" />
              <stop offset="50%" stopColor="#a855f7" />
              <stop offset="100%" stopColor="#ff0055" />
            </linearGradient>
          </defs>
          <path
            d="M12 1L14.7 5.7L20 4.5L18.8 9.8L23 12.5L18.8 15.2L20 20.5L14.7 19.3L12 24L9.3 19.3L4 20.5L5.2 15.2L1 12.5L5.2 9.8L4 4.5L9.3 5.7L12 1Z"
            fill="url(#legendaryGrad)"
          />
          <path
            d="M9.5 12.5L11 14L15 9.5"
            stroke="#ffffff"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ) : (
        <svg
          width={size}
          height={size}
          viewBox="0 0 24 24"
          fill="currentColor"
          aria-label={tierData ? `Verified ${tierData.name}` : config.label}
        >
          <path d="M22.25 12c0-1.43-.88-2.67-2.19-3.34.46-1.39.2-2.9-.81-3.91s-2.52-1.27-3.91-.81c-.67-1.31-1.91-2.19-3.34-2.19s-2.67.88-3.34 2.19c-1.39-.46-2.9-.2-3.91.81s-1.27 2.52-.81 3.91C2.63 9.33 1.75 10.57 1.75 12s.88 2.67 2.19 3.34c-.46 1.39-.2 2.9.81 3.91s2.52 1.27 3.91.81c.67 1.31 1.91 2.19 3.34 2.19s2.67-.88 3.34-2.19c1.39.46 2.9.2 3.91-.81s1.27-2.52.81-3.91c1.31-.67 2.19-1.91 2.19-3.34zm-11.79 3.84l-3.3-3.3 1.41-1.41 1.89 1.89 5.09-5.09 1.41 1.41-6.5 6.5z" />
        </svg>
      )}
    </span>
  );
}

export function ProductImage({
  src,
  alt,
  className = "",
}: {
  src?: string;
  alt: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  return src && !failed ? (
    <img
      className={className}
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  ) : (
    <div className={`image-placeholder ${className}`}>
      <ImageOff size={32} />
      <span>{alt}</span>
    </div>
  );
}
export function FlashCountdown({ end }: { end?: string | null }) {
  const [timeLeft, setTimeLeft] = useState<{ hours: number; minutes: number; seconds: number; expired: boolean } | null>(null);

  useEffect(() => {
    if (!end) return;
    function calculate() {
      const diff = new Date(end!).getTime() - new Date().getTime();
      if (diff <= 0) {
        setTimeLeft({ hours: 0, minutes: 0, seconds: 0, expired: true });
        return;
      }
      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);
      setTimeLeft({ hours, minutes, seconds, expired: false });
    }
    calculate();
    const interval = setInterval(calculate, 1000);
    return () => clearInterval(interval);
  }, [end]);

  if (!timeLeft || timeLeft.expired) return null;

  const pad = (n: number) => String(n).padStart(2, '0');

  return (
    <span
      className="flash-deal-badge"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 3,
        background: "#fee2e2",
        color: "#dc2626",
        padding: "1px 6px",
        borderRadius: "8px",
        fontSize: "10px",
        fontWeight: 700,
        letterSpacing: "0.02em"
      }}
      title="Limited-time Flash Deal"
    >
      <span>⚡</span>
      <span>{timeLeft.hours > 0 ? `${pad(timeLeft.hours)}:` : ''}{pad(timeLeft.minutes)}:{pad(timeLeft.seconds)}</span>
    </span>
  );
}

export function ProductCard({ product }: { product: Product }) {
  const { saved, toggleSave, add, notify } = useShop();
  const [busy, setBusy] = useState(false);
  const liked = saved.some((item) => item.id === product.id);
  return (
    <article className="product-card">
      <div className="product-photo">
        <Link
          href={`/products/${product.id}`}
          aria-label={`View ${product.title}`}
        >
          <ProductImage src={product.image} alt={product.title} />
        </Link>
        <div style={{ position: "absolute", top: 8, left: 8, display: "flex", flexDirection: "column", gap: 4, zIndex: 1 }}>
          {product.discount > 0 && (
            <span className="discount">−{product.discount}%</span>
          )}
          {product.flash_sale_end && (
            <FlashCountdown end={product.flash_sale_end} />
          )}
        </div>
        <button
          className={`icon-button save-button ${liked ? "saved" : ""}`}
          aria-label={`${liked ? "Unsave" : "Save"} ${product.title}`}
          title={liked ? "Remove from saved items" : "Save for later"}
          onClick={() =>
            toggleSave(product).catch((error) => notify(error.message, true))
          }
        >
          <Heart size={18} fill={liked ? "currentColor" : "none"} />
        </button>
        <button
          className="quick-add"
          disabled={busy || !product.available || product.is_own_store}
          onClick={async () => {
            setBusy(true);
            try {
              await add(product);
            } catch (error) {
              notify((error as Error).message, true);
            } finally {
              setBusy(false);
            }
          }}
        >
          <Plus size={16} />
          {product.is_own_store
            ? "Your listing"
            : !product.available
              ? "Sold out"
              : busy
                ? "Adding…"
                : "Add to bag"}
        </button>
      </div>
      <div className="product-meta">
        <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
          {product.brand || product.store_name}
          <VerifiedBadge
            tier={product.is_official_store ? "official" : "starter"}
            tierData={product.seller_tier}
            size={13}
          />
        </span>
        <span>
          <Star size={12} fill="currentColor" />
          {Number(product.average_rating) > 0
            ? Number(product.average_rating).toFixed(1)
            : "New"}
        </span>
      </div>
      <Link className="product-title" href={`/products/${product.id}`}>
        {product.title}
      </Link>
      <div className="price">
        <strong>{money(product.sale_price)}</strong>
        {product.discount > 0 && <del>{money(product.price)}</del>}
      </div>
    </article>
  );
}
export function ProductGrid({ products }: { products: Product[] }) {
  return (
    <div className="product-grid">
      {products.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  );
}
export function Loading({ cards = false }: { cards?: boolean }) {
  return cards ? (
    <div className="product-grid" aria-label="Loading products">
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className="skeleton-card">
          <div className="skeleton" />
          <div className="skeleton line" />
          <div className="skeleton line short" />
        </div>
      ))}
    </div>
  ) : (
    <div className="loading" role="status">
      <span className="spinner" />
      Loading…
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: Error;
  retry?: () => void;
}) {
  return (
    <div className="empty-state" role="alert">
      <AlertCircle size={32} />
      <h2>Something interrupted your visit</h2>
      <p>{error.message}</p>
      {retry && (
        <button className="button" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}
export function Empty({
  title,
  text,
  href = "/shop",
  label = "Explore the shop",
  icon,
}: {
  title: string;
  text: string;
  href?: string;
  label?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="empty-state">
      {icon || <ShoppingBag size={36} strokeWidth={1.3} />}
      <h2>{title}</h2>
      <p>{text}</p>
      <Link className="button" href={href}>
        {label}
        <ArrowRight size={16} />
      </Link>
    </div>
  );
}
export function Quantity({
  value,
  max,
  onChange,
  disabled = false,
}: {
  value: number;
  max: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="quantity">
      <button
        aria-label="Decrease quantity"
        title="Decrease quantity"
        disabled={disabled || value <= 1}
        onClick={() => onChange(value - 1)}
      >
        <Minus size={14} />
      </button>
      <span>{value}</span>
      <button
        aria-label="Increase quantity"
        title="Increase quantity"
        disabled={disabled || value >= max}
        onClick={() => onChange(value + 1)}
      >
        <Plus size={14} />
      </button>
    </div>
  );
}
export function Status({ value }: { value: string }) {
  return (
    <span className={`status status-${value.replaceAll(" ", "-")}`}>
      {value.replaceAll("_", " ")}
    </span>
  );
}
export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}
