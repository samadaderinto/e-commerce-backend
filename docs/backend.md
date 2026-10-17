# Backend documentation

## Identifier and date boundaries

Affiliate referral and ClickBank outbound paths accept numeric product IDs only;
malformed paths return 404 rather than reaching integer ORM conversion. Review
deletion validates a supplied `review_id` as a positive integer (400 for malformed
or empty values, 404 for missing records), preserving moderation/ownership checks.
Omitting `review_id` still removes the caller's own review. Its query parameter
is documented in the endpoint's OpenAPI schema.

The shared listing query serializer rejects `end_date=9999-12-31` with 400 before
inclusive-date filtering can overflow; ordinary inclusive end dates are unchanged.
`storefront/test_input_validation.py` covers these boundaries and review ownership.

Catalog tag-change invalidation handles product instances and reverse tag
instances only. Blog posts share Taggit's through model but are excluded from
this product-specific handler, so blog tagging and `populate_fake_data` do not
attempt invalid product-tag queries.

Bank-account list queries support combined `search` (bank, holder, account suffix) and `is_default` filters within the authenticated owner's records. The frontend also filters its complete owner-scoped collection locally, without cross-account cache reuse.

Bank accounts: authenticated owner-scoped `/api/v1/bank-accounts/` GET/POST and `/api/v1/bank-accounts/<id>/` GET/PATCH/DELETE use `core.BankAccount`. Account/routing numbers are Fernet-encrypted with a purpose-specific key derived from `SECRET_KEY`; responses expose last-four identifiers only. Stripe treasury destinations use the parallel `/api/v1/stripe-payout-destinations/` collection and detail routes, encrypt connected account IDs, and expose only their last four characters. Default mutations lock the owner and database constraints allow at most one default for each destination type; deleting a default selects a replacement. Preserve the secret key or migrate encrypted records when rotating it. Treasury withdrawal requests require a saved `bank_account_id` or `stripe_destination_id`, resolve the destination for the authenticated requester, and snapshot its details into the audited request. A saved Stripe destination identifies the intended recipient; the treasury request flow does not execute a Stripe transfer. Staff directory requests exclude all privileged accounts, including direct profile access; staff permission PATCH permits only `is_active` for regular accounts. Stripe Connect re-provisions missing connected accounts without exposing raw provider errors. Payment success returns through `/orders/stripe-return?session_id=…`, confirms ownership/payment and navigates to the actual order; no unpaid order is pre-created. Object storage configuration raises an error when enabled S3 dependencies are missing instead of silently using filesystem storage.

`CELERY_TASK_ALWAYS_EAGER` defaults to false even in debug mode so background tasks do not block HTTP requests. Set it explicitly to true only for tests or diagnostics; offline test settings already do so.

Catalog invalidation queues `storefront.tasks.warm_catalog_snapshot` after commit. The task prepares the first anonymous page for the most recently observed backend origin, preserving host-specific media URLs. A ten-second pending-job lock coalesces bursts; failed enqueue attempts are logged and ordinary requests can still populate snapshots. The Celery worker must run. Tests disable automatic warming with `CATALOG_CACHE_WARM_ENABLED=False` and exercise the task explicitly. Apple public signing keys are cached in Redis for one hour; unknown key IDs force refresh and provider requests time out after five seconds. This is background processing and shared caching; no blanket async view conversion is implied.

Catalog responses expose the backend `visibility` flag. The product page shows the draft preview banner only for explicit `visibility: false`; missing metadata is not evidence of a draft. Hidden products return 404, and unverified-store previews require the store owner or an authorized operator, even with `?preview=1`.

## Lifecycle tracking

`User.updated` records profile/credential changes, while JWT sign-in updates `last_login`. Authenticated requests update `last_active_at` for the user and owned/assigned stores at most once every five minutes; activity writes do not change profile/catalog revision times. Existing device records matching the authenticated user and direct request IP receive the sign-in timestamp. Guest browsing is not assigned to a user.

Product detail visits refresh `Recent.updated` under a user row lock. Cart additions, quantity changes, and removals touch `Cart.updated`. Product, image, specification, and store-profile/address revisions touch `Store.updated`. Product serializers expose both creation and revision timestamps as read-only metadata.

The active shopper cart API is `CartView` at `/api/v1/cart/`. Mutations derive the owner from the authenticated user, enforce aggregate product stock across selected variants, and revalidate listing, store, option and stock state at checkout. The older `CartViewSet` routes remain separately mounted under `/cart/`; they are not the Next.js shopper API. Guest cart and saved-item merge failures remain in browser storage for review and retry instead of being discarded.

Authorized store/product management requests also refresh the selected store's activity, including official-store operations by staff without an explicit assignment. Public customer store visits never mark a merchant active.

`Order.ordered_date` is immutable after creation. Model saves persist `status_updated_at` only on transitions, and record `cancelled_at` / `refunded_at` for those states. Successful partial refunds also record `refunded_at` without changing order status. Tracking events continue to carry the per-event audit trail. Use `save()` for lifecycle transitions; queryset updates bypass model tracking.

Notifications record `read_at` and `updated_at` on individual/bulk reads; marking unread clears `read_at`. Push registration refreshes `last_active_at`, and successful push delivery records `last_sent_at`. Review content changes persist `is_edited`, including edits performed within one second of creation. Reserved coupon redemptions record `last_used_at`. Affiliate redirects increment click counts atomically and record `last_clicked_at`.

Run migrations before serving the updated code. Historical activity/read/transition times remain null when no reliable timestamp exists. Existing `ordered_date` values are retained: previously overwritten values cannot be reconstructed with certainty. New user/notification revision fields establish a baseline at migration time.

The backend lives in `server/`. It is a Django project whose Python settings
package is still named `codematics`. The integrated marketplace runtime uses
`codematics.storefront_settings`.

For the newcomer setup flow and the full route-group overview, see
[Getting started](getting-started.md) and
[Architecture and API map](architecture.md). The route declarations in
`server/storefront/urls.py` are authoritative for the integrated API.

## Code map

- `server/manage.py`: Django management entrypoint.
- `server/codematics/settings.py`: base legacy settings.
- `server/codematics/storefront_settings.py`: integrated commerce runtime.
- `server/codematics/urls.py`: legacy URL tree; the duplicate core API is not mounted.
- `server/core/`: shared identity and customer-domain models, migrations and serializers used across apps.
- `server/storefront/`: integrated `/api/v1/` storefront API, serializers,
  customer views and seed command.
- `server/product/`: product models, catalog presentation, product policies,
  product serializers and product endpoints.
- `server/store/`: seller stores, merchant profile, moderation, media services
  and merchant endpoints.
- `server/cart/`: cart models, cache helpers, serializers and cart endpoints.
- `server/payment/`: checkout, order and payment-adjacent workflows.
- `server/notification/`: notification models and endpoints.
- `server/staff/`: staff/admin-facing API surfaces.
- `server/affiliates/`: affiliate routes and models.
- `server/observability/`: health checks, metrics, JSON logging, request
  middleware, tracing hooks and log indexing helpers.
- `server/utils/`: shared API exception handling and cross-app helpers.

## Runtime behavior

The integrated API is mounted under `/api/v1/`. Public catalog responses exclude
draft products and blocked sellers. Seller and customer ownership are derived
from authenticated users rather than trusting client-supplied owner fields.

Authentication uses JWT bearer tokens at the API layer. The browser storefront
does not store tokens in local storage; it calls through the Next.js proxy, which
keeps tokens in HTTP-only cookies.

### Social Authentication (Google & Apple) & Staff Guardrails
Customers can sign up and sign in using Google or Apple credentials via:
- `POST /api/v1/auth/google/`: Validates Google ID credentials against Google's tokeninfo service (or mock/dev tokens in non-production).
- `POST /api/v1/auth/apple/`: Validates Apple identity JWT tokens and user claims.
- `POST /api/v1/auth/social/`: Unified provider action (`provider: 'google' | 'apple'`).

**Security & Role Guardrails**:
- Administrative and staff accounts (`is_staff=True`, `is_superuser=True`, or `is_business_admin=True`) **cannot sign in via social providers**. Attempting social authentication for an admin/staff identity raises `PermissionDenied` with HTTP 403: `"Administrative and staff accounts cannot sign in via social providers. Please sign in with your email and password."`
- Social signups create customer accounts with unusable passwords (`user.set_unusable_password()`).
- Email addresses are stored in lowercase and login remains case-insensitive for legacy accounts. Password reset links are checked while the account row is locked, invalidated after credential-version changes, and unavailable to inactive accounts. Staff invitations continue to require verified email and password setup; staff and administrators cannot use Google or Apple login.
- Logout returns a generic service error if refresh-token revocation cannot be confirmed, while expired or malformed refresh tokens remain safe to log out idempotently.

**Affiliate Referral Synchronization**:
- New social signups accepting an optional `referral_code` invoke `reward_referral(referral_code, user)` from `server/affiliates/services.py`.
- If the referral code matches a registered marketer, the code is carried through email verification. Only after successful verification does the server create a `Referral` record and credit up to four $25 promotional rewards (`SOURCE_REFERRAL`), for a $100 maximum. Rewards are serialized on the marketer row so concurrent verifications cannot exceed the cap.

Mutating browser flows require same-origin behavior through the proxy. Direct API
clients can use bearer tokens and the OpenAPI docs.

## Product and seller flow

Sellers create a store and pickup address, then create drafts, upload images,
publish products, update pricing/stock/specifications and review seller-specific
orders. Store moderation can block publishing. Product creation and update logic
validates owner, store state, price and stock server-side.

