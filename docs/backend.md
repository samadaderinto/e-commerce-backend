# Backend documentation

## Lifecycle tracking

`User.updated` records profile/credential changes, while JWT sign-in updates `last_login`. Authenticated requests update `last_active_at` for the user and owned/assigned stores at most once every five minutes; activity writes do not change profile/catalog revision times. Existing device records matching the authenticated user and direct request IP receive the sign-in timestamp. Guest browsing is not assigned to a user.

Product detail visits refresh `Recent.updated` under a user row lock. Cart additions, quantity changes, and removals touch `Cart.updated`. Product, image, specification, and store-profile/address revisions touch `Store.updated`. Product serializers expose both creation and revision timestamps as read-only metadata.

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

Mutating browser flows require same-origin behavior through the proxy. Direct API
clients can use bearer tokens and the OpenAPI docs.

## Product and seller flow

Sellers create a store and pickup address, then create drafts, upload images,
publish products, update pricing/stock/specifications and review seller-specific
orders. Store moderation can block publishing. Product creation and update logic
validates owner, store state, price and stock server-side.

### Seller Tier Ranks & Milestone Verification
Stores automatically earn tier rankings based on cumulative gross sales, dynamically resolved by `calculate_store_tier()` in `server/store/services.py`:
- **Starter** ($0 – $999): Blue checkmark badge (`#2563eb`).
- **Booster** ($1,000 – $4,999): Silver badge (`#94a3b8`).
- **Accelerator** ($5,000 – $49,999): Purple badge (`#8b5cf6`).
- **Power Seller** ($50,000 – $499,999): Emerald badge (`#059669`).
- **Mega Seller** ($500,000 – $999,999): Diamond badge (`#0ea5e9`).
- **Legendary Seller** ($1,000,000+): Gold Crown badge (`#d97706`).
- **Official Brand Store**: Dedicated Golden Tick (`#eab308`).

### Product Variants, Specifications & Flash Sales
- **Product Specifications (`Product.specifications`)**: Nested technical specifications dictionary exposing dimensions (`height`, `width`, `breadth`, `weight`), `color`, `serial` / part number, and `attributes` string. Specifications and physical dimensions are physical-only; digital downloads and ClickBank partner offers disallow them.
- **Product Variants (`Product.variants`)**: JSON-based array storing option names (e.g. Size, Color), price deltas (`price_delta`), and dedicated stock allocation (`available`).
- **Flash Deals (`Product.flash_sale_end`)**: Optional expiration timestamp powering urgency badges and live countdown timers across storefronts.
- **Store Announcements (`StoreInfo.announcement`)**: Marquee banner text displayed on the public store showcase page.
- **Verified Buyer Reviews & Moderation**: Restricts review posting to verified purchasers with up to 3 attached photo URLs. Reviews expose `can_moderate` and can be deleted by authors, store owners, and staff via `DELETE /api/v1/products/<pk>/reviews/?review_id=<id>`.
- **Digital Image Watermarking (`Product.digital_preview_watermark`)**: Digital goods support high-resolution image asset downloads (PNG, JPG, WebP, SVG). The buyer preview watermark overlay (`PROACE PREVIEW`) is guarded and enabled exclusively for digital image assets; non-image digital files (PDF e-books, audio MP3s, software ZIPs) disable the option and normalize `digital_preview_watermark=False` both client-side and server-side.

### Merchant escrow and payouts
- **Platform Commission (4%)**: Automatically items and deducts a 4% platform fee (`PLATFORM_FEE_PERCENT = 4.00`) from gross item sales.
- **7-Day Review Escrow**: Net sales from customer orders placed within the 7-day refund window (`REFUND_WINDOW_DAYS = 7`) are held in `in_review` status.
- **Cleared Balance**: Once orders surpass the 7-day refund deadline, funds unlock to `cleared_net` and become available for merchant withdrawal requests via `/api/v1/stores/<id>/payouts/`.
- **Admin Payout Processing**: Backoffice staff review and process withdrawal requests via `/api/v1/admin/staff/payouts/` with approve/reject actions and audit notes.
- **Fulfillment & Carrier Tracking**: Merchants update carrier, tracking number, and milestone descriptions on store orders via `/api/v1/stores/<id>/orders/<order_id>/tracking/`, which triggers customer notifications and provides live tracking links.

## ProAce User Wallet, Order Cancellation, and 7-day refunds

