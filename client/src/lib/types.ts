export type SellerTier = {
  tier: 'official' | 'starter' | 'booster' | 'accelerator' | 'power' | 'mega' | 'legendary';
  name: string;
  badge_color: 'gold' | 'blue' | 'silver' | 'purple' | 'emerald' | 'diamond' | 'legendary';
  badge_hex: string;
  min_sales: number;
  current_sales?: number;
  next_tier?: string | null;
  next_threshold?: number | null;
};
export type ProductVariant = {
  id?: string;
  name: string;
  sku?: string;
  price?: string;
  price_delta?: string;
  available?: number;
};
export type Product = { is_own_store: boolean; is_official_store?: boolean; seller_tier?: SellerTier; is_digital: boolean; id: number; title: string; description: string; category: string; brand: string; price: string; sale_price: string; discount: number; available: number; weight?: string; sales?: number; flash_sale_end?: string | null; variants?: ProductVariant[]; average_rating: string; rating_count: number; store: number; store_name: string; store_username: string; image: string; images: string[]; tags: string[]; created: string };
export type User = { id: number; email: string; first_name: string; last_name: string; phone1: string; is_staff: boolean; is_superuser: boolean };
export type StaffUser = User & { phone2?: string | null; gender: 'male' | 'female'; is_active: boolean; date_joined: string };
export type Address = { id: number; address: string; city: string; state: string; country: string; zip: string; is_default: boolean };
export type CartLine = { product: Product; quantity: number; total: string; purchasable: boolean };
export type Cart = { id?: number; items: CartLine[]; subtotal: string; shipping: string; total: string };
export type ShippingRate = { service_id: string; name: string; description: string; amount: string; is_default: boolean };
export type TrackingEvent = { status: string; description: string; timestamp: string };
export type Order = { id: number; reference: string; status: string; created: string; total: string; subtotal: string; payment_type: string; carrier?: string; tracking_number?: string; tracking_url?: string; shipped_at?: string | null; delivered_at?: string | null; tracking_events?: TrackingEvent[]; items: { product: number; title: string; image: string; quantity: number; unit_price: string; is_digital?: boolean; download_url?: string }[]; address: Address };
export type StoreProfile = { email?: string; bio?: string; announcement?: string; pinned_products?: number[]; avatar_url?: string; banner_url?: string; website?: string; instagram?: string; twitter?: string; facebook?: string; whatsapp?: string; phone1?: string; phone2?: string };
export type Store = { id: number; name: string; username: string; status: 'pending' | 'active' | 'blocked'; is_official?: boolean; seller_tier?: SellerTier; verified_at?: string | null };
export type PublicStore = { id: number; name: string; username: string; is_official: boolean; seller_tier?: SellerTier; created: string; profile?: StoreProfile | null; address?: { city: string; state: string; country: string } | null; product_count: number };

export type Review = {
  id: number;
  author: string;
  rating: number;
  label: string;
  comment: string;
  images?: string[];
  created: string;
  is_verified_buyer: boolean;
  is_own_review?: boolean;
};

export type MerchantProduct = { id: number; title: string; description: string; category: string; price: string; available: number; discount: number; visibility: boolean; brand: string; image_url: string; images: {id: number; image: string}[]; tags: string[]; sales: number; flash_sale_end?: string | null; variants?: ProductVariant[]; is_digital: boolean; digital_file_url: string; weight?: string };
export type Page<T> = { count: number; results: T[]; next?: string | null; previous?: string | null; pages?: number; page?: number };
export type UserWalletTransaction = { id: number; transaction_type: 'credit' | 'debit'; amount: string; source: string; description: string; reference: string; created: string };
export type UserWallet = { balance: string; transactions: UserWalletTransaction[] };
export type StorePayout = { id: number; store?: number | null; wallet?: number | null; amount: string; status: 'pending' | 'completed' | 'rejected'; payout_method: string; account_details: Record<string, unknown>; reference: string; processed_at?: string | null; notes?: string; created: string };
export type StoreEarningsLedger = { id: number; wallet: number; store: number; store_name: string; store_username: string; order?: number | null; entry_type: 'sale' | 'fee' | 'payout' | 'refund' | 'adjustment'; gross_amount: string; fee_amount: string; net_amount: string; status: 'pending' | 'available' | 'completed' | 'reversed'; available_at?: string | null; cleared_at?: string | null; description: string; reference: string; created: string };
export type MerchantStoreSummary = { store_id: number; store_name: string; store_username: string; status: string; is_official: boolean; gross_sales: string; platform_fee_percent: string; platform_fee_deducted: string; net_sales: string; in_review: string; cleared_total: string; payouts_completed: string; payouts_pending: string; available_balance: string; refund_window_days: number };
export type MerchantWallet = { wallet_id: number; stripe_account_id: string; stripe_details_submitted: boolean; stripe_payouts_enabled: boolean; available_balance: string; pending_balance: string; total_withdrawn: string; total_gross_sales: string; total_platform_fees: string; total_net_sales: string; refund_window_days: number; platform_fee_percent: string; stores_count: number; stores: MerchantStoreSummary[] };
export type Dashboard = { inventory: { total: number; published: number; drafts: number; units: number; low_stock: number; out_of_stock: number }; orders: { total: number; by_status: {status: string; count: number}[] }; sales: { units: number; estimated_item_value: string }; wallet?: { gross_sales: string; platform_fee_percent: string; platform_fee_deducted: string; net_sales: string; in_review: string; cleared_total?: string; payouts_completed?: string; payouts_pending?: string; available_balance: string; refund_window_days: number }; orders_by_day: {date: string; count: number}[]; top_products: {product_id: number; product__title: string; units: number}[]; low_stock_products: { id: number; title: string; available: number}[] };
export type NotificationItem = { id: number; level: 'success' | 'info' | 'warning' | 'error'; unread: boolean; verb: string; description?: string | null; timestamp: string; deleted: boolean; data?: Record<string, unknown> | null; actor?: { id?: number; type: string; label: string } | null; target?: { id?: number; type: string; label: string } | null; action_object?: { id?: number; type: string; label: string } | null };
export type NotificationCounts = { unread: number; read: number; archived: number; total: number };
export type AdminDashboardData = {
  period: { from: string; to: string; days: number };
  users: { total: number; active: number; staff: number; new: number };
  stores: { total: number; active: number; blocked: number; new: number };
  products: { total: number; published: number; hidden: number; out_of_stock: number; sponsored: number };
  orders: { total: number; ordered: number; gross_total: string; by_status: { status: string; count: number }[] };
  coupons: { total: number; active: number };
  refunds: { total: number; accepted: number; pending: number };
  marketers: { total: number };
  recent_orders: { orderId: string; user: number; buyer_email: string; total: string; status: string; created: string; carrier?: string; tracking_number?: string }[];
  top_stores: { id: number; name: string; username: string; status: string; products: number; orders: number }[];
};
