export type ActivityTimestamps = {
  created?: string;
  updated?: string;
  last_login?: string | null;
  last_active_at?: string | null;
  date_joined?: string;
};

export type LifecycleTimestamps = {
  updated?: string;
  ordered_date?: string;
  status_updated_at?: string | null;
  cancelled_at?: string | null;
  refunded_at?: string | null;
};

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
  barcode?: string;
  price?: string;
  price_delta?: string;
  image_url?: string;
  available?: number;
};

export type Product = LifecycleTimestamps & {
  selected_variant?: string;
  is_own_store: boolean;
  is_official_store?: boolean;
  store_verified?: boolean;
  seller_tier?: SellerTier;
  is_digital: boolean;
  digital_preview_watermark?: boolean;
  id: number;
  title: string;
  description: string;
  category: string;
  brand: string;
  price: string;
  sale_price: string;
  discount: number;
  available: number;
  weight?: string;
  length?: string;
  width?: string;
  height?: string;
  sales?: number;
  flash_sale_end?: string | null;
  variants?: ProductVariant[];
  average_rating: string;
  rating_count: number;
  store: number;
  store_name: string;
  store_username: string;
  image: string;
  images: string[];
  tags: string[];
  created: string;
  specifications?: {
    serial?: string;
    attributes?: string;
    height?: string;
    width?: string;
    breadth?: string;
    weight?: string;
    color?: string;
  } | null;
  product_type?: 'standard' | 'affiliate_clickbank';
  affiliate_hoplink?: string;
  affiliate_vendor_nickname?: string;
  affiliate_button_text?: string;
};

export type User = ActivityTimestamps & {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone1: string;
  is_staff: boolean;
  is_superuser: boolean;
  is_business_admin: boolean;
  must_change_password: boolean;
  role: string;
};

export type StaffUser = User & {
  phone2?: string | null;
  gender: 'male' | 'female';
  is_active: boolean;
  staff_email_verified: boolean;
  staff_blocked_at?: string | null;
  date_joined: string;
};

export type AdminUserProfile = {
  user: StaffUser;
  wallet: {
    balance: string;
    transactions: Array<{
      id: number;
      type: string;
      source: string;
      amount: string;
      description: string;
      created: string;
    }>;
  };
  orders: Array<LifecycleTimestamps & {
    id: number;
    reference: string;
    created: string;
    status: string;
    total: string;
  }>;
  activity: Array<{
    id: number;
    verb: string;
    description?: string;
    created: string;
    level: string;
  }>;
};

export type Address = {
  id: number;
  address: string;
  city: string;
  state: string;
  country: string;
  zip: string;
  is_default: boolean;
};

export type CartLine = {
  product: Product;
  quantity: number;
  total: string;
  purchasable: boolean;
};

export type Cart = {
  updated?: string;
  id?: number;
  items: CartLine[];
  subtotal: string;
  shipping: string;
  total: string;
};

export type ShippingRate = {
  carrier: string;
  currency: string;
  source: string;
  quote_token: string;
  tax?: string;
  tax_rate?: string;
  tax_jurisdiction?: string;
  service_id: string;
  name: string;
  description: string;
  amount: string;
  is_default: boolean;
};

export type TrackingEvent = {
  status: string;
  description: string;
  timestamp: string;
};

export type OrderFulfillment = {
  store: number;
  status: string;
  carrier: string;
  tracking_number: string;
  shipped_at: string | null;
  delivered_at: string | null;
};

export type Order = LifecycleTimestamps & {
  id: number;
  reference: string;
  status: string;
  created: string;
  total: string;
  paid_total: string;
  refunded_total: string;
  fulfillments: OrderFulfillment[];
  subtotal: string;
  tax?: string;
  tax_snapshot?: Record<string, unknown>;
  payment_type: string;
  carrier?: string;
  tracking_number?: string;
  tracking_url?: string;
  shipped_at?: string | null;
  delivered_at?: string | null;
  tracking_events?: TrackingEvent[];
  items: {
    product: number;
    title: string;
    image: string;
    quantity: number;
    unit_price: string;
    net_total?: string;
    discount_amount?: string;
    tax_amount?: string;
    line_total?: string;
    is_digital?: boolean;
    digital_preview_watermark?: boolean;
    download_url?: string;
  }[];
  address: Address;
};

export type StoreProfile = {
  email?: string;
  bio?: string;
  announcement?: string;
  pinned_products?: number[];
  avatar_url?: string;
  banner_url?: string;
  website?: string;
  instagram?: string;
  twitter?: string;
  facebook?: string;
  whatsapp?: string;
  phone1?: string;
  phone2?: string;
};

