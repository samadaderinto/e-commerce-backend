"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  Calendar,
  Check,
  ChevronRight,
  Globe,
  Heart,
  Headphones,
  Laptop,
  Mail,
  MapPin,
  MessageCircle,
  Phone,
  Shirt,
  Smartphone,
  Dumbbell,
  BookOpen,
  SlidersHorizontal,
  Star,
  Truck,
  ShieldCheck,
  Store as StoreIcon,
  X,
} from "lucide-react";
import { api, categories, money } from "@/lib/api";
import type { Page, Product, PublicStore, Review } from "@/lib/types";
import {
  Empty,
  ErrorState,
  Field,
  FlashCountdown,
  Loading,
  ProductGrid,
  ProductImage,
  Quantity,
  VerifiedBadge,
} from "./ui";
import { useShop } from "./providers";

const categoryIcons = [
  Headphones,
  Shirt,
  Smartphone,
  Laptop,
  Dumbbell,
  BookOpen,
];

export function HomePage() {
  const products = useQuery({
    queryKey: ["products", "home"],
    queryFn: () => api<Page<Product>>("products?ordering=-sales"),
  });
  return (
    <>
      <section className="hero">
        <img
          className="hero-image"
          src="https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=2000&q=90"
          alt="Yellow studio backdrop with a pair of over-ear headphones"
          fetchPriority="high"
        />
        <div className="container hero-content">
          <span className="eyebrow">THE EVERYDAY EDIT · VOL. 01</span>
          <h1>
            Everyday
            <br />
            essentials.
          </h1>
          <p>
            Good design. Great finds.
            <br />A little more you, every day.
          </p>
          <Link href="/shop" className="button dark">
            Find your next favourite <ArrowUpRight size={18} />
          </Link>
          <span className="hero-note">
            Thoughtfully selected. Refreshingly priced.
          </span>
        </div>
        <span className="hero-index">
          THE SOUND EDIT <span />
        </span>
      </section>
      <div className="category-tiles container">
        {categories.map((category, index) => {
          const Icon = categoryIcons[index];
          return (
            <Link href={`/shop?category=${category.key}`} key={category.key}>
              <span className={`category-symbol symbol-${index}`}>
                <Icon size={24} strokeWidth={1.4} />
              </span>
              <span>{category.name}</span>
              <ArrowUpRight size={14} />
            </Link>
          );
        })}
      </div>
      <section className="container section">
        <div className="section-heading">
          <div>
            <span className="eyebrow green">A FEW GOOD FINDS</span>
            <h2>Your next favourites</h2>
          </div>
          <Link className="text-link" href="/shop">
            Shop all products <ArrowRight size={17} />
          </Link>
        </div>
        {products.isLoading ? (
          <Loading cards />
        ) : products.error ? (
          <ErrorState error={products.error} retry={() => products.refetch()} />
        ) : (
          <ProductGrid products={products.data?.results.slice(0, 8) || []} />
        )}
      </section>
      <section className="editorial-band">
        <div className="container editorial-inner">
          <span className="eyebrow">LESS SEARCHING. MORE DISCOVERING.</span>
          <h2>
            Small upgrades.
            <br />
            Better everydays.
          </h2>
          <p>
            From your morning playlist to your next big idea,
            <br />
            find the things that make your day.
          </p>
          <Link className="button" href="/shop?deals=true">
            Discover everyday deals <ArrowUpRight size={17} />
          </Link>
          <img
            src="https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=800&q=85"
            alt="Minimal white watch with a grey strap"
            loading="lazy"
          />
        </div>
      </section>
      <section className="container section">
        <div className="section-heading">
          <div>
            <span className="eyebrow green">GOOD THINGS, BETTER PRICES</span>
            <h2>A little less. A lot to love.</h2>
          </div>
          <Link className="text-link" href="/shop?deals=true">
            See all deals <ArrowRight size={17} />
          </Link>
        </div>
        {products.data && (
          <ProductGrid
            products={products.data.results
              .filter((product) => product.discount > 0)
              .slice(0, 4)}
          />
        )}
      </section>
    </>
  );
}

