"use client";
import { isMilitaryAddress } from "@/lib/geo";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronRight,
  LockKeyhole,
  MapPin,
  Pencil,
  Plus,
  ShoppingBag,
  Trash2,
  Truck,
  WalletCards,
  X,
} from "lucide-react";
import { api, money } from "@/lib/api";
import type { Address, Order, Product, UserWallet } from "@/lib/types";
import { useShop } from "./providers";
import { AddressForm, Gate } from "./account";
import { Empty, ErrorState, Loading, ProductImage, Quantity } from "./ui";

export function CartPage() {
  const { cart, cartLoading, cartError, setQuantity, notify } = useShop();
  const hasPhysicalItems = cart.items.some((item) => !item.product.is_digital);
  const [busy, setBusy] = useState<number | null>(null);
  async function update(product: Product, quantity: number) {
    setBusy(product.id);
    try {
      await setQuantity(product, quantity);
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setBusy(null);
    }
  }
  return (
    <div className="container cart-page">
      <div className="breadcrumb">
        <Link href="/">Home</Link>
        <ChevronRight size={12} />
        <span>Your bag</span>
      </div>
      <div className="section-heading">
        <div>
          <span className="eyebrow green">YOUR GOOD FINDS</span>
          <h1>
            In the bag<span className="heading-count">{cart.items.length}</span>
          </h1>
        </div>
        <Link className="text-link" href="/shop">
          <ArrowLeft size={16} />
          Keep discovering
        </Link>
      </div>
      {cartLoading ? (
        <Loading />
      ) : cartError ? (
        <ErrorState error={cartError} />
      ) : !cart.items.length ? (
        <Empty
          title="Room for something good"
          text="Your bag is waiting for its first find. Let's change that."
        />
      ) : (
        <div className="checkout-layout">
          <section className="cart-items">
            <div className="shipping-banner">
              <Truck size={21} />
              <div>
                <strong>Physical delivery is currently US-only.</strong>
                <span>
                  Digital downloads are available worldwide and have no shipping
                  fee.
                </span>
              </div>
            </div>
            <div className="cart-table-head">
              <span>Product</span>
              <span>Quantity</span>
              <span>Total</span>
            </div>
            {cart.items.map((row) => (
              <article className="cart-row" key={`${row.product.id}:${row.product.selected_variant || ''}`}>
                <Link
                  className="cart-image"
                  href={`/products/${row.product.id}`}
                >
                  <ProductImage
                    src={row.product.image}
                    alt={row.product.title}
                  />
                </Link>
                <div className="cart-product-info">
                  <small>{row.product.brand}</small>
                  <Link href={`/products/${row.product.id}`}>
                    {row.product.title}
                  </Link>
                  <p>{money(row.product.sale_price)}</p>
                  {!row.purchasable && (
                    <span className="form-error">
                      {row.product.is_own_store
                        ? "You cannot buy from your own store. Remove this item."
                        : "This listing is currently unavailable."}
                    </span>
                  )}
                  <button
                    className="text-button"
                    disabled={busy === row.product.id}
                    onClick={() => update(row.product, 0)}
                  >
                    <Trash2 size={13} />
                    Remove
                  </button>
                </div>
                {row.product.is_digital ? (
                  <div
                    className="quantity quantity-digital"
                    title="Digital entitlement — limited to 1 per customer"
                    aria-label="Digital entitlement quantity: 1"
                  >
                    <span className="quantity-digital-val">1</span>
                    <span className="quantity-digital-badge">Digital</span>
                  </div>
                ) : (
                  <Quantity
                    value={row.quantity}
                    max={row.product.available}
                    disabled={busy === row.product.id}
                    onChange={(value) => update(row.product, value)}
                  />
                )}
                <strong>
                  {money(Number(row.product.sale_price) * row.quantity)}
                </strong>
              </article>
            ))}
          </section>
          <aside className="order-summary">
            <h2>A good little haul.</h2>
            <div className="summary-line">
              <span>Subtotal</span>
              <strong>{money(cart.subtotal)}</strong>
            </div>
            <div className="summary-line">
              <span>Delivery</span>
              <strong>
                {cart.shipping === null
                  ? "Calculated at checkout"
                  : Number(cart.shipping)
                  ? money(cart.shipping)
                  : "Free"}
              </strong>
            </div>
            <div className="summary-total">
              <span>{hasPhysicalItems ? "Items total" : "Total"}</span>
              <strong>{money(cart.total)}</strong>
            </div>
            <Link className="button" href="/checkout">
              Continue to checkout <ArrowRight size={17} />
            </Link>
            <span className="secure-note">
              <LockKeyhole size={14} />
              Secure checkout
            </span>
          </aside>
        </div>
      )}
    </div>
  );
}

export type CarrierCode = "UPS" | "FEDEX" | "DHL" | "USPS";

export type ShippingTierCategory = "fastest" | "best_value" | "economical" | "standard";