### Seller Tier Ranks & Milestone Verification
Stores automatically earn tier rankings based on cumulative gross sales, dynamically resolved by `calculate_store_tier()` in `server/store/services.py`:
- **Starter** ($0 – $4,999): Sapphire Blue badge (`#2563eb`).
- **Booster** ($5,000 – $24,999): Slate Silver badge (`#64748b`).
- **Accelerator** ($25,000 – $99,999): Vivid Purple badge (`#7c3aed`).
- **Power Seller** ($100,000 – $499,999): Emerald Green badge (`#059669`).
- **Mega Seller** ($500,000 – $999,999): Flame Orange badge (`#ea580c`).
- **Legendary Seller** ($1,000,000+): Cosmic Ruby Flame badge (`#ff0055`).
- **Official Brand Store**: Dedicated Radiant Gold badge (`#d97706`).

### Product Variants, Specifications & Flash Sales
- **Product Specifications (`Product.specifications`)**: Nested technical specifications dictionary exposing dimensions (`height`, `width`, `breadth`, `weight`), `color`, `serial` / part number, and `attributes` string. Specifications and physical dimensions are physical-only; digital downloads and ClickBank partner offers disallow them.
- **Product Variants (`Product.variants`)**: JSON-based array storing opt-in option names (e.g. Size, Color), price deltas (`price_delta`), and dedicated stock allocation (`available`). A blank `CartItem.variant` deliberately represents the separately purchasable main/default product and uses its own price and stock.
- **Flash Deals (`Product.flash_sale_end`)**: Optional expiration timestamp powering urgency badges and live countdown timers across storefronts.
- **Store Announcements (`StoreInfo.announcement`)**: Marquee banner text displayed on the public store showcase page.
- **Verified Buyer Reviews & Moderation**: Restricts review posting to purchasers with up to 3 HTTPS photo URLs (maximum 2,048 characters each); blank-only titles/comments are rejected. The public review endpoint returns the newest 50 reviews and computes verified-buyer badges with a bounded query count. Authors can edit/delete their own review; store owners and backoffice staff can moderate/delete reviews via `DELETE /api/v1/products/<pk>/reviews/?review_id=<id>`. Rating averages refresh after API changes and Django admin edits or deletions.
- **Digital Image Watermarking (`Product.digital_preview_watermark`)**: Digital goods support high-resolution image asset downloads (PNG, JPG, WebP, SVG). The buyer preview watermark overlay (`PROACE PREVIEW`) is guarded and enabled exclusively for digital image assets; non-image digital files (PDF e-books, audio MP3s, software ZIPs) disable the option and normalize `digital_preview_watermark=False` both client-side and server-side. Digital-artwork gallery uploads and image-variant assets generate public preview derivatives under `images/digital-previews/`; the submitted originals never become public gallery files.

### Media upload limits and digital asset isolation
- Main and variant digital assets are limited to 50 MiB. Nginx accepts 55 MiB request bodies for multipart framing and allows up to 60 seconds between body reads. Variant download paths must remain inside that exact product's private `digital_products/{store_id}/{product_id}/variants/` directory. Failed image-preview generation occurs before the private original is stored; if storing the original fails, the generated preview is removed.
- Private originals remain available after a listing is replaced or removed because completed orders retain immutable download paths and buyers may still have valid entitlements. Unreferenced files from abandoned staged uploads can accumulate; safe cleanup requires a retention period and reference checks against live listings and paid order snapshots.

### Media upload limits and digital asset isolation
- Main and variant digital assets are limited to 50 MiB. Nginx accepts 55 MiB request bodies for multipart framing and allows up to 60 seconds between body reads. Variant download paths must remain inside that exact product's private `digital_products/{store_id}/{product_id}/variants/` directory. Failed image-preview generation occurs before the private original is stored; if storing the original fails, the generated preview is removed.
- Private originals remain available after a listing is replaced or removed because completed orders retain immutable download paths and buyers may still have valid entitlements. Unreferenced files from abandoned staged uploads can accumulate; safe cleanup requires a retention period and reference checks against live listings and paid order snapshots.

### Merchant escrow and payouts
- **Platform Commission (4%)**: Automatically items and deducts a 4% platform fee (`PLATFORM_FEE_PERCENT = 4.00`) from gross item sales.
- **7-Day Review Escrow**: Net sales from customer orders placed within the 7-day refund window (`REFUND_WINDOW_DAYS = 7`) are held in `in_review` status.
- **Cleared Balance**: Once orders surpass the 7-day refund deadline, funds unlock to `cleared_net` and become available for merchant withdrawal requests via `/api/v1/stores/<id>/payouts/`.
- **Payout Scope & Readiness**: Store payout requests are rechecked against that store's own cleared balance while the merchant wallet is locked; `/api/v1/stores/wallet/payouts/` remains a combined-wallet withdrawal unless a `store_id` is supplied. Stripe Connect approval requires the saved account to report payouts enabled. Payout requests reserve funds until completed or rejected.
- **Admin Payout Processing**: Backoffice staff review and process withdrawal requests via `/api/v1/admin/staff/payouts/` with approve/reject actions and audit notes.
- **Fulfillment & Carrier Tracking**: Merchants update carrier, tracking number, and milestone descriptions on store orders via `/api/v1/stores/<id>/orders/<order_id>/tracking/`, which triggers customer notifications and provides live tracking links.
- **Store Order Search & Filtering**: `GET /api/v1/stores/<id>/orders/` supports `search` (order reference ID, customer name, email, phone, tracking number, purchased item titles), `order_id` (a single order only when it contains items from that store), `status` (including `picked up`), `days` / `date_from` / `date_to`, `carrier`, `delivery_method`, and `ordering` (`-created`, `created`, `-updated`, `updated`). Multi-store merchants can filter and switch across their stores seamlessly.

## ProAce User Wallet, Order Cancellation, and 7-day refunds

- **Customer Wallet (`/api/v1/wallet/`)**: Every registered customer has an integrated store balance for instant 1-click checkout purchases and instant store credit refund resolution.
- **Merchant Wallet (`/api/v1/stores/wallet/`)**: A normal merchant's unified wallet is created atomically with their first store and aggregates earnings across all stores they own. Sales, Stripe Connect setup, and wallet/payout access also safely create or retrieve the same wallet. Administrator-owned official store proceeds use Platform Treasury instead.
- **Stripe Connect onboarding**: `/api/v1/stores/<id>/connect-stripe/` creates or resumes Express onboarding and refuses to create another link after payouts are enabled or submitted details are under review. The Express account ID commits before its onboarding link is created, so a temporary link failure can be retried without orphaning another account; account creation also uses a stable user-scoped Stripe idempotency key. Stripe returns to merchant settings, which calls `/api/v1/stores/<id>/stripe-status/` to persist authoritative `details_submitted` and `payouts_enabled` flags; accounts with required details remaining can resume setup.
- **Wallet Top-Up (`/api/v1/wallet/topup-session/`, `/wallet/topup-confirm/`)**: Customers can top up their wallet balance with preset ($25, $50, $100, $250, $500) or custom ($5–$25,000) amounts, subject to $50,000 daily and $100,000 monthly limits including outstanding reservations.
- **Split-Tender Payments**: Customers can combine available wallet balances with Stripe payments during checkout, deducting the wallet credit from the card charge. Checkout cancellation identifies the exact attempt; wallet funds are released only after Stripe confirms that its Checkout Session is expired. A provider lookup or expiry failure leaves the reservation available to the scheduled recovery task. Top-up cancellation serializes against funding confirmation, refuses ambiguous multiple-session cancellation, and never marks a completed payment as released.
- **12-Hour Physical Order Cancellation (`/api/v1/orders/<id>/cancel/`)**: Customers can cancel physical orders within 12 hours of placement if they are in `pending` or `confirmed` status and have not yet been marked as shipped by the seller. Cancellation locks the order, restocks physical product/variant quantities once, reverses merchant earnings, and refunds settled funds back to the customer's wallet or original payment method. Orders containing instant digital downloads cannot be cancelled or refunded once access is delivered. Cancellation is blocked after any store starts fulfillment or after 12 hours.
- **7-Day Refund Policy (`/api/v1/orders/<id>/refund/`)**: Customers can request refunds for physical items within 7 days of order placement. Refund destinations can be selected as ProAce Store Credit (instant wallet credit upon admin approval) or original payment method. Digital goods are non-refundable once delivered.
  - **Duplicate Prevention & Pending Edits**: Duplicate refund requests for the same order are strictly rejected while an active refund is pending review or after full payment settlement. Customers can retrieve (`GET`) and edit (`PATCH`/`PUT`) their existing pending request (reasons, refund destination, selected items) before staff moderation.
  - **Order Serialization Integration**: `GET /api/v1/orders/<id>/` exposes `active_refund` metadata (`id`, `status`, `is_pending`, `reason`, `refund_type`, `refund_amount`, `product_ids`, `failure_reason`, timestamps) directly to the customer storefront.
- **Coupon Lifecycle & Audit Preservation (`/api/v1/admin/staff/coupons/<id>/`)**: Unused coupons (`num_used == 0` and zero redemptions) can be permanently deleted by backoffice staff. Coupons with recorded customer redemption history (`num_used > 0` or redemptions present) cannot be deleted to preserve order records, receipts, and financial audit trails; they must remain deactivated.
- **Digital Order Fulfillment Guardrails (`execute_order_status_transition`, `OrderDetailView`)**: Purely digital orders are fulfilled electronically immediately upon purchase into `delivered` status with $0.00 shipping fees and no delivery address requirement. Digital orders cannot be transitioned to physical delivery statuses (`shipped`, `picked up`) or reverted from `delivered` via staff backoffice or merchant store actions. In the event of legacy or manual database drift, `OrderDetailView` self-heals digital orders to `delivered` and clears `shipped_at` to `None`. Delivery confirmation email notifications omit carrier and tracking numbers for digital purchases.