export function ShopPage() {
  const params = useSearchParams();
  const router = useRouter();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const query = params.toString();
  const products = useQuery({
    queryKey: ["products", query],
    queryFn: () => api<Page<Product>>(`products?${query}`),
  });
  const category = categories.find(
    (category) => category.key === params.get("category"),
  );
  const storeId = params.get("store");
  const storeQuery = useQuery({
    queryKey: ["public-store", storeId],
    queryFn: () => api<PublicStore>(`stores/${storeId}/public`),
    enabled: !!storeId && /^\d+$/.test(storeId),
  });

  const storeData = storeQuery.data;
  const storeProfile = storeData?.profile;
  const firstProduct = products.data?.results?.[0];
  const storeName = storeData?.name || firstProduct?.store_name || (storeId ? `Store #${storeId}` : null);
  const isOfficialStore = Boolean(storeData?.is_official ?? firstProduct?.is_official_store);

  const title = storeName
    ? storeName
    : params.get("search")
      ? `Results for “${params.get("search")}”`
      : category?.name ||
        (params.has("deals") ? "Everyday deals" : "A world of good finds");

  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    router.push(`/shop?${next}`, { scroll: false });
  }

  return (
    <div className="container shop-page">
      <div className="breadcrumb">
        <Link href="/">Home</Link>
        <ChevronRight size={12} />
        {storeName ? (
          <>
            <Link href="/shop">Marketplace</Link>
            <ChevronRight size={12} />
            <span>{storeName}</span>
          </>
        ) : (
          <span>Shop</span>
        )}
        {category && (
          <>
            <ChevronRight size={12} />
            <span>{category.name}</span>
          </>
        )}
      </div>

      {storeName && storeId ? (
        <section
          className="store-profile-header"
          style={{
            marginBottom: "28px",
            border: "1px solid var(--line)",
            borderRadius: "12px",
            overflow: "hidden",
            background: "#fff",
            boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
          }}
        >
          {/* Header Cover Banner */}
          <div
            style={{
              height: "170px",
              width: "100%",
              background: storeProfile?.banner_url
                ? `url(${storeProfile.banner_url}) center/cover no-repeat`
                : "linear-gradient(135deg, #1d9bf0 0%, #0e3d29 100%)",
              position: "relative"
            }}
          />

          {/* Announcement Bar */}
          {storeProfile?.announcement && (
            <div
              style={{
                background: "linear-gradient(90deg, #ecfdf5 0%, #f0fdf4 100%)",
                borderBottom: "1px solid #a7f3d0",
                padding: "8px 24px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "12px",
                fontWeight: 600,
                color: "#065f46"
              }}
            >
              <span>📢</span>
              <span>{storeProfile.announcement}</span>
            </div>
          )}

          {/* Profile Details Container */}
          <div style={{ padding: "0 28px 24px", position: "relative" }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-end",
                flexWrap: "wrap",
                gap: "16px",
                marginTop: "-50px",
                marginBottom: "16px"
              }}
            >
              {/* Circular Avatar */}
              <div
                style={{
                  width: "100px",
                  height: "100px",
                  borderRadius: "50%",
                  border: "4px solid #fff",
                  overflow: "hidden",
                  background: "#edf2ea",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.12)",
                  display: "grid",
                  placeItems: "center",
                  position: "relative",
                  zIndex: 2
                }}
              >
                {storeProfile?.avatar_url ? (
                  <img
                    src={storeProfile.avatar_url}
                    alt={storeName}
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                  />
                ) : (
                  <span style={{ fontSize: "36px", fontWeight: 700, color: "var(--green)" }}>
                    {storeName?.[0] || "S"}
                  </span>
                )}
              </div>

              {/* Action and Contact links */}
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                {storeProfile?.email && (
                  <a
                    href={`mailto:${storeProfile.email}?subject=Inquiry regarding ${storeName}`}
                    className="button secondary"
                    style={{ minHeight: "34px", padding: "6px 13px", fontSize: "11px", borderRadius: "20px" }}
                  >
                    <Mail size={14} /> Message Store
                  </a>
                )}
                {storeProfile?.website && (
                  <a
                    href={storeProfile.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="button secondary"
                    style={{ minHeight: "34px", padding: "6px 13px", fontSize: "11px", borderRadius: "20px" }}
                  >
                    <Globe size={14} /> Website <ArrowUpRight size={12} />
                  </a>
                )}
                {storeProfile?.phone1 && (
                  <a
                    href={`tel:${storeProfile.phone1}`}
                    className="button secondary"
                    style={{ minHeight: "34px", padding: "6px 13px", fontSize: "11px", borderRadius: "20px" }}
                  >
                    <Phone size={14} /> {storeProfile.phone1}
                  </a>
                )}
                {storeProfile?.whatsapp && (
                  <a
                    href={`https://wa.me/${String(storeProfile.whatsapp).replace(/\D/g, "")}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="button secondary"
                    style={{ minHeight: "34px", padding: "6px 13px", fontSize: "11px", borderRadius: "20px" }}
                  >
                    <MessageCircle size={14} /> WhatsApp
                  </a>
                )}
              </div>
            </div>

            {/* Store Name, Verified Badge, Username */}
            <div style={{ marginBottom: "12px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                <h1 style={{ fontSize: "26px", margin: 0, fontWeight: 750, letterSpacing: "-0.02em" }}>
                  {storeName}
                </h1>
                <VerifiedBadge
                  tier={isOfficialStore ? "official" : "starter"}
                  tierData={storeData?.seller_tier || firstProduct?.seller_tier}
                  size={22}
                />
                <span
                  style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    padding: "3px 9px",
                    borderRadius: "12px",
                    background: isOfficialStore
                      ? "#fef3c7"
                      : (storeData?.seller_tier?.tier === "legendary"
                          ? "#ffe4e6"
                          : storeData?.seller_tier?.tier === "mega"
                            ? "#e0f2fe"
                            : storeData?.seller_tier?.tier === "power"
                              ? "#d1fae5"
                              : storeData?.seller_tier?.tier === "accelerator"
                                ? "#ede9fe"
                                : storeData?.seller_tier?.tier === "booster"
                                  ? "#f1f5f9"
                                  : "#e0f2fe"),
                    color: isOfficialStore
                      ? "#b45309"
                      : (storeData?.seller_tier?.tier === "booster"
                          ? "#475569"
                          : storeData?.seller_tier?.badge_hex || "#1d9bf0"),
                    border: storeData?.seller_tier?.tier === "legendary" ? "1px solid #fecdd3" : "none",
                    letterSpacing: "0.05em"
                  }}
                >
                  {isOfficialStore
                    ? "Official Partner Store (Gold)"
                    : (storeData?.seller_tier?.name
                        ? `${storeData.seller_tier.name}`
                        : "Verified Merchant")}
                </span>
              </div>
              <p className="muted" style={{ fontSize: "13px", margin: "4px 0 0" }}>
                @{storeData?.username || firstProduct?.store_username || "store"}
              </p>
            </div>

            {/* Bio */}
            {(storeProfile?.bio || isOfficialStore) && (
              <p style={{ fontSize: "13px", lineHeight: 1.6, maxWidth: "780px", color: "var(--ink)", margin: "0 0 16px" }}>
                {storeProfile?.bio ||
                  "Official direct brand flagship. High quality catalog with guaranteed authentic products and direct marketplace fulfillment."}
              </p>
            )}

            {/* Info Badges (Location, Email, Joined date, Total listings) */}
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "14px 22px",
                fontSize: "12px",
                color: "var(--muted)",
                paddingTop: "12px",
                borderTop: "1px solid var(--line)"
              }}
            >
              {storeData?.address && (
                <span style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}>
                  <MapPin size={14} />
                  {[storeData.address.city, storeData.address.state, storeData.address.country]
                    .filter(Boolean)
                    .join(", ")}
                </span>
              )}
              {storeProfile?.email && (
                <a
                  href={`mailto:${storeProfile.email}`}
                  style={{ display: "inline-flex", alignItems: "center", gap: "5px", color: "inherit" }}
                >
                  <Mail size={14} />
                  {storeProfile.email}
                </a>
              )}
              {storeData?.created && (
                <span style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}>
                  <Calendar size={14} />
                  Joined{" "}
                  {new Date(storeData.created).toLocaleDateString("en-US", {
                    month: "short",
                    year: "numeric"
                  })}
                </span>
              )}
              <span style={{ display: "inline-flex", alignItems: "center", gap: "5px", fontWeight: 600, color: "var(--ink)" }}>
                <strong>{products.data?.count ?? 0}</strong> Listings
              </span>
            </div>
          </div>
        </section>
      ) : (
        <div className="shop-heading">
          <div>
            <span className="eyebrow green">THE PROACE COLLECTION</span>
            <h1>{title}</h1>
            <p>Considered essentials. Unexpected favourites.</p>
          </div>
          <span className="result-total">
            {products.data?.count ?? "…"} products
          </span>
        </div>
      )}

      {storeName && (
        <div style={{ display: "flex", gap: "8px", overflowX: "auto", padding: "14px 0", borderBottom: "1px solid var(--line)", marginBottom: "16px" }}>
          <button
            className={`button secondary ${!params.has("category") ? "active" : ""}`}
            style={{
              padding: "6px 14px",
              minHeight: "34px",
              fontSize: "11px",
              borderRadius: "20px",
              background: !params.has("category") ? "var(--green)" : "white",
              color: !params.has("category") ? "white" : "var(--ink)",
              borderColor: !params.has("category") ? "var(--green)" : "var(--line)"
            }}
            onClick={() => update("category", "")}
          >
            All Products
          </button>
          {categories.map((cat) => {
            const active = params.get("category") === cat.key;
            return (
              <button
                key={cat.key}
                className={`button secondary ${active ? "active" : ""}`}
                style={{
                  padding: "6px 14px",
                  minHeight: "34px",
                  fontSize: "11px",
                  borderRadius: "20px",
                  background: active ? "var(--green)" : "white",
                  color: active ? "white" : "var(--ink)",
                  borderColor: active ? "var(--green)" : "var(--line)",
                  whiteSpace: "nowrap"
                }}
                onClick={() => update("category", cat.key)}
              >
                {cat.name}
              </button>
            );
          })}
        </div>
      )}
      <div className="shop-layout">
        <aside className={`filters ${filtersOpen ? "open" : ""}`}>
          <div className="filter-heading">
            <h3>Filters</h3>
            <button
              className="text-button"
              onClick={() => router.push("/shop")}
            >
              Reset
            </button>
            <button
              className="icon-button filter-close"
              aria-label="Close filters"
              onClick={() => setFiltersOpen(false)}
            >
              <X size={19} />
            </button>
          </div>
          <h4>Categories</h4>
          <label className="check-row">
            <input
              type="radio"
              checked={!params.has("category")}
              onChange={() => update("category", "")}
            />
            All products
          </label>
          {categories.map((item) => (
            <label className="check-row" key={item.key}>
              <input
                type="radio"
                checked={params.get("category") === item.key}
                onChange={() => update("category", item.key)}
              />
              {item.name}
            </label>
          ))}
          <h4>Price range</h4>
          <div className="price-inputs">
            <label>
              <span>From $</span>
              <input
                aria-label="Minimum price"
                type="number"
                min="0"
                placeholder="0"
                defaultValue={params.get("min_price") || ""}
                key={`min${params.get("min_price")}`}
                onBlur={(event) => update("min_price", event.target.value)}
              />
            </label>
            <span>–</span>
            <label>
              <span>To $</span>
              <input
                aria-label="Maximum price"
                type="number"
                min="0"
                placeholder="Any"
                defaultValue={params.get("max_price") || ""}
                key={`max${params.get("max_price")}`}
                onBlur={(event) => update("max_price", event.target.value)}
              />
            </label>
          </div>
          <h4>Good deals</h4>
          <label className="check-row">
            <input
              type="checkbox"
              checked={params.get("deals") === "true"}
              onChange={(event) =>
                update("deals", event.target.checked ? "true" : "")
              }
            />
            On sale
          </label>
          <div className="filter-help">
            <Truck size={25} />
            <h4>Delivery that fits the order.</h4>
            <p>
              Digital delivery is free. Physical shipping varies by provider,
              size, weight and destination.
            </p>
          </div>
        </aside>
        <div className="shop-results">
          <div className="results-toolbar">
            <button
              className="button secondary filter-toggle"
              onClick={() => setFiltersOpen(true)}
            >
              <SlidersHorizontal size={16} />
              Filters
            </button>
            <span>
              {category?.name || "All products"}{" "}
              <span className="muted">/ {products.data?.count ?? 0} finds</span>
            </span>
            <label className="sort-control">
              Sort by{" "}
              <select
                aria-label="Sort products"
                value={params.get("ordering") || "-created"}
                onChange={(event) => update("ordering", event.target.value)}
              >
                <option value="-created">Newest arrivals</option>
                <option value="-sales">Most popular</option>
                <option value="price">Price: low to high</option>
                <option value="-price">Price: high to low</option>
                <option value="-discount">Biggest savings</option>
                <option value="-average_rating">Top rated</option>
              </select>
            </label>
          </div>
          {products.isLoading ? (
            <Loading cards />
          ) : products.error ? (
            <ErrorState
              error={products.error}
              retry={() => products.refetch()}
            />
          ) : !products.data?.results.length ? (
            <Empty
              title="No finds just yet"
              text="Try a different search or give your filters a little more room."
            />
          ) : (
            <ProductGrid products={products.data.results} />
          )}
          {products.data && products.data.pages! > 1 && (
            <div className="pagination">
              {Array.from({ length: products.data.pages! }, (_, index) => (
                <button
                  className={
                    Number(params.get("page") || 1) === index + 1
                      ? "active"
                      : ""
                  }
                  key={index}
                  onClick={() => update("page", String(index + 1))}
                >
                  {index + 1}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function ProductPage({ id }: { id: string }) {
  const { add, notify, toggleSave, saved, user } = useShop();
  const client = useQueryClient();
  const productQuery = useQuery({
    queryKey: ["product", id],
    queryFn: () => api<Product>(`products/${id}`),
  });
  const reviews = useQuery({
    queryKey: ["reviews", id],
    queryFn: () => api<Review[]>(`products/${id}/reviews`),
  });
  const related = useQuery({
    queryKey: ["related", productQuery.data?.category],
    queryFn: () =>
      api<Page<Product>>(`products?category=${productQuery.data?.category}`),
    enabled: !!productQuery.data,
  });
  const [quantity, setQuantity] = useState(1);
  const [image, setImage] = useState(0);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState("details");
  const [reviewBusy, setReviewBusy] = useState(false);
  const [selectedVariantIdx, setSelectedVariantIdx] = useState<number>(0);
  if (productQuery.isLoading) return <Loading />;
  if (productQuery.error)
    return (
      <ErrorState
        error={productQuery.error}
        retry={() => productQuery.refetch()}
      />
    );
  const product = productQuery.data!;
  const activeVariant = product.variants && product.variants.length > 0 ? product.variants[selectedVariantIdx] : null;
  const effectiveStock = activeVariant && typeof activeVariant.available === 'number' ? activeVariant.available : product.available;
  const variantPriceDelta = activeVariant?.price_delta ? Number(activeVariant.price_delta) : 0;
  const effectiveSalePrice = (Number(product.sale_price) + variantPriceDelta).toFixed(2);
  const effectiveOriginalPrice = (Number(product.price) + variantPriceDelta).toFixed(2);
  const liked = saved.some((row) => row.id === product.id);
  async function review(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    setReviewBusy(true);
    try {
      const imagesRaw = (data.images as string || "")
        .split(/[\n,]/)
        .map((s) => s.trim())
        .filter((s) => s.length > 0 && (s.startsWith("http://") || s.startsWith("https://") || s.startsWith("data:image/")));

      await api(`products/${id}/reviews`, "POST", {
        rating: Number(data.rating),
        label: data.label,
        comment: data.comment,
        images: imagesRaw.slice(0, 3),
      });
      await client.invalidateQueries({ queryKey: ["reviews", id] });
      await client.invalidateQueries({ queryKey: ["product", id] });
      notify("Thanks for sharing your experience");
      form.reset();
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setReviewBusy(false);
    }
  }
  return (
    <div className="container product-page">
      <div className="breadcrumb">
        <Link href="/">Home</Link>
        <ChevronRight size={12} />
        <Link href="/shop">Shop</Link>
        <ChevronRight size={12} />
        <span>{product.title}</span>
      </div>
      <div className="product-detail">
        <div className="gallery">
          <div className="gallery-main">
            <ProductImage
              src={product.images[image] || product.image}
              alt={product.title}
            />
            {product.discount > 0 && (
              <span className="discount">Save {product.discount}%</span>
            )}
          </div>
          {product.images.length > 1 && (
            <div className="gallery-thumbs">
              {product.images.map((src, index) => (
                <button
                  aria-label={`View photo ${index + 1}`}
                  className={image === index ? "active" : ""}
                  key={src}
                  onClick={() => setImage(index)}
                >
                  <ProductImage
                    src={src}
                    alt={`${product.title} view ${index + 1}`}
                  />
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="product-information">
          <span className="eyebrow green" style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            {product.brand || product.store_name}
            <VerifiedBadge
              tier={product.is_official_store ? "official" : "starter"}
              tierData={product.seller_tier}
              size={14}
            />
          </span>
          <h1>{product.title}</h1>
          <div className="rating-line" style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <Star size={16} fill="currentColor" />
              <strong>
                {Number(product.average_rating) > 0
                  ? Number(product.average_rating).toFixed(1)
                  : "New arrival"}
              </strong>
            </span>
            <span style={{ color: "var(--line)" }}>•</span>
            <button className="text-button" onClick={() => setTab("reviews")}>
              {reviews.data?.length || product.rating_count || 0} reviews
            </button>
            {typeof product.sales === "number" && product.sales > 0 && (
              <>
                <span style={{ color: "var(--line)" }}>•</span>
                <span style={{ fontSize: "12px", color: "var(--muted)", fontWeight: 500 }}>
                  <strong style={{ color: "var(--ink)", fontWeight: 700 }}>{product.sales}</strong> sold
                </span>
              </>
            )}
          </div>
          <div className="detail-price" style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <strong>{money(effectiveSalePrice)}</strong>
            {product.discount > 0 && (
              <>
                <del>{money(effectiveOriginalPrice)}</del>
                <span>
                  You save{" "}
                  {money(Number(effectiveOriginalPrice) - Number(effectiveSalePrice))}
                </span>
              </>
            )}
            {product.flash_sale_end && (
              <FlashCountdown end={product.flash_sale_end} />
            )}
          </div>
          <p className="description">{product.description}</p>

          {product.variants && product.variants.length > 0 && (
            <div className="product-variants" style={{ margin: "16px 0" }}>
              <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--ink)", display: "block", marginBottom: "8px" }}>
                Option: <strong style={{ color: "var(--green)" }}>{activeVariant?.name || "Select"}</strong>
              </span>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                {product.variants.map((variant, idx) => {
                  const isSelected = selectedVariantIdx === idx;
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setSelectedVariantIdx(idx)}
                      style={{
                        padding: "6px 14px",
                        borderRadius: "8px",
                        border: isSelected ? "2px solid var(--green)" : "1px solid var(--line)",
                        background: isSelected ? "#f0fdf4" : "#fff",
                        color: isSelected ? "var(--green)" : "var(--ink)",
                        fontWeight: isSelected ? 600 : 500,
                        fontSize: "13px",
                        cursor: "pointer",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                        transition: "all 0.15s ease",
                      }}
                    >
                      <span>{variant.name}</span>
                      {variant.price_delta && (
                        <span style={{ fontSize: "11px", opacity: 0.85 }}>
                          ({variant.price_delta.startsWith("+") || variant.price_delta.startsWith("-") ? variant.price_delta : `+$${variant.price_delta}`})
                        </span>
                      )}
                      {typeof variant.available === "number" && variant.available <= 0 && (
                        <span style={{ fontSize: "11px", color: "var(--muted)" }}>(Sold out)</span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className={`stock ${effectiveStock ? "" : "sold-out"}`}>
            <span />
            {effectiveStock > 5
              ? "In stock. Ready for your everyday."
              : effectiveStock
                ? `Only ${effectiveStock} left in stock`
                : "Currently out of stock"}
          </div>
          <label className="field">
            <span>Quantity</span>
            <Quantity
              value={quantity}
              max={effectiveStock}
              onChange={setQuantity}
            />
          </label>
          <div className="purchase-actions">
            <button
              className="button"
              disabled={busy || !effectiveStock || product.is_own_store}
              onClick={async () => {
                setBusy(true);
                try {
                  await add({
                    ...product,
                    title: activeVariant ? `${product.title} (${activeVariant.name})` : product.title,
                    sale_price: effectiveSalePrice,
                    price: effectiveOriginalPrice,
                  }, quantity);
                } catch (error) {
                  notify((error as Error).message, true);
                } finally {
                  setBusy(false);
                }
              }}
            >
              {product.is_own_store
                ? "Your listing"
                : busy
                  ? "Adding…"
                  : "Add to bag"}
              <ArrowRight size={18} />
            </button>
            <button
              className={`button secondary ${liked ? "saved" : ""}`}
              aria-label="Save product"
              onClick={() =>
                toggleSave(product).catch((error) =>
                  notify(error.message, true),
                )
              }
            >
              <Heart size={20} fill={liked ? "currentColor" : "none"} />
            </button>
          </div>
          <div className="delivery-note">
            <Truck size={21} />
            <div>
              {product.is_digital ? (
                <>
                  <strong>Worldwide digital download</strong>
                  <p>
                    Your download link appears in your order after checkout. No
                    shipping fee.
                  </p>
                </>
              ) : (
                <>
                  <strong>US delivery only</strong>
                  <p>
                    Physical products are currently delivered only within the
                    United States.
                  </p>
                </>
              )}
            </div>
          </div>
          <div className="delivery-note">
            <ShieldCheck size={21} />
            <div>
              <strong>Secure payment</strong>
              <p>
                PayPal, Cash App, cards and Stripe are supported where
                available.
              </p>
            </div>
          </div>
          <Link
            className="seller-link"
            href={`/shop?store=${product.store}`}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "12px 16px",
              background: "#f8fafc",
              border: "1px solid var(--line)",
              borderRadius: "10px",
              textDecoration: "none",
              color: "inherit",
              marginTop: "16px"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "50%",
                  background: product.is_official_store ? "#fef3c7" : "#edf2ea",
                  display: "grid",
                  placeItems: "center",
                  color: product.is_official_store ? "#b45309" : "var(--green)",
                  flexShrink: 0
                }}
              >
                <StoreIcon size={18} />
              </div>
              <div>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: "13px" }}>
                  Sold by <strong style={{ color: "var(--ink)" }}>{product.store_name}</strong>
                  <VerifiedBadge
                    tier={product.is_official_store ? "official" : "starter"}
                    tierData={product.seller_tier}
                    size={16}
                  />
                </span>
                <p className="muted" style={{ fontSize: "11px", margin: 0 }}>
                  @{product.store_username || "store"} · Visit store & all listings
                </p>
              </div>
            </div>
            <ArrowUpRight size={18} className="muted" />
          </Link>
        </div>
      </div>
      <section className="product-tabs">
        <div className="tabs" role="tablist">
          {[
            ["details", "Product details"],
            ["reviews", `Reviews (${reviews.data?.length || 0})`],
            ["delivery", "Delivery & returns"],
          ].map(([key, text]) => (
            <button
              role="tab"
              aria-selected={tab === key}
              key={key}
              className={tab === key ? "active" : ""}
              onClick={() => setTab(key)}
            >
              {text}
            </button>
          ))}
        </div>
        <div className="tab-content" role="tabpanel">
          {tab === "details" ? (
            <>
              <h2>Made for your everyday</h2>
              <p>{product.description}</p>
              <dl className="spec-list">
                <div>
                  <dt>Brand</dt>
                  <dd>{product.brand || "Independent seller"}</dd>
                </div>
                <div>
                  <dt>Category</dt>
                  <dd>
                    {categories.find(
                      (category) => category.key === product.category,
                    )?.name || product.category}
                  </dd>
                </div>
                <div>
                  <dt>Sold by</dt>
                  <dd style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                    {product.store_name}
                    <VerifiedBadge
                      tier={product.is_official_store ? "official" : "starter"}
                      tierData={product.seller_tier}
                      size={14}
                    />
                  </dd>
                </div>
              </dl>
            </>
          ) : tab === "delivery" ? (
            <>
              <h2>A good find, delivered.</h2>
              <p>
                Digital products are generally delivered immediately without a
                shipping fee. Physical-product cost and timing depend on the
                provider, destination, weight and package size. Confirm
                availability and return eligibility before ordering.
              </p>
              <Link className="text-link" href="/help">
                Delivery & support <ArrowRight size={16} />
              </Link>
            </>
          ) : (
            <div className="review-layout">
              <div>
                <h2>From the community</h2>
                {reviews.isLoading ? (
                  <Loading />
                ) : reviews.error ? (
                  <ErrorState error={reviews.error} />
                ) : reviews.data?.length ? (
                  reviews.data.map((item) => (
                    <article className="review" key={item.id}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                        <span className="review-stars">
                          {"★".repeat(item.rating)}
                          {"☆".repeat(5 - item.rating)}
                        </span>
                        {item.is_verified_buyer && (
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                              fontSize: "11px",
                              fontWeight: 600,
                              color: "#059669",
                              background: "#ecfdf5",
                              padding: "2px 8px",
                              borderRadius: "12px",
                              border: "1px solid #a7f3d0"
                            }}
                          >
                            <Check size={12} strokeWidth={2.5} /> Verified Buyer
                          </span>
                        )}
                      </div>
                      <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        {item.label}
                        {item.is_own_review && (
                          <span style={{ fontSize: "11px", fontWeight: 500, color: "var(--muted)" }}>
                            (Your Review · Editable below)
                          </span>
                        )}
                      </h3>
                      <p style={{ whiteSpace: "pre-wrap" }}>{item.comment}</p>
                      {item.images && item.images.length > 0 && (
                        <div style={{ display: "flex", gap: "8px", margin: "10px 0", flexWrap: "wrap" }}>
                          {item.images.map((imgUrl, idx) => (
                            <a
                              key={idx}
                              href={imgUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              title="Click to view full photo"
                              style={{
                                width: "70px",
                                height: "70px",
                                borderRadius: "8px",
                                overflow: "hidden",
                                border: "1px solid var(--line)",
                                display: "block",
                                background: "#f8fafc"
                              }}
                            >
                              <img
                                src={imgUrl}
                                alt={`Customer review photo ${idx + 1}`}
                                style={{ width: "100%", height: "100%", objectFit: "cover" }}
                              />
                            </a>
                          ))}
                        </div>
                      )}
                      <small>
                        {item.author || "ProAce customer"} ·{" "}
                        {new Date(item.created).toLocaleDateString()}
                      </small>
                    </article>
                  ))
                ) : (
                  <p>No reviews yet. Be the first verified buyer to share your experience.</p>
                )}
              </div>
              {user ? (
                (() => {
                  const myReview = reviews.data?.find((r) => r.is_own_review);
                  return (
                    <form className="review-form" key={myReview?.id || "new-review"} onSubmit={review}>
                      <h3>{myReview ? "Edit your review" : "Write a review"}</h3>
                      <p className="muted" style={{ fontSize: "12px", margin: "-6px 0 12px" }}>
                        Only verified buyers who purchased this item can leave a review. Submitting again updates your existing comment.
                      </p>
                      <Field label="Rating">
                        <select name="rating" defaultValue={myReview ? String(myReview.rating) : "5"}>
                          {[5, 4, 3, 2, 1].map((value) => (
                            <option key={value} value={value}>
                              {value} {value === 1 ? "star" : "stars"}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Review title">
                        <input
                          name="label"
                          required
                          maxLength={120}
                          defaultValue={myReview?.label || ""}
                          placeholder="Headline or summary of your experience"
                        />
                      </Field>
                      <Field label="Your experience & feedback">
                        <textarea
                          name="comment"
                          required
                          maxLength={1000}
                          defaultValue={myReview?.comment || ""}
                          placeholder="Tell future buyers about the quality, delivery, fit, or any complaints…"
                          rows={4}
                        />
                      </Field>
                      <Field label="Photo attachments (Up to 3 image URLs, optional)">
                        <input
                          name="images"
                          defaultValue={myReview?.images?.join(", ") || ""}
                          placeholder="https://example.com/photo1.jpg, https://example.com/photo2.jpg"
                        />
                      </Field>
                      <button className="button" disabled={reviewBusy}>
                        {reviewBusy ? "Saving…" : myReview ? "Update review" : "Submit review"}
                      </button>
                    </form>
                  );
                })()
              ) : (
                <Link
                  className="button secondary"
                  href={`/login?next=/products/${id}`}
                >
                  Sign in to review
                </Link>
              )}
            </div>
          )}
        </div>
      </section>
      <section className="section">
        <div className="section-heading">
          <h2>A few more good finds</h2>
          <Link
            className="text-link"
            href={`/shop?category=${product.category}`}
          >
            Explore more <ArrowRight size={16} />
          </Link>
        </div>
        <ProductGrid
          products={
            related.data?.results
              .filter((item) => item.id !== product.id)
              .slice(0, 4) || []
          }
        />
      </section>
    </div>
  );
}

export function SavedPage() {
  const { saved } = useShop();
  return (
    <div className="container section">
      <div className="section-heading">
        <div>
          <span className="eyebrow green">KEEP THE GOOD FINDS CLOSE</span>
          <h1>Saved for later</h1>
        </div>
        <span className="muted">{saved.length} favourites</span>
      </div>
      {saved.length ? (
        <ProductGrid products={saved} />
      ) : (
        <Empty
          title="Your favourites live here"
          text="Tap the heart on something you love. We'll keep it here for you."
          icon={<Heart size={38} />}
        />
      )}
    </div>
  );
}