export type Store = ActivityTimestamps & {
  assigned_staff?: number[];
  id: number;
  name: string;
  username: string;
  status: 'pending' | 'active' | 'blocked';
  is_official?: boolean;
  seller_tier?: SellerTier;
  verified_at?: string | null;
  blocked_reason?: string | null;
};

export type PublicStore = ActivityTimestamps & {
  id: number;
  name: string;
  username: string;
  status?: 'pending' | 'active' | 'blocked';
  is_official: boolean;
  is_verified?: boolean;
  is_preview?: boolean;
  seller_tier?: SellerTier;
  created: string;
  profile?: StoreProfile | null;
  address?: {
    city: string;
    state: string;
    country: string;
  } | null;
  product_count: number;
};

export type Review = {
  id: number;
  author: string;
  rating: number;
  label: string;
  comment: string;
  images?: string[];
  created: string;
  updated?: string;
  is_edited?: boolean;
  is_verified_buyer: boolean;
  is_own_review?: boolean;
  can_moderate?: boolean;
};

export type MerchantProduct = LifecycleTimestamps & {
  created?: string;
  id: number;
  title: string;
  description: string;
  category: string;
  price: string;
  available: number;
  discount: number;
  visibility: boolean;
  brand: string;
  image_url: string;
  images: { id: number; image: string }[];
  tags: string[];
  sales: number;
  flash_sale_end?: string | null;
  variants?: ProductVariant[];
  is_digital: boolean;
  digital_file_url: string;
  digital_preview_watermark?: boolean;
  weight?: string;
  length?: string;
  width?: string;
  height?: string;
  product_type?: 'standard' | 'affiliate_clickbank';
  affiliate_hoplink?: string;
  affiliate_vendor_nickname?: string;
  affiliate_button_text?: string;
};

export type Page<T> = {
  count: number;
  results: T[];
  next?: string | null;
  previous?: string | null;
  pages?: number;
  page?: number;
};

export type UserWalletTransaction = {
  id: number;
  transaction_type: 'credit' | 'debit';
  amount: string;
  source: string;
  description: string;
  reference: string;
  created: string;
};

export type UserWallet = {
  balance: string;
  transactions: UserWalletTransaction[];
};

export type StorePayout = {
  id: number;
  store?: number | null;
  store_name?: string;
  wallet?: number | null;
  amount: string;
  status: 'pending' | 'completed' | 'rejected';
  payout_method: string;
  account_details: Record<string, unknown>;
  reference: string;
  processed_at?: string | null;
  notes?: string;
  created: string;
};

export type StoreEarningsLedger = {
  id: number;
  wallet: number;
  store: number;
  store_name: string;
  store_username: string;
  order?: number | null;
  entry_type: 'sale' | 'fee' | 'payout' | 'refund' | 'adjustment';
  gross_amount: string;
  fee_amount: string;
  net_amount: string;
  status: 'pending' | 'available' | 'completed' | 'reversed';
  available_at?: string | null;
  cleared_at?: string | null;
  description: string;
  reference: string;
  created: string;
};

export type MerchantStoreSummary = {
  store_id: number;
  store_name: string;
  store_username: string;
  status: string;
  is_official: boolean;
  gross_sales: string;
  platform_fee_percent: string;
  platform_fee_deducted: string;
  net_sales: string;
  in_review: string;
  cleared_total: string;
  payouts_completed: string;
  payouts_pending: string;
  available_balance: string;
  refund_window_days: number;
};

export type MerchantWallet = {
  wallet_id: number;
  stripe_account_id: string;
  stripe_details_submitted: boolean;
  stripe_payouts_enabled: boolean;
  available_balance: string;
  pending_balance: string;
  total_withdrawn: string;
  total_gross_sales: string;
  total_platform_fees: string;
  total_net_sales: string;
  refund_window_days: number;
  platform_fee_percent: string;
  stores_count: number;
  stores: MerchantStoreSummary[];
};

export type Dashboard = {
  inventory: {
    total: number;
    published: number;
    drafts: number;
    units: number;
    low_stock: number;
    out_of_stock: number;
  };
  orders: {
    total: number;
    by_status: { status: string; count: number }[];
  };
  sales: {
    units: number;
    estimated_item_value: string;
  };
  wallet?: {
    gross_sales: string;
    platform_fee_percent: string;
    platform_fee_deducted: string;
    net_sales: string;
    in_review: string;
    cleared_total?: string;
    payouts_completed?: string;
    payouts_pending?: string;
    available_balance: string;
    refund_window_days: number;
  };
  orders_by_day: { date: string; count: number }[];
  top_products: { product_id: number; product__title: string; units: number }[];
  low_stock_products: { id: number; title: string; available: number }[];
};