### User Profile Avatar & Media Storage
- **Avatar Storage (`User.avatar_image`, `User.avatar_url`)**: Authenticated users across all roles (customers, merchants, staff, superadmins) can upload a personal avatar. Media files are uploaded to `user-profiles/avatars/` in MinIO/media storage.
- **Image Specifications & Validation**: Uploads are validated server-side by `UserAvatarImageSerializer` for exact 512x512 resolution, JPEG/PNG/WebP formats, and a 5MB maximum file size. Public user/store avatars, store branding, and product gallery images are decoded and re-encoded server-side, applying EXIF orientation and removing embedded metadata before storage. Images are limited to 40 million pixels to bound decode memory.
- **Endpoints**:
  - `POST /api/v1/me/avatar/`: Authenticated user uploads an avatar image via multipart form data (`avatar_image`).
  - `DELETE /api/v1/me/avatar/`: Authenticated user deletes their avatar, cleaning up the storage file and setting `avatar_image` and `avatar_url` to null.
  - `GET /api/v1/users/<pk>/public/images/avatar/`: Public proxy endpoint serving the user avatar with Cache-Control headers and 404 fallback.
- **Serializer Integration**: `UserSerializer` and `StaffSerializer` dynamically generate the proxy URL `/api/users/<pk>/public/images/avatar?v=<timestamp>` to prevent stale browser cache while isolating backend origins.

### User Email Communication Preferences
- **Preference Storage (`User.email_product_recommendations`, `User.email_marketing`)**: Users maintain granular opt-in controls over non-transactional outbound emails. Product recommendations default to `True`; marketing/promotional announcements default to `False`. Critical transaction notices (order receipts, shipping milestones, refund disbursements, password resets) are strictly preserved and bypass these marketing toggles.
- **Endpoints**:
  - `GET /api/v1/me/`: Returns authenticated user profile including `email_product_recommendations` and `email_marketing`.
  - `PATCH /api/v1/me/`: Authenticated users can update either or both preferences. Updates are persisted and returned immediately via `UserSerializer`.

## Technical Super Admin Credential Synchronization

- **Single Point of Rotation**: When the Technical Super Admin (`is_superuser=True` or `TECHNICAL_ADMIN_EMAIL`) changes or resets their password via self-service (`/api/v1/auth/reset/`), in-app settings (`/api/v1/password/change/`), or CLI (`manage.py recover_privileged_user`), `server/core/auth_sync.py` automatically synchronizes the new credentials to **Grafana** (via Grafana Admin API `PUT /api/admin/users/1/password`) and notes credential alignment for **MinIO**.
- **Isolation for Business Admins**: Business administrators (`is_business_admin=True`) and staff are explicitly excluded from infrastructure password propagation, changing passwords in the web UI without affecting Grafana or MinIO root credentials.

## USPS Tracking Engine

- `server/payment/usps.py`: USPS service-rate fixtures and official tracking links. Live rates use OAuth carrier adapters in `server/payment/carriers.py`; retired XML APIs and synthetic scans are not used.
- Physical `/api/v1/cart/` responses leave `shipping` null and set `total` to the item subtotal until a customer selects an owned destination and carrier at checkout. Digital-only carts return zero shipping. Checkout quotes are address-based and are the authoritative delivery total.
- Orders dynamically generate live tracking links (`https://tools.usps.com/go/TrackConfirmAction?tLabels=<tracking_number>`).
- Order details and `/api/v1/orders/<id>/tracking/` expose each store's fulfillment and tracking number, so multi-store orders retain separate carrier links and delivery milestones.

## Management commands & data seeding

The repository includes specialized Django management commands for seeding data, generating realistic stress load, and indexing products into Elasticsearch:

| Command | Primary Purpose | Deterministic / Predictable? | Sample Data Size | Rebuilds Elasticsearch? |
| :--- | :--- | :--- | :--- | :--- |
| `populate_fake_data` | **Comprehensive Seeding & Stress Testing** | **Yes** (Guarantees all key role accounts + realistic catalog/orders) | Configurable (`small`, `medium`, `large`, `huge`) | Automatically calls indexer |
| `rebuild_product_index` | **Elasticsearch sync** | N/A (Syncs existing DB records) | Indexes whatever is in the DB | **Core function** |

### 1. `populate_fake_data`
- **File**: `server/core/management/commands/populate_fake_data.py`
- **Purpose**: The authoritative single source for local catalog, transaction history, and account seeding. It always provisions all primary role profiles and realistic catalog datasets.
- **Guaranteed Accounts Created** (using the password passed via `--password`, or `DEFAULT_ADMIN_PASSWORD` from `.env`, defaulting to `ProaceDemo2026!`):
  - **Superuser / Technical Admin**: `admin@proace.local` (Full technical super admin, `is_superuser=True, is_staff=True`, syncs with Grafana/MinIO). **Password Immutability**: Seeding never overwrites, resets, or interferes with the existing password of an existing superuser account (`is_superuser=True`).
  - **Business Admin**: `business-admin@proace.local` (`is_business_admin=True, is_staff=True, is_superuser=False`, platform operator)
  - **Staff Backoffice**: `staff@proace.local` (`is_staff=True, is_superuser=False, is_business_admin=False`, order review & moderation)
  - **Single-store seller**: `seller@proace.local` (Owns store *Apex Athletics*)
  - **Multi-store merchant**: `merchant@proace.local` (Owns stores across seller tier badges)
  - **Shopper / Buyer**: `shopper@proace.local` and `buyer@proace.local`
  - **Moderation accounts**: `pending-seller@proace.local` (unapproved store), `blocked-seller@proace.local` (suspended store), `blocked-staff@proace.local`, `unverified@proace.local`
- **Catalog & Financial Data**:
  - Products with complete specifications schemas, variant matrices, and images.
  - Historical orders across lifecycles (`pending`, `confirmed`, `shipped`, `delivered`, `cancelled`, `refunded`) with carrier tracking.
  - Customer reviews with star ratings and photos.
  - Financial records: customer wallets, 7-day refund hold escrow balances (`in_review`), and cleared payout funds (`cleared_net`).
- **CLI Options**:
  - `--scale medium` (default): Generates ~150 products, ~350 orders, ~65 users, 12 stores.
  - `--scale small`: Generates ~45 products, ~90 orders, ~25 users, 6 stores.
  - `--scale large`: Generates ~500 products, ~1500 orders, ~200 users, 25 stores.
  - `--password <pass>`: Override the dev password for all seeded accounts (defaults to `DEFAULT_ADMIN_PASSWORD` or `ProaceDemo2026!`).
- `--clear`: Deletes commerce records across the database (including stores, products, orders, wallets, and ledgers), then repopulates demo data. Use only for an intentionally disposable development database; it is not limited to fake rows and does not clear Docker volumes.
- `--products <N>`, `--orders <N>`, `--users <N>`: Custom granular counts; all overrides must be positive and at least 11 users are required for guaranteed accounts.
- A seed invocation is one database transaction. If any generation step fails, all rows from that invocation (and any `--clear`) roll back together. Search indexing runs only after the database commit. The command requires at least 11 users so its guaranteed role and edge-case accounts are included.
- Seed output never echoes the supplied or environment-configured password. The password remains available to the operator through the original `--password` value or environment configuration.
- Fake data is refused whenever `DEBUG=False`; there is no production override. Apply schema changes separately with `python manage.py migrate` before starting application processes. Docker API startup applies migrations when `RUN_MIGRATIONS=true`; workers do not independently migrate or bootstrap accounts, and Compose waits for API readiness before starting them.
- **Usage**:
  ```sh
  # Standard seeding (provisions all role profiles + catalog)
  .venv/bin/python server/manage.py populate_fake_data

  # Inside Docker Compose
  docker compose -f server/compose.yaml exec api python manage.py populate_fake_data

  # Large dataset without deleting current records
  .venv/bin/python server/manage.py populate_fake_data --scale large
  ```

Seeded merchant wallets never claim to have connected Stripe payouts. Legacy `acct_mock_*` placeholders are removed by the seeder, and the Connect endpoint discards them before creating a real Stripe Express account.
The large preset counts are per invocation for bulk-created catalog and order records. Running it again appends another batch; it is not a volume-reset operation.

### 2. `rebuild_product_index`
- **File**: `server/product/management/commands/rebuild_product_index.py`
- **Purpose**: Recreates and populates the Elasticsearch product index (`commerce-products`) directly from the PostgreSQL / SQLite database.
- **When to run**:
  - After importing products in bulk via CSV imports or direct SQL migrations.
  - After starting or resetting the Elasticsearch container volume.
  - When modifying search analyzers, autocomplete n-grams, or field weights in `server/product/search.py`.
- **Behavior**: Drops the existing index, recreates analyzer mappings (fuzzy matching, brand/category filters, price aggregations), and iterates through all active published products. Safely bypasses if `ELASTICSEARCH_ENABLED=false`.
- **Usage**:
  ```sh
  # Local Python virtual environment
  .venv/bin/python server/manage.py rebuild_product_index

  # Inside Docker Compose
  docker compose -f server/compose.yaml exec api python manage.py rebuild_product_index
  ```

### 4. Background & Operational Commands

Beyond the catalog seeding tools, the backend includes essential operational commands:

| Command | File | Description & Usage |
| :--- | :--- | :--- |
| `settle_merchant_earnings` | `server/store/management/commands/settle_merchant_earnings.py` | **Financial Escrow Settlement**: Scans merchant ledger sales currently in `in_review` (held during the 7-day customer refund window) and moves funds whose 7-day period has elapsed to `cleared_net` for withdrawal.<br>`python server/manage.py settle_merchant_earnings` |
| `publish_scheduled_products` | `server/store/management/commands/publish_scheduled_products.py` | **Catalog Release Scheduler**: Publishes draft merchant products whose scheduled visibility release date/time has arrived.<br>`python server/manage.py publish_scheduled_products` |
| `recover_privileged_user` | `server/core/management/commands/recover_privileged_user.py` | **Emergency Admin Recovery**: Resets a superuser, staff, or business admin password locally without needing working email delivery. Automatically synchronizes new credentials to MinIO and Grafana.<br>`python server/manage.py recover_privileged_user admin@proace.local --password 'NewPassword123!'` |
| `create_business_admin` | `server/core/management/commands/create_business_admin.py` | **Business Admin Provisioning**: Creates an operational business admin (`is_business_admin=True`, `is_staff=True`, `is_superuser=False`) isolated from technical infrastructure credentials.<br>`BUSINESS_ADMIN_PASSWORD='...' python server/manage.py create_business_admin --email biz@proace.local` |
| `ensure_default_admin` | `server/core/management/commands/ensure_default_admin.py` | **Idempotent Bootstrapper**: Checks environment variables (`DEFAULT_ADMIN_*`, `DEFAULT_STAFF_*`) and creates default admin/staff accounts idempotently if they do not exist.<br>`python server/manage.py ensure_default_admin` |
| `rebuild_notification_index` | `server/notification/management/commands/rebuild_notification_index.py` | **Notification Search Sync**: Rebuilds the Elasticsearch notifications index (`commerce-notifications`) from PostgreSQL records.<br>`python server/manage.py rebuild_notification_index --clean` |
| `consume_logs` | `server/observability/management/commands/consume_logs.py` | **Kafka Log Consumer**: Consumes structured application logs from Kafka topics into the local searchable `LogEntry` audit database.<br>`python server/manage.py consume_logs --group commerce-log-indexer` |

### 5. Pre-Deployment QA, Performance Testing & Bug Audits

All QA reports are stored in `qa-reports/` (strictly untracked by git via `.gitignore`):

- **AI Agent Bug Audits**: When an AI agent performs bug audits or regression investigations, the full audit report is written directly to `qa-reports/bug-audit/`.
- **Pre-Deployment Performance & Security Testing Commands**:

| Command | Script | Target & Report Destination |
| :--- | :--- | :--- |
| `npm run test:load` | `scripts/qa/load_test.py` | Sustained concurrent user browsing, search, and detail requests &rarr; `qa-reports/performance-testing/load/` |
| `npm run test:stress` | `scripts/qa/stress_test.py` | Step-ramp concurrency, instant traffic spikes, race condition lock integrity &rarr; `qa-reports/performance-testing/stress/` |
| `npm run test:volume` | `scripts/qa/volume_test.py` | Deep pagination LIMIT/OFFSET, multi-criteria filtering, payload serialization &rarr; `qa-reports/performance-testing/volume/` |
| `npm run test:security` | `scripts/qa/security_test.py` | Sensitive information leak detection, role boundary isolation, security regression suites &rarr; `qa-reports/security/` |
| `npm run test:qa` | Sequential runner | Runs all four performance and security suites consecutively for full pre-flight verification |

## Search

Public catalog search uses Elasticsearch when `ELASTICSEARCH_ENABLED=true`.
Search covers product title, brand, category, tags and description. Multiword
queries require all terms and search across fields with title/brand/category/tag
relevance weights plus fuzzy matching. Existing Elasticsearch indices receive
the analyzed category/tag mappings when the index is ensured. Product saves and
deletes sync through Django signals on a best-effort basis. Store status or
verification changes reindex that store's products after commit, keeping the
search eligibility fields aligned with moderation state. Existing stale indexes
can be repaired with `python server/manage.py rebuild_product_index`. If
Elasticsearch is disabled or a request fails, the database fallback matches all
query terms across title, brand, category, tags and description.
Queries shorter than three characters use that database substring matcher
directly, since Elasticsearch token matching does not match a one-character
fragment inside an indexed word.

Search files:

- `server/product/search.py`: Elasticsearch client, index mapping, document
  serialization, search query and fallback-safe helpers.
- `server/product/signals.py`: product save/delete hooks.
- `server/product/management/commands/rebuild_product_index.py`: rebuilds the
  product index from the database.
- `server/storefront/views.py`: uses Elasticsearch for the public
  `/api/v1/products/?search=` flow.

## Cache, database and media

- Local container cache uses official Redis at `redis://redis:6379/0`.
- Local container database uses official PostgreSQL at `postgres:5432`.
- Uploads persist in MinIO through the S3 storage backend. The `media-data`
  volume is retained for legacy local data.
- S3-compatible object storage is required for application media; disabling it
  or missing its dependencies fails startup. Offline tests explicitly use
  isolated in-memory storage.

Runtime configuration:

| Variable | Purpose |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | Selects `codematics.storefront_settings` for the integrated app |
| `DJANGO_DEBUG` | Controls debug-only behavior |
| `SECRET_KEY` | Django signing/encryption secret |
| `ALLOWED_HOSTS` | Hostname allowlist |
| `FRONTEND_URL` | Frontend origin used for links and browser flows |
| `DATABASE_ENGINE` | Database selector, currently `postgres` in Compose |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | PostgreSQL credentials |
| `POSTGRES_HOST`, `POSTGRES_PORT` | PostgreSQL connection target |
| `DB_REQUIRE_SSL` | Enables database SSL requirement when supported |
| `REDIS_URL` | Optional Redis URL fallback when `CACHE_URL` is unset |
| `CACHE_URL` | Django Redis cache URL, set to Compose Redis in containers and defaulting to local Redis for host-run Django |
| `OBJECT_STORAGE_ENABLED` | Enables S3-compatible media storage |
| `OBSERVABILITY_TOKEN` | Protects `/metrics/` and detailed health endpoints |
| `ELASTICSEARCH_ENABLED` | Enables Elasticsearch search and health checks |
| `ELASTICSEARCH_URL` | Elasticsearch HTTP endpoint |
| `ELASTICSEARCH_PRODUCTS_INDEX` | Product search index name |
| `FCM_ENABLED` | Enables optional Firebase Cloud Messaging delivery for inbox notifications |
| `FIREBASE_PROJECT_ID` | Firebase project ID used by the Firebase Admin SDK |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to a service-account credential file, supplied outside the repository |
| `CLICKBANK_AFFILIATE_NICKNAME` | ProAce platform affiliate tracking nickname injected into outbound HopLinks (default: `proace`) |
| `CLICKBANK_SECRET_KEY` | Secret passphrase used to verify and decrypt ClickBank Instant Notification Service (INS) webhooks |
| `CLICKBANK_DEV_KEY` | ClickBank Developer API key for marketplace and reporting APIs |

Backend tools added or wired:

- `gunicorn`: production-style WSGI server used by the container.
  `server/gunicorn.conf.py` disables the optional `gunicornc` control socket;
  Docker manages shutdown and restart through signals. HTTP serving is unaffected,
  and no management socket is created on the `/app` host bind mount.
- `psycopg[binary]`: PostgreSQL driver for Django.
- `django-redis`: Redis-backed Django cache.
- `django-storages`: storage abstraction; S3 dependencies live in
  `requirements-storage.txt`.
- `drf-yasg`: Swagger/ReDoc OpenAPI documentation.
- `prometheus-client`: metrics instrumentation.
- `opentelemetry-*`: optional trace export.
- `django-silk`: local-only API profiling.
- `kafka-python`: optional Kafka log publishing and log indexing helpers.
- `elasticsearch`: official Python client for catalog search.
- `firebase-admin`: optional Firebase Cloud Messaging delivery; the server uses
  Application Default Credentials and never stores service-account credentials.

The notification outbox persists email and push deliveries before placing
them on the Celery queue. The worker sends email through the custom Resend
Django email backend and push through FCM, retries transient failures, and
periodically re-enqueues stale work. Set `RESEND_API_KEY` and a
Resend-verified `RESEND_FROM_EMAIL` to send email. Keep
`CELERY_BROKER_URL` identical for the API and worker; local Compose uses Redis
DB 1. Tests explicitly use Django's in-memory email backend and never send
real mail. To enable push, set `FCM_ENABLED=true`, `FIREBASE_PROJECT_ID`, and
Firebase credentials. Apply migrations before deploying and run the
`notification-worker` service alongside the API.

### Transactional HTML Email Templates

All transactional email templates reside in `server/templates/email-templates/` and follow a unified, responsive HTML email standard with Outlook table fallbacks, Inter typography, ProAce brand accents (`#44cf9c`), and regulatory disclaimers:

| Template Name | File Path | Event Trigger & Purpose |
| --- | --- | --- |
| `order-summary` | `server/templates/email-templates/order-summary.html` | Order placement receipt with recorded items and totals; delivery address appears only for orders containing physical items. |
| `order-confirm` | `server/templates/email-templates/order-confirm.html` | Order confirmation notice for confirmed status transitions and itemized checkout receipts. |
| `order-picked-up` | `server/templates/email-templates/order-picked-up.html` | Recorded pickup confirmation when an order is picked up; supports store name and optional pickup location. |
| `delivery-confirmation` | `server/templates/email-templates/delivery-confirmation.html` | Recorded delivery confirmation with available carrier and tracking details; no verification code is generated. |
| `wallet-funded` | `server/templates/email-templates/wallet-funded.html` | Top-up and credit confirmation showing funded amount, updated balance, and marketplace CTA. |
| `refund-request-acknowledged` | `server/templates/email-templates/refund-request-acknowledged.html` | Customer confirmation when a physical return or refund request is submitted (1–2 business day turnaround). |
| `refund-response` | `server/templates/email-templates/refund-response.html` | Staff resolution update (approved/declined) with notes, refund destination, and amount. |
| `onboarding-user` | `server/templates/email-templates/onboarding-user.html` | Customer welcome email with activation and email verification link. |
| `onboarding-staff` | `server/templates/email-templates/onboarding-staff.html` | Backoffice staff welcome and invitation verification guide. |
| `affiliate` | `server/templates/email-templates/affiliate.html` | Partner welcome detailing referral links, HopLinks, commission rules, and affiliate dashboard. |
| `password-reset` | `server/templates/email-templates/password-reset.html` | Secure password reset email with signed, expiring token link. |
| `account-delete-confirmation` | `server/templates/email-templates/account-delete-confirmation.html` | Account closure notice detailing data purge and financial audit archival policies. |

