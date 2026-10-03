"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronRight,
  LockKeyhole,
  MapPin,
  Plus,
  ShoppingBag,
  Trash2,
  Truck,
  WalletCards,
} from "lucide-react";
import { api, money } from "@/lib/api";
import type { Address, Order, Product, UserWallet } from "@/lib/types";
import { useShop } from "./providers";
import { AddressForm, Gate } from "./account";
import { Empty, ErrorState, Loading, ProductImage, Quantity } from "./ui";

export function CartPage() {
  const { cart, cartLoading, cartError, setQuantity, notify } = useShop();
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
              <article className="cart-row" key={row.product.id}>
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
                        : "Unavailable in this quantity"}
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
                <Quantity
                  value={row.quantity}
                  max={row.product.available}
                  disabled={busy === row.product.id}
                  onChange={(value) => update(row.product, value)}
                />
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
                {Number(cart.shipping) ? money(cart.shipping) : "On us"}
              </strong>
            </div>
            <div className="summary-total">
              <span>Total</span>
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

export function CheckoutPage() {
  const { user, cart, cartLoading, cartError, notify } = useShop();
  const router = useRouter();
  const client = useQueryClient();
  const search = useSearchParams();
  const addresses = useQuery({
    queryKey: ["addresses", user?.id],
    queryFn: () => api<Address[]>("addresses"),
    enabled: !!user,
  });
  const [selected, setSelected] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [coupon, setCoupon] = useState("");
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
  const addressId =
    selected ||
    addresses.data?.find((address) => address.is_default)?.id ||
    addresses.data?.[0]?.id;

  const shippingRates = useQuery({
    queryKey: ["shipping-rates", addressId],
    queryFn: () =>
      api<import("@/lib/types").ShippingRate[]>(
        `checkout/shipping-rates?address=${addressId}`,
      ),
    enabled: !!addressId,
  });

  const activeShipping =
    shippingRates.data?.find((rate) => rate.service_id === shippingService) ||
    shippingRates.data?.[0];
  const shippingFee = activeShipping
    ? Number(activeShipping.amount)
    : Number(cart.shipping);
  const totalAmount = Math.max(0, Number(cart.subtotal) + shippingFee);
  const hasPhysical = cart.items.some((item) => !item.product.is_digital);

  useEffect(() => {
    const sessionId = search.get("wallet_session_id");
    if (!sessionId || !user) return;
    setBusy(true);
    api<Order>("checkout/wallet-confirm", "POST", { session_id: sessionId })
      .then((order) => router.replace(`/orders/${order.id}?placed=true`))
      .catch((error) => setError((error as Error).message))
      .finally(() => setBusy(false));
  }, [router, search, user]);

  async function placeOrder() {
    if (!addressId) {
      setError("Choose a delivery address first.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const selectedService = activeShipping?.service_id || shippingService;
      if (paymentType === "user_wallet") {
        const order = await api<Order>("checkout", "POST", {
          address: addressId,
          checkout_key: checkoutKey,
          coupon: coupon.trim(),
          payment_type: "user_wallet",
          shipping_service: selectedService,
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
          address: addressId,
          checkout_key: checkoutKey,
          coupon: coupon.trim(),
          shipping_service: selectedService,
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
              <div className="step-heading">
                <span>1</span>
                <h2>Where are we delivering?</h2>
              </div>
              {addresses.isLoading ? (
                <Loading />
              ) : addresses.error ? (
                <ErrorState error={addresses.error} />
              ) : (
                <div className="checkout-addresses">
                  {addresses.data?.map((address) => (
                    <label
                      key={address.id}
                      className={`select-address ${addressId === address.id ? "selected" : ""}`}
                    >
                      <input
                        type="radio"
                        name="address"
                        checked={addressId === address.id}
                        onChange={() => setSelected(address.id)}
                      />
                      <div>
                        <strong>{address.address}</strong>
                        <p>
                          {address.city}, {address.state}
                          <br />
                          {address.country}, {address.zip}
                        </p>
                      </div>
                      {address.is_default && (
                        <span className="status">Default</span>
                      )}
                    </label>
                  ))}
                </div>
              )}
              {adding || addresses.data?.length === 0 ? (
                <AddressForm
                  onSaved={(address) => {
                    setSelected(address.id);
                    setAdding(false);
                  }}
                  onCancel={
                    addresses.data?.length ? () => setAdding(false) : undefined
                  }
                />
              ) : (
                <button className="text-link" onClick={() => setAdding(true)}>
                  <Plus size={17} />
                  Add a new address
                </button>
              )}
              <div className="step-heading">
                <span>2</span>
                <h2>Choose shipping method</h2>
              </div>
              {shippingRates.isLoading ? (
                <Loading />
              ) : shippingRates.error ? (
                <p className="form-error">
                  Unable to calculate USPS rates for this address. Please ensure
                  a valid US ZIP code.
                </p>
              ) : (
                <div className="checkout-addresses">
                  {shippingRates.data?.map((rate) => (
                    <label
                      key={rate.service_id}
                      className={`select-address ${activeShipping?.service_id === rate.service_id ? "selected" : ""}`}
                    >
                      <input
                        type="radio"
                        name="shipping_service"
                        checked={activeShipping?.service_id === rate.service_id}
                        onChange={() => setShippingService(rate.service_id)}
                      />
                      <div>
                        <strong>
                          {rate.name} —{" "}
                          {Number(rate.amount) === 0
                            ? "Free"
                            : money(rate.amount)}
                        </strong>
                        <p>{rate.description}</p>
                      </div>
                      <Truck size={22} />
                    </label>
                  ))}
                </div>
              )}
              <div className="step-heading">
                <span>3</span>
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
                  <strong>Cards, Stripe & Cash App</strong>
                  <p>
                    Fast, secure upfront payment with live buyer protection.
                  </p>
                </div>
                <WalletCards size={22} />
              </label>
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
                    ? "Domestic shipping rates are calculated live via USPS Web Tools."
                    : "Digital items are delivered instantly online with no delivery fee."}
                </p>
              </div>
            </section>
            <aside className="order-summary">
              <h2>Your order</h2>
              {cart.items.map((row) => (
                <div className="mini-item" key={row.product.id}>
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
              <div className="summary-line">
                <span>Delivery ({activeShipping?.name || "USPS"})</span>
                <strong>
                  {shippingFee === 0 ? "Free" : money(shippingFee)}
                </strong>
              </div>
              <label className="field">
                <span>Coupon code</span>
                <input
                  value={coupon}
                  onChange={(event) => setCoupon(event.target.value)}
                  placeholder="Enter a coupon"
                  autoComplete="off"
                />
              </label>
              <div className="summary-total">
                <span>Total to pay</span>
                <strong>{money(totalAmount)}</strong>
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
                  !addressId ||
                  cart.items.some((row) => !row.purchasable)
                }
                onClick={placeOrder}
              >
                {busy ? "Redirecting to payment…" : `Pay ${money(totalAmount)}`}
                <ArrowRight size={17} />
              </button>
              <p className="fine-print">
                By placing your order, you agree to our{" "}
                <Link href="/terms">Terms & Returns</Link>.
              </p>
            </aside>
          </div>
        )}
      </div>
    </Gate>
  );
}