export interface ShippingTierInfo {
  title: string;
  estimate: string;
  badge: {
    label: string;
    variant: ShippingTierCategory;
  };
}

export const CARRIER_OPTIONS: {
  id: CarrierCode;
  name: string;
  subtitle: string;
  brandClass: string;
  logo: React.ReactNode;
}[] = [
  {
    id: "UPS",
    name: "UPS",
    subtitle: "United Parcel Service",
    brandClass: "carrier-ups",
    logo: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 2L3 5.5V11.5C3 17 6.8 21.8 12 23C17.2 21.8 21 17 21 11.5V5.5L12 2Z" fill="#351c15" stroke="#ffb500" strokeWidth="1.5"/>
        <path d="M8 8V13C8 15 9.5 16 12 16C14.5 16 16 15 16 13V8" stroke="#ffb500" strokeWidth="1.8" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: "FEDEX",
    name: "FedEx",
    subtitle: "Federal Express",
    brandClass: "carrier-fedex",
    logo: (
      <svg width="24" height="20" viewBox="0 0 28 20" fill="none" aria-hidden="true">
        <rect width="28" height="20" rx="4" fill="#4d148c"/>
        <text x="3" y="14" fill="#ffffff" fontFamily="system-ui, sans-serif" fontWeight="900" fontSize="11" letterSpacing="-0.5">Fed</text>
        <text x="17" y="14" fill="#ff6600" fontFamily="system-ui, sans-serif" fontWeight="900" fontSize="11" letterSpacing="-0.5">Ex</text>
      </svg>
    ),
  },
  {
    id: "DHL",
    name: "DHL",
    subtitle: "Express & Logistics",
    brandClass: "carrier-dhl",
    logo: (
      <svg width="24" height="20" viewBox="0 0 28 20" fill="none" aria-hidden="true">
        <rect width="28" height="20" rx="4" fill="#ffcc00"/>
        <path d="M4 14L8 6H12L8 14H4Z" fill="#d40511"/>
        <path d="M13 14L15 6H18L16 14H13Z" fill="#d40511"/>
        <path d="M19 14L21 6H24L22 14H19Z" fill="#d40511"/>
      </svg>
    ),
  },
  {
    id: "USPS",
    name: "USPS",
    subtitle: "Postal Service",
    brandClass: "carrier-usps",
    logo: (
      <svg width="22" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <rect width="24" height="24" rx="4" fill="#004b87"/>
        <path d="M5 16L12 6L19 16H5Z" fill="#ffffff"/>
        <path d="M8 16L12 10L16 16H8Z" fill="#da291c"/>
      </svg>
    ),
  },
];

export function getShippingTierInfo(
  rate: import("@/lib/types").ShippingRate,
  carrierCode: string
): ShippingTierInfo {
  const code = (rate.service_id || "").toLowerCase();
  const name = (rate.name || "").toLowerCase();
  const desc = (rate.description || "").trim();

  // UPS
  if (carrierCode === "UPS" || code.startsWith("ups_")) {
    if (code.includes("01") || code.includes("next_day") || name.includes("next day")) {
      return {
        title: "UPS Next Day Air",
        estimate: "Next business day by 10:30 AM / 12:00 PM",
        badge: { label: "Fastest", variant: "fastest" },
      };
    }
    if (code.includes("02") || code.includes("2nd_day") || name.includes("2nd day")) {
      return {
        title: "UPS 2nd Day Air",
        estimate: "Est. 2 business days",
        badge: { label: "Standard Expedited", variant: "standard" },
      };
    }
    return {
      title: "UPS Ground",
      estimate: "Est. 3–5 business days",
      badge: { label: "Economical Baseline", variant: "economical" },
    };
  }

  // DHL
  if (carrierCode === "DHL" || code.startsWith("dhl_")) {
    if (code.includes("1200") || code.includes("12:00") || name.includes("12:00") || code === "dhl_t") {
      return {
        title: "DHL Express 12:00",
        estimate: "Next business day by 12:00 PM",
        badge: { label: "Guaranteed Time-Definite", variant: "standard" },
      };
    }
    if (
      code.includes("worldwide") ||
      code.includes("express") ||
      code === "dhl_d" ||
      code === "dhl_p" ||
      code === "dhl_n" ||
      name.includes("worldwide")
    ) {
      return {
        title: "DHL Express Worldwide",
        estimate: "Est. 1–3 business days",
        badge: { label: "Fastest", variant: "fastest" },
      };
    }
    return {
      title: "DHL Economy Select",
      estimate: "Est. 2–5 business days",
      badge: { label: "Economical", variant: "economical" },
    };
  }

  // FedEx
  if (carrierCode === "FEDEX" || code.startsWith("fedex_")) {
    if (code.includes("overnight") || code.includes("priority") || name.includes("overnight") || name.includes("priority")) {
      return {
        title: "FedEx Priority Overnight",
        estimate: "Next business day morning delivery",
        badge: { label: "Fastest", variant: "fastest" },
      };
    }
    if (code.includes("2_day") || code.includes("2day") || name.includes("2day") || name.includes("2 day")) {
      return {
        title: "FedEx 2Day",
        estimate: "Est. 2 business days",
        badge: { label: "Standard Air", variant: "standard" },
      };
    }
    return {
      title: "FedEx Ground",
      estimate: "Est. 1–5 business days",
      badge: { label: "Economical", variant: "economical" },
    };
  }

  // USPS
  if (code.includes("priority_express") || name.includes("express")) {
    return {
      title: "USPS Priority Mail Express",
      estimate: "Overnight to 2-day guaranteed",
      badge: { label: "Fastest", variant: "fastest" },
    };
  }
  if (code.includes("priority_mail") || (name.includes("priority") && !name.includes("express"))) {
    return {
      title: "USPS Priority Mail",
      estimate: "Est. 1–3 business days",
      badge: { label: "Standard", variant: "standard" },
    };
  }
  return {
    title: "USPS Ground Advantage",
    estimate: "Est. 2–5 business days",
    badge: { label: "Best Value", variant: "best_value" },
  };
}

