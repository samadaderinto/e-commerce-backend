"use client";
import Link from "next/link";
import { useState, useEffect, useRef, ReactNode } from "react";
import {
  AlertCircle,
  Check,
  LoaderCircle,
  ChevronLeft,
  ChevronRight,
  ArrowRight,
  ArrowUpRight,
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
import { useSearchParams } from "next/navigation";

export type TierLevel = 'official' | 'starter' | 'booster' | 'accelerator' | 'power' | 'mega' | 'legendary';

export const tierConfig: Record<TierLevel, { color: string; label: string; title: string }> = {
  official: {
    color: '#d97706', // Radiant Gold
    label: 'Official Store',
    title: 'Verified Official Store',
  },
  starter: {
    color: '#2563eb', // Sapphire Blue
    label: 'Starter Seller',
    title: 'Verified Starter Seller (Blue Badge)',
  },
  booster: {
    color: '#64748b', // Slate Silver
    label: 'Booster Seller',
    title: 'Verified Booster Seller ($5,000+ Sales - Silver Badge)',
  },
  accelerator: {
    color: '#7c3aed', // Electric Purple
    label: 'Accelerator Seller',
    title: 'Verified Accelerator Seller ($25,000+ Sales - Purple Badge)',
  },
  power: {
    color: '#059669', // Emerald Green
    label: 'Power Seller',
    title: 'Verified Power Seller ($100,000+ Sales - Emerald Badge)',
  },
  mega: {
    color: '#ea580c', // Flame Orange
    label: 'Mega Seller',
    title: 'Verified Mega Seller ($500,000+ Sales - Flame Orange Badge)',
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

export function normalizeImageUrl(url?: string | null): string {
  if (!url) return '';
  let clean = url.trim();
  if (clean.includes('minio:9000')) {
    clean = clean.replace(/https?:\/\/minio:9000/g, 'http://127.0.0.1:9000');
  }
  if (clean.includes('/media/') && clean.includes('?')) {
    clean = clean.split('?')[0];
  }
  return clean;
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
  const resolvedSrc = normalizeImageUrl(src);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [resolvedSrc]);

  return resolvedSrc && !failed ? (
    <img
      className={className}
      src={resolvedSrc}
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

export function ProductGallery({
  images,
  title,
  discount,
  activeImage,
  onImageChange,
}: {
  images: string[];
  title: string;
  discount: number;
  activeImage?: string;
  onImageChange?: (image: string) => void;
}) {
  const photos = [...new Set(images.map(normalizeImageUrl).filter(Boolean))];
  const normalizedActive = activeImage ? normalizeImageUrl(activeImage) : undefined;

  const [selected, setSelected] = useState<number>(() => {
    if (normalizedActive) {
      const idx = photos.indexOf(normalizedActive);
      if (idx >= 0) return idx;
    }
    return 0;
  });

  const prevPropRef = useRef<string | undefined>(normalizedActive);
  const touchStart = useRef<number | null>(null);

  // Synchronize with external activeImage prop changes (e.g. variant selection)
  useEffect(() => {
    if (normalizedActive !== prevPropRef.current) {
      prevPropRef.current = normalizedActive;
      if (normalizedActive) {
        const idx = photos.indexOf(normalizedActive);
        if (idx >= 0) {
          setSelected(idx);
        }
      }
    }
  }, [normalizedActive, photos]);

  const current = Math.min(selected, Math.max(0, photos.length - 1));

  const selectPhoto = (index: number) => {
    const validIndex = Math.min(Math.max(0, index), Math.max(0, photos.length - 1));
    setSelected(validIndex);
    onImageChange?.(photos[validIndex]);
  };

  const move = (direction: number) => {
    if (photos.length === 0) return;
    selectPhoto((current + direction + photos.length) % photos.length);
  };

  return (
    <div className="gallery" role="region" aria-roledescription="carousel" aria-label={`${title} photos`}>
      <div className="gallery-main" tabIndex={photos.length > 1 ? 0 : undefined}
        onKeyDown={event => {
          if (photos.length < 2) return;
          if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
            event.preventDefault();
            move(event.key === 'ArrowLeft' ? -1 : 1);
          }
        }}
        onTouchStart={event => { touchStart.current = event.touches[0].clientX; }}
        onTouchEnd={event => {
          if (touchStart.current !== null && photos.length > 1) {
            const distance = event.changedTouches[0].clientX - touchStart.current;
            if (Math.abs(distance) > 50) move(distance > 0 ? -1 : 1);
          }
          touchStart.current = null;
        }}
        onTouchCancel={() => {
          touchStart.current = null;
        }}
      >
        <ProductImage
          key={photos[current] || 'placeholder'}
          src={photos[current]}
          alt={`${title} — photo ${current + 1}`}
        />
        {discount > 0 && <span className="discount">Save {discount}%</span>}
        {photos.length > 1 && (
          <>
            <button
              type="button"
              className="gallery-arrow gallery-arrow-prev"
              aria-label="Previous product photo"
              onClick={() => move(-1)}
            >
              <ChevronLeft size={22} />
            </button>
            <button
              type="button"
              className="gallery-arrow gallery-arrow-next"
              aria-label="Next product photo"
              onClick={() => move(1)}
            >
              <ChevronRight size={22} />
            </button>
            <span className="gallery-counter" aria-live="polite" aria-atomic="true">
              {current + 1} / {photos.length}
            </span>
          </>
        )}
      </div>
      {photos.length > 1 && (
        <div className="gallery-thumbs">
          {photos.map((src, index) => (
            <button
              type="button"
              key={src}
              aria-label={`View photo ${index + 1}`}
              aria-pressed={current === index}
              className={current === index ? 'active' : ''}
              onClick={() => selectPhoto(index)}
            >
              <ProductImage src={src} alt={`${title} view ${index + 1}`} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function FlashCountdown({ end }: { end?: string | null }) {
  const [timeLeft, setTimeLeft] = useState<{ months: number; days: number; hours: number; minutes: number; seconds: number; expired: boolean } | null>(null);

  useEffect(() => {
    if (!end) return;
    function calculate() {
      const diff = new Date(end!).getTime() - new Date().getTime();
      if (!Number.isFinite(diff) || diff <= 0) {
        setTimeLeft({ months: 0, days: 0, hours: 0, minutes: 0, seconds: 0, expired: true });
        return;
      }
      const totalHours = Math.floor(diff / (1000 * 60 * 60));
      const totalDays = Math.floor(totalHours / 24);
      // Countdown months use a fixed 30-day duration.
      const months = Math.floor(totalDays / 30);
      const days = totalDays % 30;
      const hours = totalHours % 24;
      const minutes = Math.floor(diff / 60000) % 60;
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);
      setTimeLeft({ months, days, hours, minutes, seconds, expired: false });
    }
    calculate();
    const interval = setInterval(calculate, 1000);
    return () => clearInterval(interval);
  }, [end]);

  if (!end || !timeLeft || timeLeft.expired) return null;

  const pad = (n: number) => String(n).padStart(2, '0');

  return (
    <span
      className="flash-deal-badge"
      title="Flash deal ends in months:days:hours:minutes:seconds (30-day months)"
      aria-label={`Flash deal ends in ${timeLeft.months} months, ${timeLeft.days} days, ${timeLeft.hours} hours, ${timeLeft.minutes} minutes and ${timeLeft.seconds} seconds`}
    >
      <span aria-hidden="true">⚡</span>
      <span style={{ fontVariantNumeric: "tabular-nums" }}>
        {pad(timeLeft.months)}:{pad(timeLeft.days)}:{pad(timeLeft.hours)}:{pad(timeLeft.minutes)}:{pad(timeLeft.seconds)}
      </span>
    </span>
  );
}

export function ProductCard({ product }: { product: Product }) {
  const { saved, toggleSave, notify, user } = useShop();
  const params = useSearchParams();
  const preview = params.get('preview') === '1' && Boolean(user?.is_staff || user?.is_superuser || user?.is_business_admin);
  const isAffiliate = product.product_type === 'affiliate_clickbank';
  const isSoldOut = !product.is_digital && !isAffiliate && (product.available <= 0 || product.label === 'sold out');
  const productHref = `/products/${product.id}${preview ? '?preview=1' : ''}`;
  const liked = saved.some((item) => item.id === product.id);
  return (
    <article className="product-card">
      <div className="product-photo">
        <Link
          href={productHref}
          aria-label={`View ${product.title}`}
        >
          <ProductImage src={product.image} alt={product.title} />
        </Link>
        {(isAffiliate || isSoldOut || (!isAffiliate && (product.flash_sale_end || product.discount > 0))) && (
          <div className="product-badges">
            {isAffiliate && (
              <span className="discount partner-badge">
                Partner Offer
              </span>
            )}
            {isSoldOut && (
              <span className="discount sold-out-badge">
                Sold Out
              </span>
            )}
            {!isAffiliate && !isSoldOut && product.flash_sale_end && (
              <FlashCountdown end={product.flash_sale_end} />
            )}
            {!isAffiliate && !isSoldOut && product.discount > 0 && (
              <span className="discount">−{product.discount}%</span>
            )}
          </div>
        )}
        <button
          className={`icon-button save-button ${liked ? "saved" : ""}`}
          aria-label={`${liked ? "Unsave" : "Save"} ${product.title}`}
          title={liked ? "Remove from saved items" : "Save for later"}
          disabled={preview}
          onClick={() =>
            toggleSave(product).catch((error) => notify(error.message, true))
          }
        >
          <Heart size={18} fill={liked ? "currentColor" : "none"} />
        </button>
        <AddToBagButton product={product} className="quick-add" />
      </div>
      <div className="product-meta">
        <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
          {isAffiliate ? (
            <>
              <span>{product.brand || 'Partner Offer'}</span>
              <span className="seller-tier-pill partner-pill">ClickBank</span>
            </>
          ) : (
            <>
              {product.brand || product.store_name}
              <VerifiedBadge
                tier={product.is_official_store ? "official" : "starter"}
                tierData={product.seller_tier}
                size={13}
              />
            </>
          )}
        </span>
        <span>
          <Star size={12} fill="currentColor" />
          {Number(product.average_rating) > 0
            ? Number(product.average_rating).toFixed(1)
            : "New"}
        </span>
      </div>
      <Link className="product-title" href={productHref}>
        {product.title}
      </Link>
      <div className="price">
        <strong>{isAffiliate ? "Check price on partner site" : money(product.sale_price)}</strong>
        {!isAffiliate && product.discount > 0 && <del>{money(product.price)}</del>}
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
  onAction,
}: {
  title: string;
  text: string;
  href?: string;
  label?: string;
  icon?: ReactNode;
  onAction?: () => void;
}) {
  return (
    <div className="empty-state">
      {icon || <ShoppingBag size={36} strokeWidth={1.3} />}
      <h2>{title}</h2>
      <p>{text}</p>
      {onAction ? (
        <button type="button" className="button" onClick={onAction}>
          {label}
          <ArrowRight size={16} />
        </button>
      ) : (
        <Link className="button" href={href}>
          {label}
          <ArrowRight size={16} />
        </Link>
      )}
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

export function Pagination({
  page,
  totalPages,
  onChange,
}: {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
}) {
  if (totalPages <= 1) return null;
  const current = Math.max(1, Math.min(page, totalPages));
  const pages = [
    ...new Set(
      [1, totalPages, current - 1, current, current + 1].filter(
        (value) => value >= 1 && value <= totalPages
      )
    ),
  ].sort((a, b) => a - b);

  return (
    <nav className="pagination" aria-label="Pagination">
      <button
        aria-label="Previous page"
        disabled={current === 1}
        onClick={() => onChange(current - 1)}
      >
        ‹
      </button>
      <span className="pagination-compact" aria-live="polite">
        Page {current} of {totalPages}
      </span>
      <span className="pagination-pages">
        {pages.map((value, index) => (
          <span key={value}>
            {index > 0 && value - pages[index - 1] > 1 && (
              <span className="pagination-ellipsis" aria-hidden="true">
                …
              </span>
            )}
            <button
              aria-label={`Page ${value}`}
              aria-current={value === current ? "page" : undefined}
              className={value === current ? "active" : ""}
              onClick={() => onChange(value)}
            >
              {value}
            </button>
          </span>
        ))}
      </span>
      <button
        aria-label="Next page"
        disabled={current === totalPages}
        onClick={() => onChange(current + 1)}
      >
        ›
      </button>
    </nav>
  );
}

export function AddToBagButton({
  product,
  quantity = 1,
  className = "button",
}: {
  product: Product;
  quantity?: number;
  className?: string;
}) {
  const { cart, add, notify, cartLoading, cartError, user } = useShop();
  const params = useSearchParams();
  const preview =
    params.get("preview") === "1" &&
    Boolean(user?.is_staff || user?.is_superuser || user?.is_business_admin);
  const [busy, setBusy] = useState(false);
  const [added, setAdded] = useState(false);
  const locked = useRef(false);

  // If this is an external affiliate product, render direct outbound link to ClickBank tracking endpoint
  if (product.product_type === "affiliate_clickbank") {
    const outboundUrl = `/api/affiliates/clickbank/outbound/${product.id}`;
    const label = product.affiliate_button_text || "Buy on Partner Site";
    return (
      <a
        href={outboundUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={className}
        title="View offer directly on partner site"
        style={{
          textDecoration: "none",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "8px",
          background: "#ea580c",
          borderColor: "#ea580c",
          color: "#ffffff",
          fontWeight: 600,
        }}
      >
        <ArrowUpRight size={16} />
        <span>{label}</span>
      </a>
    );
  }

  const current =
    cart.items.find(
      (row) =>
        row.product.id === product.id &&
        (row.product.selected_variant || "") ===
          (product.selected_variant || product.variants?.[0]?.name || "")
    )?.quantity || 0;
  const committed = current >= quantity;
  const capped = !product.is_digital && current >= product.available;

  useEffect(() => {
    if (!added) return;
    const timer = window.setTimeout(() => setAdded(false), 1800);
    return () => window.clearTimeout(timer);
  }, [added]);

  async function submit() {
    if (locked.current || committed) return;
    locked.current = true;
    setBusy(true);
    try {
      await add(product, quantity - current);
      setAdded(true);
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }

  const isSoldOut = !product.is_digital && (!product.available || product.available <= 0 || product.label === "sold out");

  const label = preview
    ? "Preview only"
    : product.is_own_store
      ? "Your listing"
      : product.store_verified === false
        ? "Preview only"
        : isSoldOut
          ? "Out of stock"
          : busy
            ? "Adding…"
            : capped
              ? "Max quantity in bag"
              : added
                ? "Added!"
                : committed
                  ? `${current} in bag`
                  : "Add to bag";

  const isDisabled =
    preview ||
    busy ||
    cartLoading ||
    !!cartError ||
    committed ||
    isSoldOut ||
    (!product.is_digital && quantity > product.available) ||
    product.is_own_store ||
    product.store_verified === false;

  return (
    <button
      type="button"
      className={className}
      disabled={isDisabled}
      onClick={submit}
      aria-busy={busy}
    >
      {busy ? (
        <LoaderCircle className="bag-spinner" size={16} />
      ) : added || committed ? (
        <Check size={16} />
      ) : (
        <Plus size={16} />
      )}
      {label}
    </button>
  );
}

export function useDialogFocus(open: boolean, close: () => void) {
  const ref = useRef<HTMLElement>(null);
  const closeRef = useRef(close);
  closeRef.current = close;

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const controls = () =>
      Array.from(
        ref.current?.querySelectorAll<HTMLElement>(
          "button:not(:disabled), input:not(:disabled), select, textarea, a[href]"
        ) || []
      );

    controls()[0]?.focus();

    const keyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeRef.current();
      }
      if (event.key !== "Tab") return;

      const items = controls();
      const first = items[0];
      const last = items[items.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };

    document.addEventListener("keydown", keyboard);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", keyboard);
      previous?.focus();
    };
  }, [open]);

  return ref;
}