Emails are rendered and enqueued via `server/utils/functions.py:send_mail(file_name, reciever_email, data)` which auto-injects base context (`frontend_url`, `shop_url`, `support_email`) and sets `is_html=True` for multipart delivery.


## Local commands

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.txt
.venv/bin/python server/manage.py migrate --settings=codematics.storefront_settings
.venv/bin/python server/manage.py populate_fake_data --settings=codematics.storefront_settings --password 'ProaceDemo2026!'
.venv/bin/python server/manage.py runserver 127.0.0.1:8000 --settings=codematics.storefront_settings
```

Run backend tests:

```sh
.venv/bin/python server/manage.py test storefront --settings=codematics.storefront_settings --noinput
```

## API documentation

OpenAPI is available locally at:

- YAML schema: `http://127.0.0.1:8000/api/schema/`
- Swagger UI: `http://127.0.0.1:8000/api/docs/`
- ReDoc: `http://127.0.0.1:8000/api/redoc/`

Legacy schema routes also exist under `server/codematics/urls.py`.

Use the generated schema for exact HTTP methods, payloads and per-operation
permissions. The grouped endpoint map is in
[Architecture and API map](architecture.md).

## Documentation maintenance

Update this file when changing Django apps, model ownership rules, serializers,
API responses, permissions, auth, cache/database/media behavior, seed data,
management commands or backend tests.

## Back-office and carrier checkout

See [role matrix, staff activation, and operator setup](access-control.md) and
[multi-carrier API, environment variables, sandbox setup, and fulfillment boundaries](shipping-integrations.md).

## Product weight and user activity

Merchant product validation accepts zero weight for digital listings and normalizes digital stock and weight to zero. Physical listings require weight of at least 0.01 lb on create and update. The staff user-detail endpoint orders notification activity by `timestamp`, exposes it as `created`, and serializes user, wallet, orders and activity through an explicit response schema.

Product updates accept the existing server-generated cover URL, including local media hostnames; new pasted cover URLs still undergo URL validation.

Purchase validation also rejects existing stores without a complete default business address, including digital-only stores. Missing physical shipment origins return a validation error rather than silently using Tampa.

Time handling: Django stores timezone-aware UTC instants (`TIME_ZONE=UTC`, `USE_TZ=True`). Browser date/time inputs display local time and submit ISO UTC timestamps. Dashboard requests accept a validated IANA `time_zone` (UTC by default); the browser supplies its timezone for local calendar-day reporting. Date-only chart labels are preserved without timezone shifts. Cron and carrier request clocks use aware UTC; flash countdowns include minutes.