- **Customer Wallet (`/api/v1/wallet/`)**: Every registered customer has an integrated store balance for instant 1-click checkout purchases and instant store credit refund resolution.
- **Wallet Top-Up (`/api/v1/wallet/topup-session/`, `/wallet/topup-confirm/`)**: Customers can top up their wallet balance with preset ($25, $50, $100, $250, $500) or custom ($5–$25,000) amounts, subject to $50,000 daily and $100,000 monthly limits including outstanding reservations.
- **Split-Tender Payments**: Customers can combine available wallet balances with Stripe payments during checkout, deducting the wallet credit from the card charge.
- **Order Cancellation (`/api/v1/orders/<id>/cancel/`)**: Customers can cancel orders in `pending` or `confirmed` status. Cancellation locks the order, restocks remaining physical product/variant quantities once, closes pending refund claims, reverses merchant earnings, and refunds only the remaining settled funds. Wallet tender returns as `SOURCE_REFUND`; Stripe tender returns to its original payment method. Unpaid COD orders receive no credit. Cancellation is blocked after any store starts fulfillment.
- **7-Day Refund Policy (`/api/v1/orders/<id>/refund/`)**: Customers can request refunds for physical items within 7 days of order placement. Refund destinations can be selected as ProAce Store Credit (instant wallet credit upon admin approval) or original payment method. Digital goods are non-refundable once delivered.
  - **Duplicate Prevention & Pending Edits**: Duplicate refund requests for the same order are strictly rejected while an active refund is pending review or after full payment settlement. Customers can retrieve (`GET`) and edit (`PATCH`/`PUT`) their existing pending request (reasons, refund destination, selected items) before staff moderation.
  - **Order Serialization Integration**: `GET /api/v1/orders/<id>/` exposes `active_refund` metadata (`id`, `status`, `is_pending`, `reason`, `refund_type`, `refund_amount`, `product_ids`, `failure_reason`, timestamps) directly to the customer storefront.
- **Coupon Lifecycle & Audit Preservation (`/api/v1/admin/staff/coupons/<id>/`)**: Unused coupons (`num_used == 0` and zero redemptions) can be permanently deleted by backoffice staff. Coupons with recorded customer redemption history (`num_used > 0` or redemptions present) cannot be deleted to preserve order records, receipts, and financial audit trails; they must remain deactivated.

### User Profile Avatar & Media Storage
- **Avatar Storage (`User.avatar_image`, `User.avatar_url`)**: Authenticated users across all roles (customers, merchants, staff, superadmins) can upload a personal avatar. Media files are uploaded to `user-profiles/avatars/` in MinIO/media storage.
- **Image Specifications & Validation**: Uploads are validated server-side by `UserAvatarImageSerializer` for exact 512x512 resolution, JPEG/PNG/WebP formats, and a 5MB maximum file size.
- **Endpoints**:
  - `POST /api/v1/me/avatar/`: Authenticated user uploads an avatar image via multipart form data (`avatar_image`).
  - `DELETE /api/v1/me/avatar/`: Authenticated user deletes their avatar, cleaning up the storage file and setting `avatar_image` and `avatar_url` to null.
  - `GET /api/v1/users/<pk>/public/images/avatar/`: Public proxy endpoint serving the user avatar with Cache-Control headers and 404 fallback.
- **Serializer Integration**: `UserSerializer` and `StaffSerializer` dynamically generate the proxy URL `/api/users/<pk>/public/images/avatar?v=<timestamp>` to prevent stale browser cache while isolating backend origins.

## Technical Super Admin Credential Synchronization

- **Single Point of Rotation**: When the Technical Super Admin (`is_superuser=True` or `TECHNICAL_ADMIN_EMAIL`) changes or resets their password via self-service (`/api/v1/auth/reset/`), in-app settings (`/api/v1/password/change/`), or CLI (`manage.py recover_privileged_user`), `server/core/auth_sync.py` automatically synchronizes the new credentials to **Grafana** (via Grafana Admin API `PUT /api/admin/users/1/password`) and notes credential alignment for **MinIO**.
- **Isolation for Business Admins**: Business administrators (`is_business_admin=True`) and staff are explicitly excluded from infrastructure password propagation, changing passwords in the web UI without affecting Grafana or MinIO root credentials.

## USPS Tracking Engine

- `server/payment/usps.py`: Development cart estimates and official tracking links. Live rates use OAuth carrier adapters in `server/payment/carriers.py`; retired XML APIs and synthetic scans are not used.
- Orders dynamically generate live tracking links (`https://tools.usps.com/go/TrackConfirmAction?tLabels=<tracking_number>`).
- Recorded fulfillment milestones are queryable by customers, merchants, staff, and superusers via `/api/v1/orders/<id>/tracking/`.

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
  - **Superuser / Technical Admin**: `admin@proace.local` (Full technical super admin, `is_superuser=True, is_staff=True`, syncs with Grafana/MinIO)
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
  - `--clear`: Wipes existing fake catalog and orders before populating.
  - `--products <N>`, `--orders <N>`, `--users <N>`: Custom granular counts.
- **Usage**:
  ```sh
  # Standard seeding (provisions all role profiles + catalog)
  .venv/bin/python server/manage.py populate_fake_data

  # Inside Docker Compose
  docker compose -f server/compose.yaml exec api python manage.py populate_fake_data

  # Clean wipe with custom product/order counts
  .venv/bin/python server/manage.py populate_fake_data --clear --products 200 --orders 500
  ```

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

## Search