export type NotificationItem = {
  read_at?: string | null;
  updated_at?: string;
  id: number;
  level: 'success' | 'info' | 'warning' | 'error';
  unread: boolean;
  verb: string;
  description?: string | null;
  timestamp: string;
  deleted: boolean;
  data?: Record<string, unknown> | null;
  actor?: { id?: number; type: string; label: string } | null;
  target?: { id?: number; type: string; label: string } | null;
  action_object?: { id?: number; type: string; label: string } | null;
  category?: string;
  store?: { id: number; name: string; username?: string } | null;
};

export type NotificationCategory = {
  id: string;
  label: string;
  count: number;
};

export type NotificationStoreOption = {
  id: number;
  name: string;
  username: string;
  is_official?: boolean;
};

export type NotificationFiltersMeta = {
  categories: NotificationCategory[];
  stores: NotificationStoreOption[];
  counts: NotificationCounts;
};

export type NotificationCounts = {
  unread: number;
  read: number;
  archived: number;
  total: number;
};

export type AdminDashboardData = {
  period: { from: string; to: string; days: number };
  scopes?: Record<string, string>;
  users: { total: number; active: number; staff: number; new: number };
  stores: { total: number; active: number; blocked: number; new: number; new_last_30_days: number };
  products: { total: number; published: number; hidden: number; out_of_stock: number; sponsored: number };
  orders: { total: number; ordered: number; gross_total: string; by_status: { status: string; count: number }[] };
  coupons: { total: number; active: number };
  refunds: { total: number; accepted: number; declined: number; pending: number };
  marketers: { total: number };
  financials: { escrow_total: string; commission_earned: string };
  pending_actions: { withdrawals: number; refunds: number };
  recent_orders: AdminOrder[];
  top_stores: { id: number; name: string; username: string; status: string; products: number; orders: number }[];
};

export type AdminOrder = LifecycleTimestamps & {
  id: number;
  orderId: string;
  user?: number | null;
  buyer_email?: string;
  total: string;
  subtotal?: string;
  status: string;
  payment_type?: string;
  created: string;
  carrier?: string;
  tracking_number?: string;
  shipped_at?: string | null;
  delivered_at?: string | null;
  tracking_events?: Array<{ status: string; description: string; timestamp: string }>;
  items_snapshot?: Array<Record<string, unknown>>;
  address_snapshot?: Record<string, unknown>;
};

export type CouponRedemptionItem = {
  id: number;
  user_email?: string | null;
  order_id?: string | null;
  created: string;
};

export type AdminCoupon = {
  last_used_at?: string | null;
  id: number;
  code: string;
  valid_from: string;
  valid_to: string;
  discount: number;
  num_available: number;
  num_used: number;
  active: boolean;
  created_by?: string | null;
  redemptions?: CouponRedemptionItem[];
};

export type AdminRefund = {
  id: number;
  email: string;
  order: number;
  reason: string;
  refund_type: 'store_credit' | 'original_payment';
  refund_amount: string;
  selected_items: Array<{
    product: number;
    title: string;
    quantity: number;
    unit_price: string;
  }>;
  processing_reason?: string;
  accepted: boolean;
  status: 'pending' | 'approved' | 'declined' | 'failed';
  processed_by?: number | null;
  processed_at?: string | null;
  provider_reference?: string;
  failure_reason?: string;
  created: string;
};

export type StoreAuditProduct = LifecycleTimestamps & {
  id: number;
  title: string;
  category: string;
  price: string;
  visibility: boolean;
  is_digital: boolean;
  has_digital_asset: boolean;
  available: number | null;
  created: string;
  product_type?: 'standard' | 'affiliate_clickbank';
  affiliate_hoplink?: string;
  affiliate_vendor_nickname?: string;
  affiliate_button_text?: string;
};

export type AdminTaxJurisdiction = {
  id: number;
  country: string;
  state: string;
  postal_code: string;
  name: string;
  rate: string;
  tax_shipping: boolean;
  tax_digital: boolean;
  is_active: boolean;
  created: string;
  updated: string;
};

export type AdminTaxesResponse = {
  provider: 'local' | 'stripe';
  stripe_tax_enabled: boolean;
  default_tax_rate: string;
  summary: {
    total_jurisdictions: number;
    active_jurisdictions: number;
    zip_overrides: number;
  };
  results: AdminTaxJurisdiction[];
};