export function CheckoutPage() {
  const { user, cart, cartLoading, cartError, notify } = useShop();
  const router = useRouter();
  const client = useQueryClient();
  const search = useSearchParams();
  const addressParam = search.get("address_id");
  const addresses = useQuery({
    queryKey: ["addresses", user?.id],
    queryFn: () => api<Address[]>("addresses"),
    enabled: !!user,
  });
  const [selected, setSelected] = useState<number | null>(
    addressParam ? Number(addressParam) : null
  );
  const [editingAddress, setEditingAddress] = useState<Address | null>(null);
  const [showAddressModal, setShowAddressModal] = useState(false);
  const [modalAdding, setModalAdding] = useState(false);
  const [modalEditing, setModalEditing] = useState<Address | null>(null);

  useEffect(() => {
    if (addressParam) {
      const id = Number(addressParam);
      if (!isNaN(id)) setSelected(id);
    }
  }, [addressParam]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && showAddressModal) {
        setShowAddressModal(false);
        setModalAdding(false);
        setModalEditing(null);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showAddressModal]);

  useEffect(() => {
    if (showAddressModal) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [showAddressModal]);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [couponCode, setCouponCode] = useState("");
  const [appliedCoupon, setAppliedCoupon] = useState<{ code: string; discount: number; message: string } | null>(null);
  const [validatingCoupon, setValidatingCoupon] = useState(false);
  const [useWalletSplit, setUseWalletSplit] = useState(false);
  const [carrier, setCarrier] = useState<CarrierCode>("USPS");
  const [shippingService, setShippingService] = useState<string>(
    "usps_ground_advantage",
  );
  const [paymentType, setPaymentType] =
    useState<"stripe_wallet" | "user_wallet">("stripe_wallet");
  const wallet = useQuery({
    queryKey: ["wallet", user?.id],
    queryFn: () => api<UserWallet>("wallet"),
    enabled: !!user,
  });
  const [checkoutKey] = useState(() =>
    typeof crypto !== "undefined" ? crypto.randomUUID() : "",
  );
  const defaultAddress =
    addresses.data?.find((address) => address.is_default) ||
    addresses.data?.[0];
  const currentAddress =
    addresses.data?.find((address) => address.id === selected) ||
    defaultAddress;
  const addressId = currentAddress?.id;
  const hasPhysical = cart.items.some((item) => !item.product.is_digital);
  const militaryDelivery = hasPhysical && isMilitaryAddress(currentAddress);
  useEffect(() => {
    if (militaryDelivery) {
      setCarrier('USPS');
      setShippingService('usps_ground_advantage');
    }
  }, [militaryDelivery]);

  const shippingRates = useQuery({
    queryKey: [
      'shipping-rates',
      appliedCoupon?.code || '',
      hasPhysical ? addressId : 'digital',
      carrier,
      cart.items
        .map((row) => `${row.product.id}:${row.product.selected_variant || ''}:${row.quantity}`)
        .join(','),
    ],
    queryFn: (): Promise<import('@/lib/types').ShippingRate[]> => {
      const query: URLSearchParams = new URLSearchParams();
      if (hasPhysical && addressId) {
        query.set('address', String(addressId));
        query.set('carrier', carrier);
      }
      if (appliedCoupon?.code) {
        query.set('coupon', appliedCoupon.code);
      }
      return api<import('@/lib/types').ShippingRate[]>(
        `checkout/shipping-rates?${query.toString()}`,
      );
    },
    enabled: hasPhysical ? !!addressId && (!militaryDelivery || carrier === 'USPS') : cart.items.length > 0,
  });

  const carrierRates = useMemo(() => {
    if (!shippingRates.data) return [];
    if (!hasPhysical) return shippingRates.data;
    return shippingRates.data.filter((rate) => {
      const rateCarrier = (rate.carrier || "").toUpperCase();
      const serviceId = (rate.service_id || "").toLowerCase();
      const rateName = (rate.name || "").toLowerCase();

      // Ensure rate carrier matches selected carrier
      if (rateCarrier && rateCarrier !== carrier) return false;

      // Ensure service_id matches selected carrier prefix
      if (serviceId.includes("_")) {
        const prefix = serviceId.split("_")[0].toUpperCase();
        if (prefix !== carrier) return false;
      }

      // Hard guard: never allow cross-carrier contamination (e.g. USPS under DHL)
      if (carrier === "DHL" && (serviceId.startsWith("usps") || rateName.includes("usps"))) {
        return false;
      }
      if (carrier === "USPS" && (serviceId.startsWith("dhl") || rateName.includes("dhl"))) {
        return false;
      }
      if (carrier === "UPS" && !serviceId.startsWith("ups")) {
        return false;
      }
      if (carrier === "FEDEX" && !serviceId.startsWith("fedex")) {
        return false;
      }

      return true;
    });
  }, [shippingRates.data, carrier, hasPhysical]);

  const activeShipping = shippingRates.isFetching ? undefined :
    carrierRates.find((rate) => rate.service_id === shippingService) ||
    carrierRates[0];

  useEffect(() => {
    if (carrierRates.length > 0) {
      const match = carrierRates.find(r => r.service_id === shippingService);
      if (!match) {
        const defaultTier = carrierRates.find(r => r.is_default) || carrierRates[0];
        setShippingService(defaultTier.service_id);
      }
    }
  }, [carrierRates, shippingService]);

  function handleCarrierChange(nextCarrier: CarrierCode) {
    if (nextCarrier === carrier) return;
    setCarrier(nextCarrier);
    setShippingService("");
  }

  async function handleApplyCoupon() {
    if (!couponCode.trim()) return;
    setValidatingCoupon(true);
    setError("");
    try {
      const res = await api<{ code: string; discount_amount: string; message: string }>(
        "checkout/validate-coupon",
        "POST",
        { code: couponCode.trim() }
      );
      setAppliedCoupon({
        code: res.code,
        discount: Number(res.discount_amount),
        message: res.message,
      });
      notify(res.message);
    } catch (err) {
      setError((err as Error).message);
      setAppliedCoupon(null);
    } finally {
      setValidatingCoupon(false);
    }
  }

  function handleRemoveCoupon() {
    setAppliedCoupon(null);
    setCouponCode("");
  }

  const shippingFee = activeShipping
    ? Number(activeShipping.amount)
    : 0;
  const taxAmount = Number(activeShipping?.tax || 0);
  const couponDiscount = appliedCoupon?.discount || 0;
  const grossTotal = Math.max(0, Number(cart.subtotal) - couponDiscount + shippingFee + taxAmount);

  const walletBalance = Number(wallet.data?.balance || 0);
  const canUseWalletSplit = walletBalance > 0 && paymentType === "stripe_wallet" && grossTotal > 0.50;
  const walletDeduction = (useWalletSplit && canUseWalletSplit)
    ? Math.min(walletBalance, Math.max(0, grossTotal - 0.50))
    : 0;
  const chargeAmount = grossTotal - walletDeduction;

  useEffect(() => {
    const sessionId = search.get("wallet_session_id");
    if (!sessionId || !user) return;
    setBusy(true);
    api<Order>("checkout/wallet-confirm", "POST", { session_id: sessionId })
      .then((order) => router.replace(`/orders/${order.id}?placed=true`))
      .catch((error) => setError((error as Error).message))
      .finally(() => setBusy(false));
  }, [router, search, user]);

  useEffect(() => {
    if (search.get("wallet_cancelled") === "1" && user) {
      const checkoutKey = search.get("checkout_key");
      if (!checkoutKey) {
        setError("The checkout reference is missing. Your wallet reservation will remain held until payment status is verified.");
        return;
      }
      void api<{
        detail: string;
        released: boolean;
        completed?: boolean;
        session_id?: string;
      }>("checkout/wallet-cancel", "POST", { checkout_key: checkoutKey })
        .then(async (result) => {
          if (result.completed && result.session_id) {
            const order = await api<Order>("checkout/wallet-confirm", "POST", {
              session_id: result.session_id,
            });
            router.replace(`/orders/${order.id}?placed=true`);
            return;
          }
          if (result.released) {
            notify("Checkout cancelled. Reserved store credit returned to your wallet.");
          } else {
            notify(result.detail, true);
          }
          router.replace("/checkout");
        })
        .catch((reason: unknown) => {
          notify(reason instanceof Error ? reason.message : "Unable to verify checkout cancellation.", true);
          router.replace("/checkout");
        });
    }
  }, [router, search, user, notify]);

  async function placeOrder() {
    if (hasPhysical && !addressId) {
      setError("Choose a delivery address first.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (hasPhysical && (!activeShipping?.quote_token || shippingRates.isFetching)) {
        throw new Error("Choose an available shipping service before paying.");
      }
      const selectedService = hasPhysical ? (activeShipping?.service_id || "usps_ground_advantage") : "digital_delivery";
      const effectiveCoupon = appliedCoupon?.code || couponCode.trim();
      if (paymentType === "user_wallet") {
        const order = await api<Order>("checkout", "POST", {
          ...(hasPhysical && addressId ? { address: addressId } : {}),
          checkout_key: checkoutKey,
          coupon: effectiveCoupon,
          payment_type: "user_wallet",
          shipping_service: selectedService,
          ...(hasPhysical && activeShipping?.quote_token ? { shipping_quote: activeShipping.quote_token } : {}),
        });
        await client.invalidateQueries({ queryKey: ["cart"] });
        await client.invalidateQueries({ queryKey: ["wallet"] });
        router.replace(`/orders/${order.id}?placed=true`);
        return;
      }
      const session = await api<{ url: string }>(
        "checkout/wallet-session",
        "POST",
        {
          ...(hasPhysical && addressId ? { address: addressId } : {}),
          checkout_key: checkoutKey,
          coupon: effectiveCoupon,
          shipping_service: selectedService,
          ...(hasPhysical && activeShipping?.quote_token ? { shipping_quote: activeShipping.quote_token } : {}),
          ...(walletDeduction > 0 ? { wallet_amount: walletDeduction } : {}),
        },
      );
      window.location.assign(session.url);
    } catch (error) {
      setError((error as Error).message);
      await client.invalidateQueries({ queryKey: ["cart"] });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Gate next="/checkout">
      <div className="container checkout-page">
        <Link className="text-link" href="/cart">
          <ArrowLeft size={16} />
          Back to your bag
        </Link>
        <div className="section-heading">
          <div>
            <span className="eyebrow green">ALMOST YOURS</span>
            <h1>The final little details.</h1>
          </div>
          <span className="secure-note">
            <LockKeyhole size={15} />
            Secure checkout
          </span>
        </div>
        {cartLoading ? (
          <Loading />
        ) : cartError ? (
          <ErrorState error={cartError} />
        ) : !cart.items.length ? (
          <Empty
            title="Your bag is empty"
            text="Find something you love before checking out."
          />
        ) : (
          <div className="checkout-layout">
            <section className="checkout-steps">
              {!hasPhysical ? (
                <div className="checkout-delivery-card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
                  <div className="checkout-delivery-card-header" style={{ marginBottom: '0.75rem' }}>
                    <div className="checkout-delivery-card-title">
                      <MapPin size={15} style={{ color: "var(--green)" }} />
                      <span className="delivery-card-label" style={{ fontWeight: 600 }}>Worldwide digital delivery</span>
                      <span className="status">Digital delivery</span>
                    </div>
                  </div>
                  <div className="checkout-delivery-card-body">
                    <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--foreground)' }}>
                      Your order contains digital products only. Instant global delivery is included with no physical shipping address or courier quote required.
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <div className="step-heading">
                    <span>1</span>
                    <h2>Where are we delivering?</h2>
                  </div>
                  {addresses.isLoading ? (
                    <Loading />
                  ) : addresses.error ? (
                    <ErrorState error={addresses.error} />
                  ) : editingAddress ? (
                    <AddressForm
                      initialData={editingAddress}
                      onSaved={(address) => {
                        setSelected(address.id);
                        setEditingAddress(null);
                        notify("Address updated successfully");
                      }}
                      onCancel={() => setEditingAddress(null)}
                    />
                  ) : currentAddress ? (
                    <div className="checkout-delivery-card">
                      <div className="checkout-delivery-card-header">
                        <div className="checkout-delivery-card-title">
                          <MapPin size={15} style={{ color: "var(--green)" }} />
                          <span className="delivery-card-label">Delivery Address</span>
                          {currentAddress.is_default && (
                            <span className="status">Default</span>
                          )}
                        </div>
                        <button
                          type="button"
                          className="address-pen-btn"
                          aria-label="Edit address"
                          title="Edit this address"
                          onClick={() => setEditingAddress(currentAddress)}
                        >
                          <Pencil size={15} />
                        </button>
                      </div>
                      <div className="checkout-delivery-card-body">
                        <strong className="delivery-street">{currentAddress.address}</strong>
                        <p className="delivery-location">
                          {currentAddress.city}, {currentAddress.state} {currentAddress.zip}
                        </p>
                        <span className="delivery-country">{currentAddress.country}</span>
                      </div>
                      <div className="checkout-delivery-card-footer">
                        <button
                          type="button"
                          className="change-address-btn"
                          onClick={() => setShowAddressModal(true)}
                        >
                          <span>Select another address</span>
                          <ArrowRight size={13} />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="checkout-empty-address">
                      <MapPin size={22} style={{ color: "var(--green)" }} />
                      <div>
                        <p>No delivery address found.</p>
                        <button
                          type="button"
                          className="button"
                          style={{ minHeight: "36px", padding: "8px 14px", fontSize: "11px" }}
                          onClick={() => {
                            setModalAdding(true);
                            setShowAddressModal(true);
                          }}
                        >
                          <Plus size={14} />
                          <span>Add delivery address</span>
                        </button>
                      </div>
                    </div>
                  )}
                  <div className="step-heading">
                    <span>2</span>
                    <h2>Choose shipping method</h2>
                  </div>
                  {militaryDelivery && <p role="status" className="muted">APO/FPO/DPO military addresses use USPS. Other carriers are unavailable for this destination.</p>}
                  <fieldset className="carrier-options">
                    <legend>Choose a courier</legend>
                    {CARRIER_OPTIONS.map((c) => (
                      <label
                        key={c.id}
                        className={`carrier-option ${carrier === c.id ? "selected" : ""}`}
                        title={militaryDelivery && c.id !== "USPS" ? "USPS is required for military postal addresses" : undefined}
                      >
                        <input
                          type="radio"
                          name="shipping-carrier"
                          value={c.id}
                          checked={carrier === c.id}
                          disabled={militaryDelivery && c.id !== "USPS"}
                          onChange={() => handleCarrierChange(c.id)}
                        />
                        <div className="carrier-badge-icon">{c.logo}</div>
                        <div className="carrier-info">
                          <span className={`carrier-brand ${c.brandClass}`} aria-label={`${c.name} carrier`}>
                            {c.name}
                          </span>
                          <small className="carrier-subtitle">{c.subtitle}</small>
                        </div>
                      </label>
                    ))}
                  </fieldset>
                  {shippingRates.isFetching ? (
                    <div className="shipping-skeleton" role="status" aria-label="Loading shipping plans">
                      <span /><span /><span />
                    </div>
                  ) : shippingRates.error ? (
                    <p className="form-error">
                      {shippingRates.error.message}
                    </p>
                  ) : (
                    <div className="shipping-tier-list" role="radiogroup" aria-label={`${carrier} shipping service options`}>
                      {carrierRates.map((rate) => {
                        const tier = getShippingTierInfo(rate, carrier);
                        const isSelected = activeShipping?.service_id === rate.service_id;
                        return (
                          <label
                            key={rate.service_id}
                            className={`shipping-tier-card ${isSelected ? "selected" : ""}`}
                          >
                            <input
                              type="radio"
                              name="shipping_service"
                              value={rate.service_id}
                              checked={isSelected}
                              onChange={() => setShippingService(rate.service_id)}
                            />
                            <div className="shipping-tier-content">
                              <div className="shipping-tier-header">
                                <span className="shipping-tier-title">{tier.title}</span>
                                <span className={`shipping-tier-badge badge-${tier.badge.variant}`}>
                                  {tier.badge.label}
                                </span>
                              </div>
                              <span className="shipping-tier-estimate">{tier.estimate}</span>
                            </div>
                            <div className="shipping-tier-price">
                              <strong>
                                {Number(rate.amount) === 0
                                  ? "Free"
                                  : money(rate.amount)}
                              </strong>
                            </div>
                          </label>
                        );
                      })}
                      {carrierRates.length === 0 && (
                        <p className="form-error">
                          No {carrier} shipping options are available for this destination.
                        </p>
                      )}
                    </div>
                  )}
                </>
              )}
              <div className="step-heading">
                <span>{hasPhysical ? '3' : '1'}</span>
                <h2>Upfront payment</h2>
              </div>
              <label
                className={`select-address ${paymentType === "stripe_wallet" ? "selected" : ""}`}
              >
                <input
                  type="radio"
                  name="payment"
                  checked={paymentType === "stripe_wallet"}
                  onChange={() => setPaymentType("stripe_wallet")}
                />
                <div>
                  <strong>Cards, Stripe & Digital Wallets</strong>
                  <p>
                    Pay securely on Stripe with Visa, Mastercard, Amex, Apple Pay, Google Pay, or Cash App.
                  </p>
                </div>
                <WalletCards size={22} />
              </label>
              {paymentType === "stripe_wallet" && (
                <div style={{ marginTop: "0.5rem", marginBottom: "0.75rem", padding: "0.75rem 1rem", background: "var(--soft)", borderRadius: "8px", border: "1px solid var(--line)", fontSize: "0.85rem", color: "var(--muted)", display: "flex", alignItems: "center", gap: "8px" }}>
                  <LockKeyhole size={16} style={{ color: "var(--green)", flexShrink: 0 }} />
                  <span>
                    You will be redirected to Stripe to complete your payment with your card, Apple Pay, Google Pay, or supported bank.
                  </span>
                </div>
              )}
              <label
                className={`select-address ${paymentType === "user_wallet" ? "selected" : ""}`}
              >
                <input
                  type="radio"
                  name="payment"
                  checked={paymentType === "user_wallet"}
                  onChange={() => setPaymentType("user_wallet")}
                />
                <div>
                  <strong>ProAce Wallet Balance ({money(wallet.data?.balance || "0.00")})</strong>
                  <p>
                    Pay instantly using your available store credit balance.
                  </p>
                </div>
                <WalletCards size={22} />
              </label>
              <div className="checkout-note">
                <Truck size={20} />
                <p>
                  {hasPhysical
                    ? "Compare delivery services from UPS, FedEx, DHL, and USPS."
                    : "Digital items are delivered instantly online with no delivery fee."}
                </p>
              </div>
            </section>
            <aside className="order-summary">
              <h2>Your order</h2>
              {cart.items.map((row) => (
                <div className="mini-item" key={`${row.product.id}:${row.product.selected_variant || ''}`}>
                  <ProductImage
                    src={row.product.image}
                    alt={row.product.title}
                  />
                  <div>
                    <strong>{row.product.title}</strong>
                    <span>Qty {row.quantity}</span>
                  </div>
                  <span>
                    {money(Number(row.product.sale_price) * row.quantity)}
                  </span>
                </div>
              ))}
              <div className="summary-line">
                <span>Subtotal</span>
                <strong>{money(cart.subtotal)}</strong>
              </div>
              {appliedCoupon && (
                <div className="summary-line" style={{ color: "var(--green)" }}>
                  <span>Coupon ({appliedCoupon.code})</span>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <strong>-{money(appliedCoupon.discount)}</strong>
                    <button
                      type="button"
                      className="icon-button"
                      aria-label="Remove coupon"
                      onClick={handleRemoveCoupon}
                      style={{ padding: "2px" }}
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>
              )}
              <div className="summary-line">
                <span>Delivery ({activeShipping?.name || carrier})</span>
                <strong>
                  {shippingFee === 0 ? "Free" : money(shippingFee)}
                </strong>
              </div>
              <div className="summary-line">
                <span>
                  Tax
                  {activeShipping?.tax_jurisdiction ? (
                    <small style={{ color: "var(--muted)", fontWeight: "normal", marginLeft: "4px" }}>
                      ({activeShipping.tax_jurisdiction})
                    </small>
                  ) : hasPhysical && !addressId ? (
                    <small style={{ color: "var(--muted)", fontWeight: "normal", marginLeft: "4px" }}>
                      (Calculated at checkout)
                    </small>
                  ) : null}
                </span>
                <strong>{money(taxAmount)}</strong>
              </div>
              <div className="coupon-box" style={{ margin: "0.75rem 0" }}>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <input
                    value={couponCode}
                    onChange={(event) => setCouponCode(event.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void handleApplyCoupon(); }}}
                    placeholder="Enter coupon code"
                    autoComplete="off"
                    style={{ flex: 1 }}
                  />
                  <button
                    type="button"
                    className="button secondary"
                    disabled={validatingCoupon || !couponCode.trim()}
                    onClick={handleApplyCoupon}
                    style={{ padding: "0 0.85rem", whiteSpace: "nowrap" }}
                  >
                    {validatingCoupon ? "Checking…" : "Apply"}
                  </button>
                </div>
                {appliedCoupon && (
                  <small style={{ color: "var(--green)", display: "block", marginTop: "4px" }}>
                    ✓ {appliedCoupon.message}
                  </small>
                )}
              </div>
              {canUseWalletSplit && (
                <div className="wallet-split-box" style={{ background: "var(--soft)", padding: "0.75rem", borderRadius: "6px", margin: "0.75rem 0" }}>
                  <label className="check-row" style={{ margin: 0, fontSize: "0.88rem" }}>
                    <input
                      type="checkbox"
                      checked={useWalletSplit}
                      onChange={(e) => setUseWalletSplit(e.target.checked)}
                    />
                    <span>
                      Apply <strong>{money(Math.min(walletBalance, grossTotal - 0.50))}</strong> from ProAce Wallet ({money(walletBalance)} available)
                    </span>
                  </label>
                  {walletDeduction > 0 && (
                    <div style={{ marginTop: "0.5rem", fontSize: "0.82rem", color: "var(--muted)" }}>
                      <div>Wallet deduction: -{money(walletDeduction)}</div>
                      <div>Card payment: <strong>{money(chargeAmount)}</strong></div>
                    </div>
                  )}
                </div>
              )}
              <div className="summary-total">
                <span>Total to pay</span>
                <strong>{money(walletDeduction > 0 ? chargeAmount : grossTotal)}</strong>
              </div>
              {error && (
                <p className="form-error" role="alert">
                  {error}
                </p>
              )}
              <button
                className="button"
                disabled={
                  busy ||
                  (hasPhysical && !addressId) || !activeShipping?.quote_token || shippingRates.isFetching ||
                  cart.items.some((row) => !row.purchasable)
                }
                onClick={placeOrder}
              >
                {busy
                  ? paymentType === "stripe_wallet" ? "Redirecting to Stripe…" : "Placing order…"
                  : paymentType === "stripe_wallet"
                    ? `Pay ${money(walletDeduction > 0 ? chargeAmount : grossTotal)} with Stripe`
                    : `Pay ${money(grossTotal)} from ProAce Wallet`}
                <ArrowRight size={17} />
              </button>
              <p className="fine-print">
                By placing your order, you agree to our{" "}
                <Link href="/terms">Terms & Returns</Link>.
              </p>
            </aside>
          </div>
        )}
        {showAddressModal && (
          <div
            className="checkout-modal-backdrop"
            role="presentation"
            onMouseDown={(e) => {
              if (e.target === e.currentTarget) {
                setShowAddressModal(false);
                setModalAdding(false);
                setModalEditing(null);
              }
            }}
          >
            <section
              className="checkout-address-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="address-modal-title"
            >
              <div className="checkout-modal-head">
                <div>
                  <span className="eyebrow green">CHECKOUT DELIVERY</span>
                  <h2 id="address-modal-title">
                    {modalAdding
                      ? "Add Delivery Address"
                      : modalEditing
                      ? "Edit Address"
                      : "Select Delivery Address"}
                  </h2>
                  <p className="muted" style={{ margin: "4px 0 0", fontSize: "12px" }}>
                    {modalAdding
                      ? "Enter your delivery details below."
                      : modalEditing
                      ? "Update this address for delivery."
                      : "Choose which saved address to deliver your items to."}
                  </p>
                </div>
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Close address selector"
                  onClick={() => {
                    setShowAddressModal(false);
                    setModalAdding(false);
                    setModalEditing(null);
                  }}
                >
                  <X size={18} />
                </button>
              </div>

              {modalAdding ? (
                <div style={{ marginTop: "14px" }}>
                  <AddressForm
                    embedded
                    onSaved={(address) => {
                      client.invalidateQueries({ queryKey: ["addresses"] });
                      setSelected(address.id);
                      setModalAdding(false);
                      setShowAddressModal(false);
                      notify("Address saved and selected for delivery");
                    }}
                    onCancel={() => setModalAdding(false)}
                  />
                </div>
              ) : modalEditing ? (
                <div style={{ marginTop: "14px" }}>
                  <AddressForm
                    embedded
                    initialData={modalEditing}
                    onSaved={(address) => {
                      client.invalidateQueries({ queryKey: ["addresses"] });
                      setSelected(address.id);
                      setModalEditing(null);
                      setShowAddressModal(false);
                      notify("Address updated");
                    }}
                    onCancel={() => setModalEditing(null)}
                  />
                </div>
              ) : (
                <div className="checkout-modal-body">
                  <div className="checkout-modal-address-list">
                    {addresses.data?.map((address) => {
                      const isSelected = addressId === address.id;
                      return (
                        <div
                          key={address.id}
                          className={`checkout-modal-address-card ${isSelected ? "selected" : ""}`}
                          onClick={() => {
                            setSelected(address.id);
                            setShowAddressModal(false);
                          }}
                          role="button"
                          tabIndex={0}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              setSelected(address.id);
                              setShowAddressModal(false);
                            }
                          }}
                        >
                          <div className="modal-address-radio">
                            <span className={`radio-dot ${isSelected ? "active" : ""}`}>
                              {isSelected && <Check size={12} strokeWidth={3} />}
                            </span>
                          </div>
                          <div className="modal-address-info">
                            <div className="modal-address-badges">
                              <strong>{address.address}</strong>
                              {address.is_default && (
                                <span className="status">Default</span>
                              )}
                              {isSelected && (
                                <span className="status status-selected">Selected</span>
                              )}
                            </div>
                            <p>
                              {address.city}, {address.state} {address.zip}
                            </p>
                            <small>{address.country}</small>
                          </div>
                          <div
                            className="modal-address-actions"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button
                              type="button"
                              className="icon-button modal-address-pen"
                              aria-label={`Edit ${address.address}`}
                              title="Edit this address"
                              onClick={() => setModalEditing(address)}
                            >
                              <Pencil size={14} />
                            </button>
                            {!isSelected && (
                              <button
                                type="button"
                                className="button secondary modal-deliver-btn"
                                onClick={() => {
                                  setSelected(address.id);
                                  setShowAddressModal(false);
                                }}
                              >
                                Deliver here
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div className="checkout-modal-footer">
                    <button
                      type="button"
                      className="button secondary"
                      style={{ width: "100%", justifyContent: "center" }}
                      onClick={() => setModalAdding(true)}
                    >
                      <Plus size={16} />
                      <span>Add a new address</span>
                    </button>
                  </div>
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </Gate>
  );
}