Public catalog search uses Elasticsearch when `ELASTICSEARCH_ENABLED=true`.
Product saves and deletes sync to Elasticsearch through Django signals on a
best-effort basis. If Elasticsearch is disabled or a search request fails, the
catalog falls back to database `icontains` filtering for title, brand and
description. Multi-match queries apply field weights (`title^4`, `brand^3`, `category^2`, `tags^2`, `description`) and `fuzziness: "AUTO"`.

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
- Local uploads use the `media-data` Docker volume by default.
- S3-compatible object storage is optional and enabled only when configured for
  deployment.

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
| `REDIS_URL` | Redis URL when running Django directly on the host |
| `CACHE_URL` | Django cache URL, set to Compose Redis in containers |
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
| `delivery-confirmation` | `server/templates/email-templates/delivery-confirmation.html` | Recorded delivery confirmation with available carrier and tracking details; no verification code is generated. |
| `wallet-funded` | `server/templates/email-templates/wallet-funded.html` | Top-up and credit confirmation showing funded amount, updated balance, and marketplace CTA. |
| `refund-request-acknowledged` | `server/templates/email-templates/refund-request-acknowledged.html` | Customer confirmation when a physical return or refund request is submitted (1–2 business day turnaround). |
| `refund-response` | `server/templates/email-templates/refund-response.html` | Staff resolution update (approved/declined) with notes, refund destination, and amount. |
| `onboarding-user` | `server/templates/email-templates/onboarding-user.html` | Customer welcome email with activation and email verification link. |
| `onboarding-staff` | `server/templates/email-templates/onboarding-staff.html` | Backoffice staff welcome and temporary access credentials guide. |
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
   - `MerchantProductSerializer`: Enforces non-empty, valid URL HopLinks when `product_type == 'affiliate_clickbank'`. Clears shipping weight/dimensions and defaults `available = 999` while bypassing variant requirements.
   - Cart addition protection: `CartViewSet.add_to_cart` immediately rejects affiliate items with HTTP 400 and provides the partner HopLink.
   - Cron protection: `server/product/cron.py` skips auto-marking affiliate products as "sold out".
4. **Staff Catalog Audit**:
   - `StoreAuditProductSerializer` exposes affiliate metadata and `StaffViewSet.store_products` supports filtering by `product_type=affiliate_clickbank` for compliance oversight.

## Settled-payment accounting and audit remediation

`Order.paid_total` and `wallet_paid` record actual settlement; `refunded_total`, `wallet_refunded_total`, and `card_refunded_total` cap cumulative reversals. Database constraints enforce nonnegative totals and tender consistency. Order placement is distinct from payment: physical COD has no paid balance, earns no payout credit, and cannot unlock digital downloads or receive monetary refunds.

Checkout snapshots persist `line_subtotal`, `discount_amount`, `net_total`, `tax_amount`, and `line_total`. Coupon allocations conserve cents across eligible lines; refunds use final line amounts and earnings use discounted merchandise amounts. Shipping quotes accept the applied coupon so preview and checkout share the tax basis. Local tax snapshots retain exact line taxes; Stripe Tax receives discounted lines and its returned line/shipping taxes are retained when available.

Cancellation, refund creation and approval acquire the same order lock. Claims reserve quantities; approved claims reduce remaining inventory and refundable funds. Original-payment split refunds distribute only the remaining wallet/card tender, and card operations use provider idempotency. Provider failures leave the transaction retriable instead of recording fictional refunds. Cancellation also reverses merchant ledgers. The existing seven-day escrow applies only to verified settled sales.

`OrderFulfillment` records status, carrier and tracking per store. Merchant updates permit forward fulfillment transitions only; global completion requires all physical store shipments to finish. Financial statuses use the support/payment workflows.

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
| `order-shipped.html` | Shipping notification with carrier, tracking number & URL | `STATUS_SHIPPED` transition (`ProductOrderTrackingView` & `execute_order_status_transition`) |
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
- **Typo & Legacy Aliases**: The legacy template path `refund-request-acknowleged` is retained as an alias to `refund-request-acknowledged.html` for backward compatibility.


Transactional service emails cover store verification, blocking (including the review reason), and restoration; administrative account suspension/restoration and backoffice permission changes; successful password changes/resets; and low physical stock for the store owner and authorized operators. Store, account-security, and inventory notices use branded HTML templates through the existing delivery outbox. No-op moderation/access requests do not resend notices. When a dedicated receipt is sent for checkout, shipment/delivery, refund decisions, cancellation, wallet top-ups, or payout decisions, the companion inbox notification suppresses its generic email while retaining inbox and push delivery. Delivery requires the configured email provider and notification worker; local console delivery does not send real email.

Inbox notifications and their email/push outbox rows are persisted in one database transaction. Worker dispatch waits until commit, so rollback removes both and broker outages leave persisted deliveries available for recovery.

Invalid, expired, or blacklisted refresh tokens return a structured HTTP 401 (`token_not_valid`) from `/api/v1/auth/refresh/`, allowing the browser proxy to clear revoked sessions and continue public browsing anonymously.

Email receipts display actual order snapshot and recipient data. Missing personal details are omitted; digital-only orders omit delivery address sections and physical-shipment language. Delivery notices report recorded status and never include sample verification codes, names, addresses, phone numbers, carrier values, or product photos.
