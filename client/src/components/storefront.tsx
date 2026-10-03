"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  Heart,
  Headphones,
  Laptop,
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
import type { Page, Product } from "@/lib/types";
import {
  Empty,
  ErrorState,
  Field,
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
  const firstProduct = products.data?.results?.[0];
  const storeName = firstProduct?.store_name || (storeId ? `Store #${storeId}` : null);
  const isOfficialStore = Boolean(firstProduct?.is_official_store);

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

      <div className="shop-heading" style={storeName ? { paddingBottom: "24px" } : undefined}>
        <div>
          <span className="eyebrow green">
            {storeName ? (isOfficialStore ? "OFFICIAL PARTNER STORE" : "FEATURED MERCHANT") : "THE PROACE COLLECTION"}
          </span>
          <h1 style={{ display: "inline-flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            {title}
            {storeName && isOfficialStore && <VerifiedBadge size={24} />}
          </h1>
          <p>
            {storeName
              ? isOfficialStore
                ? "Official brand catalog. Authenticity guaranteed with direct marketplace fulfillment."
                : `Browse the curated catalog and collections from ${storeName}.`
              : "Considered essentials. Unexpected favourites."}
          </p>
        </div>
        <span className="result-total">
          {products.data?.count ?? "…"} products
        </span>
      </div>

      {storeName && (
        <div style={{ display: "flex", gap: "8px", overflowX: "auto", padding: "14px 0", borderBottom: "1px solid var(--line)", marginBottom: "10px" }}>
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

type Review = {
  id: number;
  author: string;
  rating: number;
  label: string;
  comment: string;
  created: string;
};

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
  if (productQuery.isLoading) return <Loading />;
  if (productQuery.error)
    return (
      <ErrorState
        error={productQuery.error}
        retry={() => productQuery.refetch()}
      />
    );
  const product = productQuery.data!;
  const liked = saved.some((row) => row.id === product.id);
  async function review(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    setReviewBusy(true);
    try {
      await api(`products/${id}/reviews`, "POST", data);
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
            {product.is_official_store && <VerifiedBadge size={14} />}
          </span>
          <h1>{product.title}</h1>
          <div className="rating-line">
            <Star size={16} fill="currentColor" />
            <strong>
              {Number(product.average_rating) > 0
                ? Number(product.average_rating).toFixed(1)
                : "New arrival"}
            </strong>
            <button className="text-button" onClick={() => setTab("reviews")}>
              {reviews.data?.length || 0} reviews
            </button>
          </div>
          <div className="detail-price">
            <strong>{money(product.sale_price)}</strong>
            {product.discount > 0 && (
              <>
                <del>{money(product.price)}</del>
                <span>
                  You save{" "}
                  {money(Number(product.price) - Number(product.sale_price))}
                </span>
              </>
            )}
          </div>
          <p className="description">{product.description}</p>
          <div className={`stock ${product.available ? "" : "sold-out"}`}>
            <span />
            {product.available > 5
              ? "In stock. Ready for your everyday."
              : product.available
                ? `Only ${product.available} left in stock`
                : "Currently out of stock"}
          </div>
          <label className="field">
            <span>Quantity</span>
            <Quantity
              value={quantity}
              max={product.available}
              onChange={setQuantity}
            />
          </label>
          <div className="purchase-actions">
            <button
              className="button"
              disabled={busy || !product.available || product.is_own_store}
              onClick={async () => {
                setBusy(true);
                try {
                  await add(product, quantity);
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
          <Link className="seller-link" href={`/shop?store=${product.store}`}>
            <StoreIcon size={19} />
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              Sold by <strong>{product.store_name}</strong>
              {product.is_official_store && <VerifiedBadge size={15} />}
            </span>
            <ArrowUpRight size={16} />
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
                    {product.is_official_store && <VerifiedBadge size={14} />}
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
                      <span className="review-stars">
                        {"★".repeat(item.rating)}
                        {"☆".repeat(5 - item.rating)}
                      </span>
                      <h3>{item.label}</h3>
                      <p>{item.comment}</p>
                      <small>
                        {item.author || "ProAce customer"} ·{" "}
                        {new Date(item.created).toLocaleDateString()}
                      </small>
                    </article>
                  ))
                ) : (
                  <p>No reviews yet. Be the first to share your experience.</p>
                )}
              </div>
              {user ? (
                <form className="review-form" onSubmit={review}>
                  <h3>Write a review</h3>
                  <Field label="Rating">
                    <select name="rating" defaultValue="5">
                      {[5, 4, 3, 2, 1].map((value) => (
                        <option key={value} value={value}>
                          {value} stars
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Review title">
                    <input name="label" required maxLength={80} />
                  </Field>
                  <Field label="Your experience">
                    <textarea
                      name="comment"
                      required
                      maxLength={60}
                      placeholder="Up to 60 characters"
                    />
                  </Field>
                  <button className="button" disabled={reviewBusy}>
                    {reviewBusy ? "Saving…" : "Submit review"}
                  </button>
                </form>
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