Military postal delivery: APO/FPO/DPO destinations use USPS only with the currently supported integrations. Checkout disables other carrier options and the server rejects unsupported carriers in both demo and live rating and payment flows. Address city/state/ZIP must agree: AA uses 340xx, AE uses 090xx–098xx, AP uses 962xx–966xx, with country United States. This is a supported-service policy, not a claim that all commercial postal handoff services are prohibited: UPS Ground Saver and Mail Innovations have military-address support but are not integrated here. See [USPS military addressing standards](https://pe.usps.com/text/dmm300/703.htm) and [UPS supported services](https://www.ups.com/us/en/support/shipping-support/print-shipping-labels/how-to-write-address). ZIP blocks alone do not guarantee an active destination or eligibility for every USPS service; live carrier availability and military mail content/customs requirements still apply.

Checkout safety: `payment.CheckoutAttempt` durably tracks wallet reservations, paid-checkout compensation and expiry; `payment.recover_checkout_attempts` runs every minute through Celery Beat. `CartItem.variant` stores the selected option name and checkout locks variant/master stock while using server-calculated prices. Merchant financial summaries use immutable ledger records and preserve negative debt. Buyer downloads stream bytes only for eligible paid-order statuses. See [audit remediation](security-audit-remediation.md), including required migrations and recovery deployment requirements.

## Hybrid Multi-Jurisdiction Tax Calculation Engine

The platform provides a dual-layer destination sales tax engine adhering to the Enterprise Hybrid model (Option C):

1. **Database-Driven Destination Rules (`payment.TaxJurisdiction`)**:
   - Stores granular tax rates with 5 decimal places of precision (`rate = DecimalField(max_digits=7, decimal_places=5)`) to support exact municipal and special district tax rates (e.g. NYC `0.08875`).
   - Supports 5-digit ZIP prefix overrides that take precedence over state-level statutory baselines.
   - Distinct taxability switches: `tax_shipping` (determines whether carrier shipping fees are taxed) and `tax_digital` (determines whether digital goods are taxable or exempt).
   - Inherent state tax exemptions: Explicit active ZIP/state rules take precedence over zero-rate defaults for Alaska, Delaware, Montana, New Hampshire, and Oregon. International deliveries are zero-rated.
2. **Pluggable Stripe Tax Adapter (`server/payment/tax.py`)**:
   - Configured via `TAX_PROVIDER=stripe` and `STRIPE_TAX_ENABLED=true`.
   - Directly integrates with `stripe.tax.Calculation.create` using shipping destination, product lines, and postal details.
   - **Fault-Tolerant Degraded Fallback**: If Stripe Tax experiences an outage, network timeout, rate limit, or invalid credentials, the provider catches the exception, logs a warning, and automatically falls back to `LocalTaxProvider` with zero disruption to checkout.
3. **Comprehensive Audit Snapshots (`Order.tax_snapshot`)**:
   - Every order persists a detailed JSON audit snapshot (`tax_snapshot`) containing `amount`, `rate`, `jurisdiction`, `taxable_merchandise`, `taxable_shipping`, `shipping_tax`, `provider`, `is_exempt`, and `details`.
4. **Seed Automation**:
   - `populate_fake_data` automatically seeds statutory tax rules across all 50 US states + DC via `seed_tax_jurisdictions()`.
5. **Backoffice Administration & API Endpoints**:
   - `/api/v1/admin/taxes/` (`GET`, `POST`): Lists tax jurisdictions with search, state filtering, and status filtering. Allows creating new state rules or 5-digit ZIP overrides.
   - `/api/v1/admin/taxes/<int:pk>/` (`GET`, `PATCH`, `DELETE`): Partial update of rates, taxability flags, active status, or removal of overrides.
   - `/api/v1/admin/taxes/seed-defaults/` (`POST`): Restores or resets default baseline statutory rates for all 50 US states and DC.
   - Django Admin: Registered at `/admin/payment/taxjurisdiction/` with inline rate editing, status filters, and search.

## ClickBank Affiliate Partner Integration

The platform supports hybrid commerce where third-party ClickBank affiliate products coexist cleanly with native merchant listings:

1. **Schema & Models (`server/product/models.py` & `server/affiliates/models.py`)**:
   - `Product.product_type`: Categorized as `'standard'` or `'affiliate_clickbank'`.
   - `Product.affiliate_hoplink`: Validated HTTP/HTTPS vendor HopLink URL.
   - `Product.affiliate_vendor_nickname`: ClickBank vendor nickname identifier.
   - `Product.affiliate_button_text`: Call-to-action button label (e.g. `'Buy on Partner Site'`).
   - `ClickBankOutboundClick`: Records each outbound redirection with foreign keys to `Product` and `User` (or `guest`), tracking token (`tracking_id`), HopLink used, client IP address, and User-Agent.
   - `ClickBankConversion`: Prepares data structures for future webhook or postback attribution matching.
2. **Outbound Redirector Endpoint (`/api/v1/affiliates/clickbank/outbound/<product_id>/`)**:
   - Verifies product existence, published status, and active store status.
   - Open redirect protection: enforces standard HTTP/HTTPS schemes with non-empty netlocs.
   - Generates unique attribution tracking tokens (`cb_user_<nanoid>` or `cb_guest_<nanoid>`).
   - Appends `&tid=<token>` to the target HopLink and records the click event.
   - Issues an HTTP 302 redirect to the external partner destination.
3. **Validation & Checkout Guardrails**:
   - `MerchantProductSerializer`: Enforces non-empty, valid URL HopLinks when `product_type == 'affiliate_clickbank'`. Clears shipping weight/dimensions, locks platform discounts to `0`, clears flash deal timers (`flash_sale_end = None`), and defaults `available = 999` while bypassing variant requirements.
   - `Product.sale_price`: Always returns the vendor reference price (`str(self.price)`) without discounting when `product_type == 'affiliate_clickbank'`.
   - `CouponAdminSerializer`: Rejects creating coupons targeted to ClickBank affiliate items because partner checkouts occur off-platform.
   - Cart addition protection: `CartView.mutate` immediately rejects affiliate items from the shopper cart; the legacy `CartViewSet.add_to_cart` also rejects them.
   - Cron protection: `server/product/cron.py` skips auto-marking affiliate products as "sold out".
4. **Staff Catalog Audit**:
   - `StoreAuditProductSerializer` exposes affiliate metadata and `StaffViewSet.store_products` supports filtering by `product_type=affiliate_clickbank` for compliance oversight.

## Settled-payment accounting and audit remediation

`Order.paid_total` and `wallet_paid` record actual settlement; `refunded_total`, `wallet_refunded_total`, and `card_refunded_total` cap cumulative reversals. Database constraints enforce nonnegative totals and tender consistency. Order placement is distinct from payment: physical COD has no paid balance, earns no payout credit, and cannot unlock digital downloads or receive monetary refunds.

Checkout snapshots persist `line_subtotal`, `discount_amount`, `net_total`, `tax_amount`, and `line_total`. Coupon allocations conserve cents across eligible lines; refunds use final line amounts and earnings use discounted merchandise amounts. Shipping quotes accept the applied coupon so preview and checkout share the tax basis. Local tax snapshots retain exact line taxes; Stripe Tax receives discounted lines and its returned line/shipping taxes are retained when available. Digital-only orders bypass physical quote verification and carrier lookups, always evaluate to `$0.00` Instant Digital Delivery, normalize address to `None`, and generate deterministic quote fingerprints independently of saved customer delivery addresses.

Cancellation, refund creation and approval acquire the same order lock. Claims reserve quantities; approved claims reduce remaining inventory and refundable funds. Refund requests enforce per-product claim idempotency across all statuses (`pending`, `approved`, `declined`, `failed`); products whose refund claims were previously declined or processed cannot be re-submitted for duplicate refunds (`OrderSerializer.claimed_product_ids`), while remaining unclaimed physical items on the order remain eligible for return within the 7-day window. Original-payment split refunds distribute only the remaining wallet/card tender, and card operations use provider idempotency. Provider failures leave the transaction retriable instead of recording fictional refunds. Cancellation also reverses merchant ledgers. The existing seven-day escrow applies only to verified settled sales.

`OrderFulfillment` records status, carrier and tracking per store. Merchant updates permit forward fulfillment transitions only; global completion requires all physical store shipments to finish. Financial statuses use the support/payment workflows. Staff order queries (`/api/v1/admin/staff/orders/`) support filtering by `carrier` / `courier` (matching either the root order carrier or store fulfillments) and include courier names in global search queries.

Order cancellation is guarded in the shared status-transition service as well as the shopper endpoint: instant digital orders cannot be cancelled, and physical orders cannot be cancelled after any store fulfillment has shipped, been delivered, or picked up. Use the refund workflow for post-fulfillment financial adjustments; inventory is never restocked by a cancellation after dispatch.

`WalletFundingAttempt` reserves deposit allowance at session creation. Confirmations lock the user, verify ownership, currency and amount, and credit a unique session receipt once. Paid invalid/over-limit sessions are refunded; failed refunds retain a durable `refund_pending` state. Celery Beat runs `recover_wallet_funding` every 60 seconds to recover paid sessions and expire unpaid sessions at Stripe before releasing allowance.

Apply core migration 0019 and payment migrations 0018–0020 with `python server/manage.py migrate`, then restart the API, Celery workers and Celery Beat to load the new models/tasks. The historical backfill recognizes wallet debit receipts and legacy confirmed Stripe session references. Unverifiable older orders remain unpaid for refund, download and payout eligibility until reconciled. It does not change wallet balances, rewrite immutable tax snapshots, or claw back historical overcredits. Operators must reconcile any previous duplicate refunds or coupon-inflated earnings separately. The canonical seeder explicitly marks its simulated historical payments as wallet settlements.

Generated affiliate links use configured `FRONTEND_URL` and `/api/affiliates/r/<product>/<identifier>/`, matching the same-origin redirect route.

## Transactional HTML Email & Notification Pipeline

The platform dispatches responsive, branded HTML emails through `server/utils/functions.py:send_mail` and `server/notification/delivery.py:queue_email_delivery`. Every template email generates an audited `NotificationDelivery` record (`channel=email`, `is_html=True`) scheduled for asynchronous Celery delivery (`deliver_notification_task`).

### Template Inventory & Canonical Triggers

All email templates reside under `server/templates/email-templates/`:

| Template File | Context / Purpose | Canonical Trigger Point |
| --- | --- | --- |
| `onboarding-user.html` | Welcome email for newly registered shoppers & merchants | `POST /api/v1/auth/register/` (`AuthView.post`) |
| `onboarding-staff.html` | Activation email with secure token link for invited staff | `invite_staff` & `resend_staff_verification` (`core.onboarding`) |
| `password-reset.html` | Password reset link & instructions | `POST /api/v1/auth/forgot/` (`AuthView.post`) |
| `account-delete-confirmation.html` | GDPR / account deletion acknowledgment | `DELETE /api/v1/storefront/me/` (`MeView.delete`) |
| `affiliate.html` | Welcome email for approved affiliate marketers | `POST /api/v1/affiliates/affiliates/register/` (`AffiliatesViewSet.create_marketer`) |
| `order-summary.html` | Order confirmation with itemized receipt & tax breakdown | `POST /api/v1/storefront/orders/checkout/` (`CheckoutView._complete`) |
| `order-confirm.html` | Order confirmation & review receipt | `STATUS_CONFIRMED` transition (`ProductOrderTrackingView` & `transition_order_status`) |
| `order-shipped.html` | Shipping notification with carrier, tracking number & URL | `STATUS_SHIPPED` transition (`ProductOrderTrackingView` & `execute_order_status_transition`) |
| `order-picked-up.html` | Order picked up confirmation & receipt review | `STATUS_PICKED_UP` transition (`ProductOrderTrackingView` & `transition_order_status`) |
| `delivery-confirmation.html` | Delivery confirmation & receipt | `STATUS_DELIVERED` transition (`execute_order_status_transition`) |
| `order-cancelled.html` | Cancellation notice with wallet/card refund breakdown | `STATUS_CANCELLED` transition (`execute_order_status_transition`) |
| `refund-request-acknowledged.html` | Return/refund claim acknowledgment | `POST /api/v1/storefront/orders/refund/` (`OrderRefundView.post`) |
| `refund-response.html` | Refund decision notice (Approved/Declined with reason) | `process_order_refund` & `decline_order_refund` (`payment.services`) |
| `wallet-funded.html` | Wallet top-up confirmation receipt | `payment.confirm_wallet_funding_session` (`stripe_webhook`) |
| `payout-processed.html` | Merchant payout status notice (Approved/Rejected) | `POST /api/v1/staff/payouts/<pk>/process/` (`StaffViewSet.process_payout`) |
| `store-status.html` | Store verification, blocking reason and restoration | Store review and backoffice moderation |
| `account-security.html` | Account access changes and password change/reset confirmations | Administrative access endpoints and password flows |
| `inventory-low.html` | Physical stock threshold and out-of-stock alerts | Inventory signals; owner and authorized operators |
| `service-notification-base.html` | Shared responsive service notification layout | Inherited by store, security and inventory templates |

### Template Conventions & Safety

- **Default Context Injections**: `send_mail` automatically supplies safe defaults for `frontend_url`, `shop_url`, `dashboard_url`, `order_url`, `support_email`, and `absolute_url`.
- **Recipient Correlation**: `send_mail` automatically matches the destination email to the corresponding `core.User` foreign key when available, guaranteeing audit traceability in `NotificationDelivery.recipient`.
- **Typo & Legacy Aliases**: The legacy template path `refund-request-acknowleged` is retained as an alias to `refund-request-acknowledged.html`. The aliases `order-pickup.html` and `order-confirmation.html` route directly to `order-picked-up.html` and `order-confirm.html` respectively for backward compatibility.


Transactional service emails cover store verification, blocking (including the review reason), and restoration; administrative account suspension/restoration and backoffice permission changes; successful password changes/resets; and low physical stock for the store owner and authorized operators. Store, account-security, and inventory notices use branded HTML templates through the existing delivery outbox. No-op moderation/access requests do not resend notices. When a dedicated receipt is sent for checkout, shipment/delivery, refund decisions, cancellation, wallet top-ups, or payout decisions, the companion inbox notification suppresses its generic email while retaining inbox and push delivery. Delivery requires the configured email provider and notification worker; local console delivery does not send real email.

Inbox notifications and their email/push outbox rows are persisted in one database transaction. Worker dispatch waits until commit, so rollback removes both and broker outages leave persisted deliveries available for recovery.

Invalid, expired, or blacklisted refresh tokens return a structured HTTP 401 (`token_not_valid`) from `/api/v1/auth/refresh/`, allowing the browser proxy to clear revoked sessions and continue public browsing anonymously.

Email receipts display actual order snapshot and recipient data. Missing personal details are omitted; digital-only orders omit delivery address sections and physical-shipment language. Delivery notices report recorded status and never include sample verification codes, names, addresses, phone numbers, carrier values, or product photos.

The catalog supports 29 departments shared by homepage category tiles, shop/store filters, and merchant product forms: Electronics, Fashion, Phones, Computing, Sports & outdoors, Books, Toys & games, Kids & baby, Home & living, Kitchen & dining, Beauty & personal care, Health & wellness, Pet supplies, Gaming, Tablets, Fishing, Lingerie & sleepwear, Coffee, tea & drinks, Garden & tools, Automotive, Jewelry & watches, Software & apps, Courses & learning, Templates & planners, Design assets, Photos & video, Music & audio, Business resources, Digital tools & presets. New department keys are validated by Django product choices; apply product migrations before using them. Existing product category keys are preserved.

Staff user detail accepts validated `order_search`, `order_status`, `order_carrier`, `order_payment`, `order_ordering`, and `order_offset` parameters. Orders remain scoped to the selected user; `order_count` counts matching rows, while `total_orders` and `lifetime_spent` cover all placed orders (spend excludes cancellations). Order pages contain up to 15 rows.

Backoffice coupon attribution displays the recorded creator’s email. Coupon creation assigns the authenticated staff/admin server-side; records without a creator show “Not recorded” rather than an assumed staff identity.

Digital catalog categories: `software`, `courses`, `templates`, `design_assets`, `photo_video`, `music_audio`, `business`, and `digital_tools` supplement existing departments such as Books and Gaming. Merchant product validation and category filtering accept these keys. Apply product migration `0014_digital_product_categories`; existing category values and digital fulfillment rules are unchanged.


Listing filtering remediation (2026-10-10): payout approvals, merchant payouts and earnings, customer orders/wallet, treasury withdrawals, user/staff management and profile wallet histories now filter before server pagination with matching counts. Finance criteria combine reference search, status/type/method, inclusive UTC date ranges and amount bounds; balances and lifetime totals remain independent of listing filters. Catalog controls expose category, physical/digital and standard/partner types, stock and visibility as applicable. Coupons support type, validity and creator email; stores support official/merchant and creation dates. Saved products filter the complete saved collection before pagination. Notifications support independent read/archive state and category. Search is debounced by 300 ms, criteria changes return to the first page, and reset controls clear active criteria. Invalid financial bounds and pagination return HTTP 400; existing user/store access scopes remain authoritative.


The [notification audit of 11 October 2026](notification-audit-2026-10-11.md) traces order `uuEl5iwv6QMVG`, records reproduced store-filter visibility and duplicate merchant notices, and defines the proposed recipient/channel matrix and remaining delivery/remediation work. Audit findings are not implemented fixes; local console email and disabled FCM do not verify external delivery.


Notification remediation (11 October 2026): one canonical event identity per recipient, recipient-scoped multi-store associations, canonical categories and archived/list filters, selected-store refund reviewer routing, treasury/affiliate/review coverage, transactional inbox/outbox writes, credential outbox delivery, stable email/push queue keys and provider idempotency, shared SSE/FCM toast deduplication, and numeric order-detail links. Apply notification migrations before using the updated API and restart API, notification-worker and celery-beat together. Migration backfills do not send messages; duplicate legacy order-created notices are archived rather than deleted. Local test mode intentionally retains console email and disabled FCM; external provider delivery has not been verified. See the notification audit for channel policy and regression coverage.

Transactional email contacts use `SUPPORT_EMAIL` (default `admin@proaceintl.com`) and `ORDER_SUPPORT_EMAIL` (default `productace@proaceintl.com`), matching the storefront contacts. Sender identity uses `RESEND_FROM_EMAIL` separately. Order/refund replies go to order support; other replies go to general support. Missing contacts omit their labeled template rows.

Push delivery retries intersect any saved failed-token list with the recipient's currently registered push devices before sending. Unregistered tokens and tokens reassigned after account switching are excluded from retries, preventing an older account's notification from reaching a device now registered to another account.

The referral workspace at `/account/affiliates` supports enrollment, copyable `/register?ref=…` invite links, credited-signup progress, and searchable/filterable paginated referral history. Registration accepts an invite code visibly in an optional field; rewards are issued only after email verification. The server grants $25 non-withdrawable ProAce Wallet credit for up to four referred signups; additional referrals remain pending without credit, and reward issuance is serialized per affiliate to enforce the cap under concurrent signups. The displayed earned total is cumulative promotional credit, not a cash balance or ClickBank commission. `/admin/affiliates` lets backoffice operators search/filter enrolled affiliates and review referral totals, credit earned, and account status, with links to existing user management. Customer history omits referred users’ personal information; affiliate account, wallet, and referral routes reject backoffice accounts. Generated links can only target published products in active, verified stores and stop redirecting if a listing becomes unavailable. API endpoints: `/api/v1/affiliates/workspace/` (owner-scoped), `/api/v1/affiliates/referrals/` (owner-scoped, paginated), and `/api/v1/admin/affiliates/` (backoffice-only).

Digital product onboarding & variant enhancements:
- **Redundant Cover Photo Elimination & Auto-Cover**: For digital image products (artwork, wallpapers, photography), uploading a digital file automatically populates `product.image_url` if no custom cover was specified, removing redundant cover uploads. Custom promotional banners remain optional.
- **Automatic Preview Watermark Protection**: Digital image files default `digital_preview_watermark = True` to protect artwork on public storefronts with the `PROACE PREVIEW` overlay. Non-image files (PDFs, ZIPs) coerce watermark to `False`. The raw unwatermarked file is securely served only after authorized purchase via `/api/v1/orders/<id>/download/`.
- **Digital Product Options & Variants**: Digital products support options/variants (e.g., 4K Wallpaper, Mobile HD, Print-Ready Vector) with unlimited digital inventory, variant-specific prices/deltas, and gallery image mappings without physical inventory deduction during checkout.



### Performance benchmark validation

Catalog responses load specifications in the product query and aggregate seller earnings once per response. This keeps catalog database query counts bounded as product and store counts grow, while retaining current tiers, ownership checks, and the existing 24-item page contract.

Performance runners discover real product IDs, categories, and populated page counts from the target API. Load tests default to 60 seconds and record HTTP status distributions, empty-response coverage, and successful-only latency. Stress verdicts require ramp p95 below 450 ms and error rates below 1%; spike thresholds and catalog recovery are evaluated from measurements. Volume reports include every sample's status and result count and mark insufficient dataset/deep-page coverage as INCOMPLETE. API timings do not establish browser rendering, image performance, query plans, or index utilization. Exit codes are 0 for PASS, 1 for FAIL, and 2 for INCOMPLETE; discovery failure also exits unsuccessfully.

Run the same workload through the same-origin frontend proxy:

```bash
PERFORMANCE_API_PREFIX=/api npm run test:load -- --url http://127.0.0.1:3000
PERFORMANCE_API_PREFIX=/api npm run test:volume -- --url http://127.0.0.1:3000
```

The inventory check uses 20 separate buyers making real checkout requests against five units in a uniquely named PostgreSQL test database. It asserts five successful orders, fifteen stock rejections, and zero remaining stock. It never uses live commerce carts or products. The runner also stubs realtime publishing so fixture user IDs cannot emit events to live Redis inbox channels; email delivery uses the test memory backend. The database is created and removed by Django's test runner. Run it through the existing API container:

```bash
.venv/bin/python scripts/qa/inventory_check.py
INVENTORY_TEST_JUNIT=qa-reports/performance-testing/stress/inventory-check-<timestamp>.xml npm run test:stress
.venv/bin/pytest scripts/qa/test_performance_reports.py
```

The stress runner accepts only a completed matching inventory test case from a JUnit artifact less than one hour old. Missing or skipped inventory evidence yields INCOMPLETE when performance otherwise passes. SQLite offline runs skip the PostgreSQL contention test explicitly.


Catalog review counts use a scalar subquery so page totals do not group the full catalog. Worker-count tuning must be benchmarked against the actual deployment: increasing local processes did not improve tail latency in this environment. The two-process, 32-thread default is retained, overridable with `GUNICORN_THREADS`. A local eight-thread trial improved the anonymous benchmark during memory pressure, but lowers total request slots from 64 to 16. Live notification streams occupy those slots, so that trial is not sufficient evidence to lower the application-wide default. Rebenchmark process/thread limits with notification streams and carrier I/O on the actual deployment.

Anonymous catalog pages use a short-lived Redis-backed shared snapshot (`PUBLIC_CATALOG_CACHE_SECONDS=15`, range 0–60; 0 disables). Runtime Django cache is Redis-only; local development defaults to `redis://127.0.0.1:6379/0`, containers use Compose Redis, and cache connection failures surface instead of silently falling back to uncached catalog responses. Warm snapshots perform two lightweight database checks instead of fetching and serializing the model graph. Every hit rechecks current product visibility, active/verified store status, ownership, price, discount, stock and variants. Model, image, specification, review, tag and earnings changes invalidate after commit, with store timestamps covering missed Redis invalidations. Earnings-related timestamps update after commit to avoid adding Store row locks to financial transactions. Authenticated, transactional and search requests bypass snapshots; checkout retains authoritative database validation. Bulk changes that skip model signals and explicit invalidation can leave metadata, page membership and totals stale until the bounded TTL; use model saves or `invalidate_product_cache()` for such writes. Load reports record HIT/MISS/BYPASS counts and describe their mixed warm/uncached workload.

Repeated empty catalog-filter pages are cached independently, and the Redis warm lock remains held until the background warm finishes. Product, image, tag, and store-visibility model changes clear the legacy product response cache after commit. Elasticsearch product indexing and deletion run as Celery tasks after commit so external search requests do not hold up merchant writes; search results may reflect a recent edit after the worker processes its queue.

Cached landing and product payloads prefetch images and tags and aggregate wishlist counts in the product query. Serializer methods use an annotated count without evaluating an unnecessary per-product fallback query.

USPS live rating uses HTTPX async I/O with one bounded three-connection pool: authenticate once, then request Ground Advantage, Priority Mail and Priority Mail Express concurrently. Failure cancels sibling requests before closing the pool and returns a sanitized shipping error without invented rates. Other carriers retain their existing adapters. Tests use mock transports; live carrier latency and credentials are not established by these tests.

The API runs two Gunicorn processes with 32 request threads each by default. Async USPS calls are bridged into the synchronous request stack; the request thread waits while network operations overlap. Celery already runs background work in separate processes. Async is appropriate for independent network waits; CPU-heavy work needs process workers, and checkout/payment/inventory transactions stay synchronous and atomic. A full ASGI migration would also require async-compatible middleware/authentication, native async I/O, database connection-pooling review, and benchmarks; merely changing `def` to `async def` does not provide that migration. See [Django async guidance](https://docs.djangoproject.com/en/5.2/topics/async/) and [HTTPX async clients](https://www.python-httpx.org/async/).

Elasticsearch search reuses one thread-safe client and its persistent connection pool per process instead of creating a client for every request. Forked workers reset the inherited client and lock; configuration changes replace the local pool. Search still queries Elasticsearch for current IDs/counts and retains the existing database fallback. This is connection reuse, not caching search results or an ASGI migration. See [the official Python client's connection/thread guarantees](https://github.com/elastic/elasticsearch-py).

Merchant payout processing is available to authenticated backoffice staff and administrators through `/api/v1/admin/staff/payouts/<id>/process/`. Customer accounts remain excluded. Requests may be processed only once; every request must include an explicit `approve` or `reject` action, and rejection requires an audit reason. Stripe Connect approval sends a transfer while bank-transfer approval records external payment completion. Refund decisions likewise require an explicit `approve` or `decline` action and a reason; missing or invalid decisions leave the pending record unchanged.

Platform Treasury withdrawal requests are reservations, not automatic transfers. Superusers and business administrators resolve them through `/api/v1/admin/staff/commission-wallet/withdrawals/<id>/process/`; completion requires a note confirming the external transfer, while failure requires a reason and releases the reserved amount. Store-scoped merchant payouts are revalidated against that store's cleared funds under the wallet lock. The unified wallet payout endpoint uses combined funds unless a `store_id` is explicitly supplied.

Email backend selection: use `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` for normal local development; use `EMAIL_BACKEND=notification.email_backend.ResendEmailBackend` for production or temporary local delivery testing. An explicit console backend overrides a configured Resend key. See [local and production email setup](getting-started.md#email-backend-local-development-and-resend-testing) for verified sender requirements, recreating services after environment changes, and returning to console mode.

For effective API/worker backend checks and retry interpretation, see [notification worker settings](getting-started.md#notification-worker-settings-and-troubleshooting). Follow the [production transition](deployment.md#transitioning-notifications-from-local-to-production) to refresh all delivery processes, start the scheduler and avoid carrying a local console backend into production.

Social signup imports a missing Google profile image from the verified credential into configured media storage (MinIO/S3 when enabled), preserving user-selected avatars. When tokeninfo omits the picture, the accepted ID token supplies that claim after provider verification. Google/Apple sign-in with an empty phone number prompts for a phone number and saves it through the authenticated profile endpoint before continuing; existing phones are preserved. Referral codes from the signup field, URL or remembered auth-page referral remain attached to new social signups only; existing-account logins do not create or reassign referrals. A missing Google image or unavailable image service does not block authentication and is retried on the next sign-in while the avatar remains empty.

Customers can manage Google/Apple connections and password sign-in in profile/settings. Provider subjects resolve to a single account, verified matching emails link existing customer profiles, and disconnect preserves at least one login method. See [social account linking](social-account-linking.md) for the schema, authenticated API routes, legacy account migration, security rules and frontend flow.

Settings use compact expandable sections for appearance, optional email preferences and sign-in methods. Authentication pages remain viewable while signed in, with email/password above horizontal Google/Apple alternatives. Sign-in and registration controls are disabled during session loading or an active session; an explicit sign-out action permits account switching. The backend rejects login, registration and public social sign-in attempts carrying a valid current session with HTTP 409, while expired/revoked credentials can recover through normal sign-in. Existing authentication throttling remains active. Password recovery and authenticated provider linking remain available.

Bank account list requests return both default and non-default accounts when `is_default` is omitted. The default-account filter is applied only when explicitly supplied; switching a default remains visible after list refresh.

Payout account actions prevent overlapping mutations and report successful default/deletion changes. Pickers discard selections that disappear from refreshed account lists. Unified merchant payout history applies search, status, method, date and amount criteria before pagination, with deterministic creation/ID ordering.

Merchant bank-transfer payout requests require an owner-scoped saved bank account or legacy bank-name/account-number details before reserving funds. Bank account IDs are rejected for other payout methods.

Merchant escrow settlement locks ledger rows explicitly (`FOR UPDATE OF self`) so nullable order joins work on PostgreSQL; wallet balances remain protected by separate row locks. The API and Celery consumers must be refreshed when this shared service changes.

Store dashboards expose `withdrawable_balance`, capped by both the store’s cleared funds and the unified wallet after pending/completed payouts. Merchant payout controls use that amount. Repeated fake-data seeding preserves existing payout debits and does not generate another automated demo payout for the same wallet.


### Notification record navigation

Notification actions use recipient-scoped destinations and contextual labels for orders,
refunds, payouts, stores, wallet, referrals, and account notices. Admin orders/refunds/payouts
and merchant payouts/earnings consume `order`, `refund`, `payout`, or `ledger` query IDs to
open their existing detail dialogs. Buyer orders retain their dedicated detail page;
stores/accounts/wallet/referrals open their existing relevant page. Closing a notification
dialog clears its record query parameter. Unavailable records show a clean access/unavailable
message and leave the listing usable.

Dialog resolution uses a separate, user-keyed request with `record_id`, `limit=1`, and
`offset=0`, independent of listing search, filters, and pagination. `record_id` is a positive
integer accepted by shared filtered listing endpoints and admin order/refund listings;
existing endpoint permissions and tenant ownership still apply. Saved notification payloads
are resolved through the current routing policy when serialized and when push is dispatched,
so legacy list-only URLs do not require database reseeding or a notification resend.


### Backoffice store order history

`/admin/stores/<id>` includes a Store orders section with independent debounced
search, status/carrier/payment filters, sorting, reset, counts, pagination and the
existing order detail dialog. The shared admin order endpoint accepts a positive
`store_id` and filters before pagination. Immutable item snapshots define store
membership, with fulfillment associations and an empty-snapshot legacy cart fallback.
Mixed orders appear for each participating store; displayed totals and emergency
status actions apply to the complete customer order, as labeled. Migration
`payment.0021_order_items_store_gin` adds a PostgreSQL GIN index for snapshot store
membership (SQLite uses its test-compatible index implementation). Existing backoffice
permissions apply; this does not grant access to third-party merchant dashboards.


### Backoffice store payments

Admin store detail pages include store financial totals, payout history and an earnings
ledger with detail dialogs. The summary uses the existing store financial calculation;
filters apply to histories independently of the all-time summary. Each history has its
own debounced search, status/type/method/date/amount filters, reset, count and pagination.
`GET /api/v1/admin/staff/stores/<id>/financials/` returns the typed financial summary;
`GET /api/v1/admin/staff/stores/<id>/ledger/` returns filtered, paginated store ledger
entries. The existing `/api/v1/admin/staff/payouts/?store_id=<id>` endpoint scopes payout
history to that store before filtering and pagination. Unallocated merchant-wallet payouts
are not attributed to individual stores. These endpoints retain backoffice permissions
and do not grant merchant-dashboard access or submit financial transactions.
Backoffice refund listings (overview and full history) and refund detail dialogs show the processing staff or administrator's email under “Processed by” after an action. Attribution comes from the backend's recorded refund processor; pending or older records without a processor show no invented identity. This field is exposed only through the existing backoffice refund serializer and access controls.
App-wide audit fixes (2026-10-15): merchant order history resolves recorded snapshot/fulfillment membership, with live-cart fallback for legacy records. Merchant shipment events are store-scoped; delivery addresses appear only for that store's physical items. Digital download links include an encoded `variant` selector when required and resolve only purchased order lines; legacy single-item links remain supported. Guest physical carts display “Calculated at checkout” and keep totals limited to item costs until the backend quotes delivery. Failed refund attempts retain the operator email, timestamp and reason, while customer/backoffice payloads use safe failure text, including for older failed records. Malformed password-reset identifiers return validation errors. The security runner requires expected live response statuses, uses the current protected routes, treats unreachable probes as failures and exits nonzero on failure. Run `.venv/bin/pytest scripts/qa/test_security_reports.py` for offline runner regressions in addition to the standard test suites.
The security runner, its offline regression tests and shared report helper are explicitly exempted from the local `scripts/` ignore rule so their fixes can be versioned; generated `qa-reports/` output remains ignored.
Order-list performance: customer history/detail batch-load related refunds and store fulfillments; merchant history loads store fulfillments once per page and prefetches cart items only for legacy orders without snapshots. Each request reads fresh authorized data; no cross-request private response cache is added. Query-growth regression coverage is documented in [performance.md](performance.md).

## Catalog request diagnostics

Catalog pages now sort/page narrow IDs, then hydrate only the selected current product graphs. Created/ID and category/created/ID indexes are provided by migration `product.0015`. Public miss coalescing has a two-second lease and bounded 200 ms follower wait, with live payload revalidation and no stale-data fallback. Image URL memoization is per response only. Elasticsearch uses a configurable bounded per-process pool (default 32), preserving fuzzy relevance and rejecting partial results into the existing SQL fallback.

`codematics.stream_settings` reuses normal authentication/security settings with a restricted SSE/health URLconf for the internal `notification-stream` Compose service. It runs no migrations or commerce routes; existing per-user Redis channel selection and live credential/access checks remain unchanged. Dedicated stream connections use `CONN_MAX_AGE=0`, returning sockets after access checks and before Redis waits to a bounded PostgreSQL pool (maximum four physical connections per process; three-second acquisition timeout). Its image additionally installs `requirements-stream.txt`; ordinary API images do not. See [performance](performance.md) for pool budgets and finite WSGI capacity.

Catalog search requests record request-local `search`, `hydrate` and `serialize` stage durations in internal structured logs. Public snapshot reads record `catalog_cache`; safe aggregate `Server-Timing` and generated `X-Request-ID` headers support correlation through the frontend proxy. No query text or business payload is included in stage diagnostics.

Anonymous, nontransactional searches use Elasticsearch's refresh-invalidated shard request cache when `SEARCH_REQUEST_CACHE_ENABLED=true` (default). Only IDs/counts are retrieved (`_source` is disabled), then current product records are hydrated and filtered from PostgreSQL. Fuzzy relevance, pagination and total-hit counting are unchanged. Authenticated/transactional searches do not opt in. See [performance](performance.md) for consistency boundaries and controlled worker trials.


Signed-out visitors to `/orders/<id>` are redirected to `/login?next=...` after the
session check, then returned to that order after authentication. A signed-in viewer
without access sees an unavailable-order message with Your orders and an explicit
Switch account action. Switching uses normal logout before opening sign-in and retains
the order return path. Missing and inaccessible orders share the same safe 404 response;
no owner identity is revealed. Expired-session 401s return to sign-in, while other order
loading failures show a generic retry message without exposing backend internals.
