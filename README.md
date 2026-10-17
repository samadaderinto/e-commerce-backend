# Proace Commerce

Local Docker Compose workers use `CELERY_WORKER_CONCURRENCY` (default `2`) to
bound prefork memory. Set it to `7` to restore the earlier CPU-sized pool; this
does not change host-managed Celery defaults. See [worker memory tuning](docs/performance.md#local-celery-worker-memory).

Demo seeding uses `populate_fake_data`; blog-tag changes are excluded from the
product-specific catalog invalidation handler. Product-tag invalidation remains
enabled. See [backend documentation](docs/backend.md).

Frontend route bundles load on demand with SSR preserved; unconfigured browser
push does not download the Firebase SDK. See [performance](docs/performance.md)
for measured bundle reductions and verification commands. Authentication and
private-data cache freshness are unchanged.

Saved payout destinations support bank/holder/account-suffix search and default-account filtering; the API accepts `search` and `is_default` on the owner-scoped bank-account list.

Payout destinations have a dedicated `/account/payout-accounts` page in My Account. Bank account and Stripe connected-account identifiers are encrypted at rest and masked in the UI; destinations are owner-scoped and support edit, deletion, and a default per destination type. Treasury withdrawal forms group amount and method together, show available funds clearly, and keep the destination and content-sized submit action within a 620px form; the destination opens a checkout-style management modal to select, add, edit, delete, or set a default bank or Stripe destination, with a link to the full payout accounts page inside the modal. Only its ID is submitted for server-side resolution. A Stripe destination records where an audited transfer request is intended to go; it does not itself execute a Stripe transfer. `/settings/bank-accounts` redirects to the My Account page. Apply migrations through `core.0024_stripepayoutdestination` before using saved Stripe destinations. Preserve the application secret key (or migrate encrypted data when rotating it). Staff directory access is limited to regular accounts; staff can change their active state but cannot inspect or change privileged accounts. Stripe payment returns confirm payment and navigate to the specific order through `/orders/stripe-return`; orders are created only after payment confirmation. Stripe Connect discards demo `acct_mock_*` placeholders and replaces accounts reported missing by Stripe; fake-data seeding never marks payouts as connected. Object storage never silently falls back when enabled dependencies are unavailable. Root browser media downloads are ignored by Git.

Celery uses the worker by default, including debug mode. `CELERY_TASK_ALWAYS_EAGER=true` explicitly runs tasks inline and should be reserved for tests or deliberate local diagnostics.

Catalog invalidation queues a Celery task after commit to warm the first anonymous page at the last observed backend origin. Pending warm jobs are coalesced for ten seconds; broker failures are logged without failing committed commerce changes. Warming requires the worker and Redis and retains host-specific cache keys and authoritative row checks. Apple public signing keys are shared in Redis for one hour, with forced refresh on key rotation and a five-second provider timeout. These improvements require measurements before claiming a latency gain.

`client/tests/filter-stability.spec.ts` exercises delayed filter responses for guests, shoppers, buyers, sellers, merchants, staff, business administrators, and technical administrators on desktop and mobile. It verifies retained results, typing focus, mounted controls, same-document shop history, and customer profile stability.

Notification search, tabs, and category filters retain results within the same account and store. Backoffice filter caches and private product previews include the viewer identity; login cancels outstanding queries and clears the prior query cache before activating the new account. External payment and onboarding redirects remain full navigations.

Shop filters update browser history without route navigation. Filtered catalog, merchant, and backoffice queries retain current results while fetching and show a local update status; store and account detail queries discard previous results when the selected entity changes.

Catalog responses expose the backend `visibility` flag. The product page shows the draft preview banner only for explicit `visibility: false`; missing metadata is not evidence of a draft. Hidden products return 404, and unverified-store previews require the store owner or an authorized operator, even with `?preview=1`.

Shared frontend styling in `client/src/app/design-system.css` standardizes form controls, buttons, cards, dialogs, catalog typography, and ClickBank partner badges across light and dark themes. Dense actions use the reusable 12px, 36px `.button.compact` variant, including backoffice and merchant heading actions; rounded store contact actions use `.button.compact.pill`. Mobile controls use readable input sizes, touch devices expose quick product actions, and reduced-motion preferences are respected.

Lifecycle tracking records JWT sign-ins, throttled authenticated user/store activity, profile/catalog revisions, cart mutations, notification reads, review edits, coupon redemptions, affiliate clicks, and order transitions. Apply the new Django migrations with `python server/manage.py migrate`; admin/account/merchant views surface the timestamps. Existing unknown activity and transition times remain unrecorded rather than being inferred.

Admin and staff record details share a responsive dialog with a labeled header, status badge, two-column definition list (one column on mobile), and print/close actions. Printing isolates the selected record.

A Next.js marketplace and Django API in one base repository.

```text
client/                 Next.js 16 App Router frontend and browser UI
server/                 Django REST Framework modular monolith API
docs/                   Canonical documentation directory (all technical guides & architecture)
monitoring/             Observability stack (Grafana, Loki, Prometheus, Tempo, Alloy)
.github/                CI/CD and HostGator VPS deployment workflow
package.json            npm workspace and root commands
AGENTS.md               Global AI agent operational guidelines and architecture rules
README.md               Root project summary, quickstart, and entry point
```

The previous `codematics/` backend directory is now `server/`. The Python settings
package inside it is still named `codematics`. Existing backend work was moved,
not replaced. The runnable commerce configuration is
`codematics.storefront_settings`; the legacy settings remain available separately.

## Centralized Documentation Hub

All detailed technical documentation is centralized exclusively in [`docs/`](docs/README.md). The root `README.md` is the primary repository entry point. New contributors should start with the [3-Minute Quickstart & Documentation Hub](docs/README.md), followed by the specific topic guides:

- **Getting Started & Local Setup**: [`docs/getting-started.md`](docs/getting-started.md)
- **Architecture & Route Registry**: [`docs/architecture.md`](docs/architecture.md)
- **Frontend Architecture & Components**: [`docs/frontend.md`](docs/frontend.md)
- **Backend Architecture & Business Logic**: [`docs/backend.md`](docs/backend.md)
- **Access Control, Roles & Permissions**: [`docs/access-control.md`](docs/access-control.md)
- **Shipping & Fulfillment Integrations**: [`docs/shipping-integrations.md`](docs/shipping-integrations.md)
- **UI Design System, Tokens & Modals**: [`docs/ui-and-events.md`](docs/ui-and-events.md)
- **Infrastructure & Container Stacks**: [`docs/infrastructure.md`](docs/infrastructure.md)
- **Observability & Health Monitoring**: [`docs/observability.md`](docs/observability.md)
- **Current Bug Audit (8 October 2026)**: [`docs/bug-audit-2026-10-08.md`](docs/bug-audit-2026-10-08.md)
- **Global AI Agent Operational Rules**: [`AGENTS.md`](AGENTS.md)

Whenever code behavior, models, endpoints, or configurations change, developers and AI agents must update the matching guide in `docs/` AND the root `README.md` in the same pass.

## App Boundary

This is one codebase with two separately hostable apps:

- `client/`: Next.js frontend. Host on a frontend platform or as its own
  container. It talks to the backend through `API_URL`.
- `server/`: Django API. Deploy to the HostGator VPS. It owns data, auth, search,
  observability and background/service integrations.

The browser calls the Next.js `/api/*` proxy. The proxy forwards to the Django
backend configured by `API_URL`, stores tokens in HTTP-only cookies and keeps raw
JWTs out of browser-visible JSON.

## Run Locally

Requires Node.js 22 and Python 3.11 or newer.

```sh
npm ci
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.txt
.venv/bin/python server/manage.py migrate --settings=codematics.storefront_settings
.venv/bin/python server/manage.py populate_fake_data --settings=codematics.storefront_settings --password 'ProaceDemo2026!'
```

In Docker Compose, the API applies migrations and configured default-account
bootstrap at startup when `RUN_MIGRATIONS=true`; Celery worker and beat containers
wait for that shared schema and never run migrations or account bootstrap.

For a larger local dataset, run `populate_fake_data --scale large` (200 users,
25 seeded stores, 500 products, 1,500 orders, and 1,100 reviews). Re-running
adds bulk-seeded products and orders; it does not require deleting Docker
volumes. `--clear` deletes commerce rows throughout the database, so use it
only with disposable data. Each invocation is transactional: failures roll
back both generated rows and any requested clear, and search indexing starts
after commit. The command requires at least 11 users for its guaranteed
accounts, never prints the configured seed password, and is disabled whenever
`DEBUG=False`. Volume overrides must be positive; `--users` must include the
11 guaranteed accounts. Seeded merchant wallets do not pretend to have a
real Stripe Connect account. Stripe onboarding returns to merchant settings, where the backend refreshes `details_submitted` and `payouts_enabled`; enabled accounts show a connected state, submitted accounts under review show a pending state, and neither can create another onboarding link. Accounts with required details remaining can resume setup.

Run the API and client in separate terminals:

```sh
.venv/bin/python server/manage.py runserver 127.0.0.1:8000 --settings=codematics.storefront_settings
```

```sh
npm run dev
```

Open <http://127.0.0.1:3000>. The client defaults to
`http://127.0.0.1:8000/api/v1`; override `API_URL` in `client/.env` when needed.
Set `NEXT_PUBLIC_GOOGLE_CLIENT_ID` / `NEXT_PUBLIC_APPLE_CLIENT_ID` in
`client/.env` and matching `GOOGLE_CLIENT_ID` / `APPLE_CLIENT_ID` values in
`server/.env` to enable real Google and Apple customer sign-in. Rebuild the
client container after changing either `NEXT_PUBLIC_*` value because Next.js
embeds them into the browser bundle at build time.
Product cards, storefront media, review photos and avatars use responsive
Next.js AVIF/WebP optimization with blurred loading placeholders for configured
MinIO, Unsplash and Google image hosts. Product detail and opened media views
retain the original resolution. Set `MINIO_PUBLIC_URL` before building the
client container so its image optimizer allows the correct public media host;
inside Docker it fetches MinIO through the internal service address. Listing
thumbnails use reduced image quality, and generated image variants cache for
seven days; uploaded objects use non-overwriting paths.
Customer email verification and password-reset links print to the API terminal with the local console email backend. Staff credential issuance requires a private email backend such as Resend or SMTP.
Set `FRONTEND_URL=http://127.0.0.1:3000` to keep email links on that exact host.
Use `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` for normal local development and `EMAIL_BACKEND=notification.email_backend.ResendEmailBackend` for production or a temporary real-email test locally. See [email backend setup](docs/getting-started.md#email-backend-local-development-and-resend-testing) for sender requirements, environment refresh commands and switching back after testing.

## Run The Container Stacks

The project uses modular Compose stacks located in `client/`, `server/`, and `monitoring/`:

### Option A: Run All Stacks (Frontend + Backend + Monitoring)
From the repository root:

```sh
# Start all stacks via package.json script
npm run docker:up

# Or start each stack individually
docker compose -f server/compose.yaml up --build -d
docker compose -f client/compose.yaml up --build -d
docker compose -f monitoring/compose.yaml up -d
```

The Next.js storefront will be available at <http://127.0.0.1:3000>, the Django API at <http://127.0.0.1:8000>, and Grafana at <http://127.0.0.1:3002>.

The API image copies `mc` from a digest-pinned MinIO client image and invokes
its entrypoint through `/bin/sh` so local bind mounts do not require an executable
script. If builds report `http.docker.internal` DNS timeouts and container starts
hang, restart Docker Desktop and retry; see [infrastructure](docs/infrastructure.md).

Gunicorn's optional `gunicornc` control socket is disabled in the container
configuration. Docker manages shutdown and restart through signals, and disabling
the socket avoids unsupported Unix socket operations on macOS bind mounts.

### Option B: Backend Stack Only
From the repository root:

```sh
.venv/bin/python monitoring/init_local.py
docker compose -f server/compose.yaml up --build -d api notification-stream redis postgres elasticsearch
docker compose -f server/compose.yaml exec api python manage.py rebuild_product_index
```

### Option C: Frontend Stack Only
From the repository root:

```sh
docker compose -f client/compose.yaml up --build -d
```

### Option D: Monitoring Stack
From the repository root:

```sh
docker compose -f monitoring/compose.yaml up -d
```

The API uses `redis://redis:6379/0` inside Compose. The API is available at
<http://127.0.0.1:8000>, Redis is bound to `127.0.0.1:6379`, Grafana is at
<http://127.0.0.1:3002>, and Prometheus is at <http://127.0.0.1:9090>. PostgreSQL
is available at `127.0.0.1:5432`, Elasticsearch is at `127.0.0.1:9200`, and both
persist in named Docker volumes. The Grafana password and metrics token live in
`server/.env`. Log aggregation is part of this stack too: Alloy collects Docker
container stdout and sends it to Loki, which is available in Grafana Explore.

Check running stacks and follow logs:

```sh
docker compose -f server/compose.yaml ps
docker compose -f client/compose.yaml ps
docker compose -f monitoring/compose.yaml ps
docker compose -f server/compose.yaml logs -f api redis
```

In Grafana, open Explore, select Loki, and query API logs with:

```logql
{service_name="api"}
{service_name="api"} | json | level="ERROR"
```

The API health endpoint is <http://127.0.0.1:8000/health/live/>. Stop all
stacks with:

```sh
npm run docker:down
# Or stop individually:
docker compose -f client/compose.yaml down
docker compose -f server/compose.yaml down
docker compose -f monitoring/compose.yaml down
```

Kafka and RabbitMQ are optional and are disabled by default. Start them only for
queue-consumer work with:

```sh
docker compose -f monitoring/compose.yaml --profile messaging up -d kafka rabbitmq
```

For production, use the HostGator VPS environment and GitHub Actions secrets,
not checked-in env files. Full deployment details are in [`docs/deployment.md`](docs/deployment.md) and
[`docs/observability.md`](docs/observability.md).

The GitHub Actions deploy job targets the HostGator VPS. It validates SSH and
environment secrets, uploads the release, rebuilds the containers, and verifies
the public HTTPS health endpoints.

### Sample Accounts

The seed command creates these accounts only when absent:

| Account | Email | Password with the example seed command |
| --- | --- | --- |
| Customer | `shopper@proace.local` | `ProaceDemo2026!` |
| Seller | `seller@proace.local` | `ProaceDemo2026!` |

The seed catalog, orders and identities are local sample data. Seeding is refused
when `DJANGO_DEBUG=false`. Re-running does not reset passwords or stock. The new
SQLite database is `server/storefront.sqlite3`; existing databases are untouched.

## Customer Experience

- Storefront with product photography, categories, deals, and Elasticsearch fuzzy search.
- Search, category/price filters, sorting, and pagination.
- **Product Variants**: The base product remains a selectable **Original edition**, with opt-in size, color, material, and digital-format options that apply their own price delta and inventory updates.
- **Verified Reviews & Photos**: In-place reviews exclusively for purchasers, with 1–3 secure HTTPS photo URLs, real-time rating updates, and a photo gallery lightbox. The rating summary opens the reviews tab and scrolls it into view. Authors can edit/delete their reviews; store owners and backoffice staff can remove reviews. Admin edits and removals keep catalog averages synchronized.
- **Flash Deals & Live Countdowns**: Urgency badges and real-time countdown clocks on limited-time discounts.
- **Store Profiles & Announcements**: Dedicated merchant showcase pages with marquee announcements, pinned items, and direct "Message Store" contact actions.
- **Seller Tier Badges**: Dynamic verification tick and rank badges (Starter 🔵, Booster ⚪, Accelerator 🟣, Power 🟢, Mega 🟠, Legendary 👑, and Official 🟡).
- **ClickBank Affiliate & Partner Offers**: Seamless integration of external ClickBank partner products coexisting alongside native marketplace listings. Features partner badges, custom CTA labels ("Buy on Partner Site"), and transparent partner fulfillment notes. Secure outbound routing via `/api/affiliates/clickbank/outbound/<id>` attaches tracking tokens (`tid=cb_*`) and logs outbound clicks while blocking local cart checkout.
- Saved items and persistent guest bag with automatic guest-to-account merge on sign-in; product detail quantity reflects the desired total in the bag, adding or reducing the difference as needed. Items that fail to sync remain available for review and retry.
- Email-verified registration, sign-in, password reset, and session management.
- Email identities are normalized case-insensitively; reset links are single-use and invalidated when credentials change. Staff and admin accounts remain password-only.
- **Google & Apple Social Authentication**: Customer registration and sign-in with Google or Apple identity tokens. Google Identity Services renders its official account-selection button, with dual-theme Apple styling, strict staff/admin sign-in guardrails, and affiliate referral synchronization awarding \$25 promotional store credit to referring marketers after new customer email verification.
- **Product Sharing & Instant Link Copy**: Product detail copy controls write the listing URL to the clipboard on the first click without opening the system share sheet. They show copied feedback and a toast; product preview banners also provide link sharing.
- Profile, personal avatars with circular 512x512 crop dialog, delivery addresses, order history, and detailed order pages.
- **User Avatar & Photo Management**: Profile picture upload with client-side circular crop tool (`UserAvatarCropDialog`), 512x512 server validation, MinIO media persistence, managed centrally in Personal details (`/account/profile`) with instant reflection across customer account, merchant workspaces, and backoffice staff tables.
- **Public Image Upload Protection**: User/store avatars, store branding, and product gallery images accept JPEG, PNG, and WebP up to 5 MB. The server applies EXIF orientation and removes embedded metadata before public storage, with a 40-million-pixel decode limit. Digital downloads and variants support files up to 50 MiB through the upload proxy.
- **App Settings & Email Preferences**: Global `/settings` page supporting theme customization (Light / Dark / System) with an authenticated user section for **Email communication preferences** (opting in/out of product recommendations and promotional marketing emails via `/api/v1/me/`).
- **Order Tracking & Dual-Theme Milestone Tracker**: Dynamic fulfillment tracker with official USPS, UPS, FedEx, and DHL links; multi-store orders show tracking for each store shipment. Shipping service and carrier quotes are preserved in each order.
- **Address-Based Delivery Pricing**: Physical cart delivery is calculated after selecting a destination and carrier at checkout; digital delivery remains free. Multi-store quotes expose shipment-level amounts consistent with the selected delivery total.
- **In-App Password Management**: In-dialog password updates (`/api/v1/password/change/`) verifying current passwords and enforcing secure credential hygiene.
- **ProAce Wallet, Top-Ups & Refunds**: Integrated customer wallet balance with Stripe Checkout top-up sessions (`/api/v1/wallet/topup-session/`), 7-day physical return window with per-product claim idempotency (declined and processed items cannot be re-requested), and instant store credit refund resolution.
- **Order Cancellation**: Self-service shopper cancellation for unfulfilled physical orders within 12 hours of placement, with atomic variant inventory restock, merchant earnings reversal, and refunds limited to actual wallet/card payments. Shared order transitions also block cancellation of instant digital orders and physical orders already shipped, delivered, or picked up; post-fulfillment financial adjustments use the refund workflow.
- **Flexible Checkout**: Supports Cash-on-Delivery, ProAce Wallet balance, and Stripe Wallet payments with transactional stock deductions and idempotent retry handling.

## Seller Experience

Visit `/merchant` after signing in:
- **Seller Workspace Dashboard**: Daily order activity trend bar charts, low-stock inventory alerts, top-selling products, and tier milestone celebration banners.
- **Product Management & Variants**: Create physical goods, digital assets, or ClickBank affiliate offers. Configure custom variant matrices with price deltas and individual stock allocations, flash sale timers, HopLink targets, and MinIO photo galleries. Moderation alert banners provide policy violation explanations and seller guidance for blocked items while isolating merchant edits from administrative unblocking.
- **Partner Offer Configuration**: Publish ClickBank affiliate listings with direct HopLink URLs, vendor account nicknames, and custom landing CTA buttons, with automatic bypassing of physical shipping and variant restrictions. Partner listings enforce partner-controlled pricing (locking platform discounts to 0% and omitting flash sale countdowns to avoid fictitious price discrepancies).
- **Bulk CSV Catalog Import**: RFC 4180-compliant batch upload supporting quotes, multiline values, variants, and tags.
- **Storefront Customization**: Configure store announcement banner, banner covers, avatars, bio, and direct customer inquiry channels.
- **Escrow & Wallet Management**: 7-day review escrow holding net sales from new orders, transparent 4% platform commission calculation, available balance release, and withdrawal requests (`/merchant/payouts`). Store-scoped withdrawals cannot spend another store's earnings; combined wallet withdrawals remain available through the unified endpoint. Stripe Connect transfers require an account whose payouts are enabled. Official company stores automatically consolidate 100% of retail sales into Platform Treasury.
- **Official Store Ownership Separation**: Staff and administrators can operate official company stores from the merchant workspace, but official products are not serialized as a user's own seller listing in the customer catalog. Backoffice accounts see preview-only purchase controls.
- **Order Fulfillment**: Review store-specific customer orders, click an order reference for its detail dialog, print order details, assign carrier & tracking numbers, update fulfillment milestones, and open linked orders directly from notifications. Notification links select the owning store and open that order’s detail dialog, even when it is outside the current page. Merchant payout and earnings-ledger references open printable detail dialogs; bank and routing numbers are masked.
- **Product Sales Counts**: The merchant product list and its CSV export show units sold for each ProAce product. Affiliate partner listing sales are marked as not tracked because purchases complete on the external partner site.

## Admin & Staff Experience

Visit `/admin` (Platform Intelligence), `/admin/commission` (Platform Treasury), and `/admin/staff` (Team Administration):
- **Staff Profiles**: Selecting a staff member's photo or name in Team Administration opens their full backoffice profile; the row's Details action remains available for a quick summary.
- **Executive Analytics Dashboard**: Platform gross revenue, order volume, active user growth, and store fleet health across 7/30/90/365-day periods.
- **Order Status Distribution Chart**: Visual fulfillment pipeline breakdown across order lifecycle stages.
- **Customer Order Audit & Emergency Controls**: Centralized order management (`/admin/orders`) with status overrides, tracking inspection, and multi-dimensional filtering across order status, payment tender, and delivery courier (USPS, UPS, FedEx, DHL, Digital).
- **Moderation & Payout Queues**: Review 7-day customer refund requests, moderate or remove abusive product reviews, and approve/reject third-party merchant payout requests (`/admin/payouts`). Refund and payout decisions require an explicit action; declines and rejections require an audit reason.
- **Platform Treasury & Commission Wallet**: Unified corporate finance ledger (`/admin/commission`) consolidating marketplace 4% fee commissions and 100% of official company store retail sales. Pending withdrawals can be completed only with a recorded external transfer confirmation or failed with a reason, which releases the reservation.
- **Store & Listing Moderation**: Staff and administrators can block or restore individual listings (`POST /api/v1/admin/staff/products/<pk>/moderation/`) with mandatory reason presets (suspected scam, prohibited item, misleading description, policy violation) without suspending the whole store. Blocking immediately hides items from public catalog/search, marks cart lines unpurchasable, and rejects checkout while notifying the merchant with guidance and preserving order records. Full store suspension remains available for repeated store-wide abuse. Moderation updates invalidate catalog cache.
- **Role Hierarchy & Credential Isolation**:
  - **Technical Super Admin (`is_superuser=True`)**: Password resets via UI or `manage.py recover_privileged_user` automatically sync across Django, MinIO, and Grafana via `server/core/auth_sync.py`.
  - **Business Admin (`is_business_admin=True`)**: Operators manage staff, verify stores, and review payouts; strictly isolated from infrastructure credential sync.
  - **Staff (`is_staff=True`)**: Backoffice operators audit orders and manage official brand stores.

## API And Authentication

All browser API calls use the Next.js `/api/*` server proxy. Access and refresh
tokens live in HTTP-only, SameSite cookies, not browser local storage. Mutating
requests require a same-origin `Origin` header. The proxy refreshes expired access
tokens, excludes credentials from JSON responses, and clears cookies on sign-out.
Public catalog, product, and store pages retry anonymously when saved authentication is rejected, clearing invalid cookies while retaining Django’s public visibility rules. Invalid or revoked refresh tokens return HTTP 401 so the proxy can clear stale sessions; temporary refresh outages preserve the saved session. Production cookies require HTTPS.

The Django API uses `/api/v1/`. It reuses existing users, stores, products, carts, and
orders. Ownership is derived from authentication. Public catalog responses exclude
drafts and blocked sellers.

The OpenAPI schema is available at `http://127.0.0.1:8000/api/schema/` (YAML by
default; request `application/vnd.oai.openapi+json` for JSON), with interactive
Swagger UI at `/api/docs/` and ReDoc at `/api/redoc/`. Authenticated API operations
use a JWT bearer access token; the browser storefront keeps those tokens in HTTP-only
cookies and calls the API through its same-origin Next.js proxy.

## Verification & Testing Hierarchy

The test suite is organized into two distinct verification tiers:

### Tier 1: Fast Offline Verification (No Servers Required)
Run locally before staging or committing changes:

```bash
# 1. Frontend TypeScript Validation (zero type errors required)
npm run typecheck

# 2. Frontend Unit Tests (33 tests via Node native runner)
npm run test:unit

# 3. Backend Test Suite (Django / Pytest: 477 tests; 468 passed, 9 environment-dependent skips offline)
.venv/bin/pytest server/
```

### Tier 2: Integration & End-to-End Suites (Live Dev Servers)
The seeded technical admin may retain a custom password. Supply `E2E_TECHNICAL_ADMIN_PASSWORD` separately from `E2E_DEMO_PASSWORD` for its live role checks; never reset that account to make tests pass. Disable trace recording (`--trace=off`) when using protected account credentials.

Run with the backend (`python server/manage.py runserver 127.0.0.1:8000`) and frontend (`npm run dev`) running with seeded demo data (`manage.py populate_fake_data`):

```bash
# Next.js API proxy integration tests
npm run test:integration

# Playwright browser end-to-end test suite (Desktop & Mobile)
npm run test:e2e
```

### Tier 3: Pre-Deployment QA, Performance, Security & Bug Audits (Local PC)
Run locally before deploying new features to production. All generated reports are saved into the git-ignored `qa-reports/` directory:

- **AI Agent Bug Audits**: Whenever an AI agent conducts a bug audit (e.g. reviewing regressions, triage, security inspection), the markdown audit report is saved to `qa-reports/bug-audit/`.
- **Pre-Deployment Performance & Security Testing Commands**:
  ```bash
  # 1. Load Testing (Sustained concurrent browsing, search, and detail requests)
  npm run test:load       # -> qa-reports/performance-testing/load/

  # 2. Stress & Spike Testing (Step-ramp concurrency, instant traffic spikes, race condition locks)
  npm run test:stress     # -> qa-reports/performance-testing/stress/

  # 3. Volume Testing (Deep pagination LIMIT/OFFSET, multi-criteria filtering, payload serialization)
  npm run test:volume     # -> qa-reports/performance-testing/volume/

  # 4. Security & Data Leak Check (Sensitive data leak detection, role boundary isolation, audit regression suites)
  npm run test:security   # -> qa-reports/security/

  # 5. Full Pre-Deployment QA Suite (Runs all 4 suites sequentially)
  npm run test:qa
  ```

Unit tests exercise frontend API serialization/error handling, currency formatting,
categories, address validation, and backend price rounding without making external service calls.
Backend tests cover authentication, permissions, cart atomicity, coupon redemption,
wallet transactions, 7-day refund escrow, destination sales tax calculation & admin management,
transactional HTML email dispatching across auth, store moderation, security, inventory, orders, refunds, and payouts,
USPS tracking, review photo validations, variants serialization, flash sale countdowns, and merchant payouts.

## Deployment Boundaries

- Set `DJANGO_DEBUG=false`, a strong `SECRET_KEY`, `ALLOWED_HOSTS`, `FRONTEND_URL`,
  Resend API/sender configuration, ClickBank affiliate keys (`CLICKBANK_AFFILIATE_NICKNAME`, `CLICKBANK_SECRET_KEY`), and persistent media/database storage. Build
  the client with `npm run build` (or `npm --prefix client run build`) and run `npm run start --workspace=client`
  behind HTTPS.
- Dedicated monitoring stack (Grafana Loki, Alloy, Prometheus, Tempo) runs via
  `monitoring/compose.yaml` with centralized dashboards at `http://127.0.0.1:3002`.
- Product photos and media uploads are persisted in named volumes or S3-compatible
  object storage (MinIO/AWS S3).

## Back-office roles and shipping

See the [endpoint permission matrix and staff onboarding](docs/access-control.md)
and [carrier setup and checkout API](docs/shipping-integrations.md).
Apply the new core, store, and payment migrations before starting this version.
Staff/admin accounts use operational workspaces and cannot shop. Grafana requires
technical-admin credentials; anonymous access is disabled.

See [UI components and live event pipeline](docs/ui-and-events.md) for responsive conventions, pagination, carrier selection, cart states, scoped SSE events, and verification procedures.

Product editors open unsaved storefront previews at `/merchant/products/preview` in a separate tab, preserving the draft while matching the buyer product-detail layout with checkout, save, and seller navigation disabled. Digital products accept zero shipping weight; physical products require at least 0.01 lb.

Product creation and asset uploads are separate steps. Failed uploads retain the saved product ID so Save changes updates the same listing rather than creating a duplicate. Local media volumes must be writable by the API’s `app` user; see [infrastructure](docs/infrastructure.md).

Product updates accept the existing server-generated cover URL, including local media hostnames; new pasted cover URLs still undergo URL validation.

Backoffice order-status overrides require an audit reason in the confirmation dialog. Browser commerce tests select listings and seller names from the seeded API and use ProAce Wallet checkout rather than legacy cash-on-delivery flows.

The unsaved product preview displays variant options with selectable prices and images, plus the configured flash deal countdown in the product price block. Countdown badges stay content-sized beside price details on both the preview and product detail page. Expired draft deals show an explanation instead of disappearing.

Anonymous API failures cannot clear cookies set by a concurrent successful login; authenticated failures still expire invalid sessions.

Backoffice navigation uses a dedicated responsive icon navigation row with active-page highlighting, separate from account controls. Overview destinations appear once in the same horizontally scrollable navigation row, including merchant payouts, users, administrator commission withdrawals, and technical-admin Grafana metrics. Required admin and staff password changes use a focused security card with password confirmation and a visibility toggle.

Store onboarding requires a complete business address (street, city, state/region, country and postal code). Products may be saved as drafts, but manual and scheduled publication require that address for both digital and physical listings.

Purchase validation also rejects existing stores without a complete default business address, including digital-only stores. Missing physical shipment origins return a validation error rather than silently using Tampa.

Time handling: Django stores timezone-aware UTC instants (`TIME_ZONE=UTC`, `USE_TZ=True`). Browser date/time inputs display local time and submit ISO UTC timestamps. Dashboard requests accept a validated IANA `time_zone` (UTC by default); the browser supplies its timezone for local calendar-day reporting. Date-only chart labels are preserved without timezone shifts. Cron and carrier request clocks use aware UTC; flash countdowns include minutes.

Military postal delivery: APO/FPO/DPO destinations use USPS only with the currently supported integrations. Checkout disables other carrier options and the server rejects unsupported carriers in both demo and live rating and payment flows. Address city/state/ZIP must agree: AA uses 340xx, AE uses 090xx–098xx, AP uses 962xx–966xx, with country United States. This is a supported-service policy, not a claim that all commercial postal handoff services are prohibited: UPS Ground Saver and Mail Innovations have military-address support but are not integrated here. See [USPS military addressing standards](https://pe.usps.com/text/dmm300/703.htm) and [UPS supported services](https://www.ups.com/us/en/support/shipping-support/print-shipping-labels/how-to-write-address). ZIP blocks alone do not guarantee an active destination or eligibility for every USPS service; live carrier availability and military mail content/customs requirements still apply.

Commerce safety: split-tender checkout reserves wallet funds and records recoverable Stripe attempts with 30-minute expiry; cancellation returns reserved funds only after Stripe confirms the exact session expired, and Celery Beat retries failed refunds and releases abandoned holds. Top-up cancellation serializes against payment confirmation and leaves ambiguous or provider-unverified sessions pending. Cart lines persist variants, merchant refund debt is retained, destination sales tax is computed via a hybrid database & Stripe Tax engine, and buyer digital downloads are authenticated streams. Apply the new cart/payment migrations before running the updated app. See [audit remediation](docs/security-audit-remediation.md) for recovery behavior, import limits and verification boundaries.

Commerce bug-audit fixes persist settled tender amounts, allocated coupon/tax line totals, cumulative refunds, store-scoped fulfillment, and unique wallet funding receipts. Apply `python server/manage.py migrate` before running the updated backend, then restart API/Celery processes. COD supports physical goods only and never grants paid balances or digital access. See [the remediation and verification record](docs/bug-audit-2026-10-08.md) and [backend accounting rules](docs/backend.md).

Transactional service emails cover store verification, blocking (including the review reason), and restoration; administrative account suspension/restoration and backoffice permission changes; successful password changes/resets; and low physical stock for the store owner and authorized operators. Store, account-security, and inventory notices use branded HTML templates through the existing delivery outbox. No-op moderation/access requests do not resend notices. When a dedicated receipt is sent for checkout, confirmation, shipment/delivery/pickup, refund decisions, cancellation, wallet top-ups, or payout decisions, the companion inbox notification suppresses its generic email while retaining inbox and push delivery. Delivery requires the configured email provider and notification worker; local console delivery does not send real email.

Inbox notifications and their email/push outbox rows are persisted in one database transaction. Worker dispatch waits until commit, so rollback removes both and broker outages leave persisted deliveries available for recovery.

Store settings use plain customer-facing labels for store branding, the logo URL, cover image URL, and store announcement. Design references are kept out of the settings interface.

Email receipts display actual order snapshot and recipient data. Missing personal details are omitted; digital-only orders omit delivery address sections and physical-shipment language. Delivery notices report recorded status and never include sample verification codes, names, addresses, phone numbers, carrier values, or product photos.

ClickBank offer prices are retained only as internal catalog references. Public product cards, detail pages, and listing previews direct shoppers to check the current price on the partner site. Selecting the ClickBank listing type hides ProAce discount and flash-deal controls; the server rejects those promotions and clears them when converting a standard listing.

Store profile pages (`/shop?store=<id>`) list only that store’s products. Filter resets retain the store and any `preview=1` mode; previews remain read-only.

The catalog supports 29 departments shared by homepage category tiles, shop/store filters, and merchant product forms: Electronics, Fashion, Phones, Computing, Sports & outdoors, Books, Toys & games, Kids & baby, Home & living, Kitchen & dining, Beauty & personal care, Health & wellness, Pet supplies, Gaming, Tablets, Fishing, Lingerie & sleepwear, Coffee, tea & drinks, Garden & tools, Automotive, Jewelry & watches, Software & apps, Courses & learning, Templates & planners, Design assets, Photos & video, Music & audio, Business resources, Digital tools & presets. New department keys are validated by Django product choices; apply product migrations before using them. Existing product category keys are preserved.

Backoffice user profiles use a compact identity card with contact and activity details, three financial summary cards, and bordered wallet, activity, and order panels. The layout stacks on smaller screens and respects the active theme. In customer, user, and staff directories, clicking the avatar or name opens that profile; row actions handle account status and staff access. In admin listings, store names open the dedicated store profile, while payout references, order IDs, coupon codes, refund IDs, and refund order IDs open their matching detail dialogs without duplicate Details buttons.

The backoffice store catalog audit shows tracked units sold for standard products, labels externally fulfilled partner offer sales as not tracked, and links each product name to its read-only product preview.

Every digital product can have an uploaded downloadable file per variant. Merchants declare each option as Image, Audio, Video, or Document/software before upload; the server enforces that the file matches the declared option type and belongs to that product. Digital-artwork gallery uploads and image variants are converted into watermarked carousel previews, while original downloads remain private until an authorized purchase. Completed orders use the file mapped to the option purchased. Digital downloads up to 50 MiB are supported through the upload proxy.

Dates across customer, merchant, and backoffice records use the shared `DateStamp` component: an unambiguous date (e.g. `10 Oct 2026`) and local 24-hour time without seconds. Table timestamps have separate columns, including Created, Updated, Last active, Requested, Processed, Valid from, and Valid to where applicable. Date fields are never stacked together or joined with slashes in a table cell. Tables scroll horizontally on narrow screens; profile activity uses aligned label/value rows. API timestamps and calendar-input timezone handling remain unchanged.

Backoffice user-profile order history supports debounced reference/coupon/carrier/tracking search, status (including pickup), courier, payment method, sorting, reset, and 15-row server pagination. Profile order totals and lifetime spend remain independent of order filters.

Backoffice coupon attribution displays the recorded creator’s email. Coupon creation assigns the authenticated staff/admin server-side; records without a creator show “Not recorded” rather than an assumed staff identity.


Agent workflow: after verified implementation changes, agents automatically rebuild and recreate only the affected local Docker services (`client`, `api`, and affected `notification-worker`/`celery-beat` consumers) using Compose `up -d --build --no-deps`, then check startup and health. Documentation-only changes require no rebuild. See `AGENTS.md` for the standing authorization and service scope rules.

Local backend Compose startup now starts MinIO and waits for `minio-init` to finish provisioning the media bucket and application credentials before starting API/worker/scheduler consumers. This also applies when starting a backend service individually without `--no-deps`; targeted `--no-deps` refreshes assume dependencies are already running. The initializer fails on required bucket/policy setup errors. Existing storage volumes are preserved.

Partner product details and merchant previews show “Price available on partner site” as a compact supporting note, with pricing determined by the external vendor.

The [listing filtering audit](docs/filtering-audit-2026-10-10.md) records gaps in payout approvals, finance histories, account/staff listings, and catalog filters, with prioritized remediation and verification criteria.


Listing filtering remediation (2026-10-10): payout approvals, merchant payouts and earnings, customer orders/wallet, treasury withdrawals, user/staff management and profile wallet histories now filter before server pagination with matching counts. Finance criteria combine reference search, status/type/method, inclusive UTC date ranges and amount bounds; balances and lifetime totals remain independent of listing filters. Catalog controls expose category, physical/digital and standard/partner types, stock and visibility as applicable. Coupons support type, validity and creator email; stores support official/merchant and creation dates. Saved products filter the complete saved collection before pagination. Notifications support independent read/archive state and category. Search is debounced by 300 ms, criteria changes return to the first page, and reset controls clear active criteria. Invalid financial bounds and pagination return HTTP 400; existing user/store access scopes remain authoritative.

Account activity on shopper, staff, admin, and user-detail profiles uses a shared responsive set of compact cards. Each label stays with its local date and time instead of spreading across the page; semantic surfaces and text colors support both themes. Table timestamps retain their separate aligned columns.


The [notification audit of 11 October 2026](docs/notification-audit-2026-10-11.md) traces order `uuEl5iwv6QMVG`, records reproduced store-filter visibility and duplicate merchant notices, and defines the proposed recipient/channel matrix and remaining delivery/remediation work. Audit findings are not implemented fixes; local console email and disabled FCM do not verify external delivery.


Notification remediation (11 October 2026): one canonical event identity per recipient, recipient-scoped multi-store associations, canonical categories and archived/list filters, selected-store refund reviewer routing, treasury/affiliate/review coverage, transactional inbox/outbox writes, credential outbox delivery, stable email/push queue keys and provider idempotency, shared SSE/FCM toast deduplication, and numeric order-detail links. Apply notification migrations before using the updated API and restart API, notification-worker and celery-beat together. Migration backfills do not send messages; duplicate legacy order-created notices are archived rather than deleted. Local test mode intentionally retains console email and disabled FCM; external provider delivery has not been verified. See the notification audit for channel policy and regression coverage.

Store suspension and restoration notifications go to the store owner and queue browser push when that owner has a registered device. The browser waits for its Firebase service worker to activate before registering; backend delivery uses FCM registration tokens (`tokens`, not Firebase installation IDs) and removes registrations Firebase reports as not found.

Customer order tracking reflects backend Pending, Confirmed, Shipped, Delivered, Picked up, Cancelled, and Refunded states. Terminal states replace the fulfillment tracker with a status notice; digital orders omit shipping. Digital orders are fulfilled electronically immediately into Delivered status upon purchase and cannot be transitioned to physical delivery statuses (shipped, picked up) or reverted from delivered in backoffice or merchant tools. Customer order lists and detail views refresh every 15 seconds while active to reflect staff changes. Cancellation and return actions retain the existing backend rules.

Customer payment labels derive Paid, Awaiting payment, Partial payment, and refund outcomes from authoritative `paid_total`, `refunded_total`, and `total` amounts, rather than labelling every order as paid.

Transactional email contacts use `SUPPORT_EMAIL` (default `admin@proaceintl.com`) and `ORDER_SUPPORT_EMAIL` (default `productace@proaceintl.com`), matching the storefront contacts. Sender identity uses `RESEND_FROM_EMAIL` separately. Order/refund replies go to order support; other replies go to general support. Missing contacts omit their labeled template rows.

The referral workspace at `/account/affiliates` supports enrollment, copyable `/register?ref=…` invite links, credited-signup progress, and searchable/filterable paginated referral history. Registration accepts an invite code visibly in an optional field; rewards are issued only after email verification. The server grants $25 non-withdrawable ProAce Wallet credit for up to four referred signups; additional referrals remain pending without credit, and reward issuance is serialized per affiliate to enforce the cap under concurrent signups. The displayed earned total is cumulative promotional credit, not a cash balance or ClickBank commission. `/admin/affiliates` lets backoffice operators search/filter enrolled affiliates and review referral totals, credit earned, and account status, with links to existing user management. Customer history omits referred users’ personal information; affiliate account, wallet, and referral routes reject backoffice accounts. Generated links can only target published products in active, verified stores and stop redirecting if a listing becomes unavailable. API endpoints: `/api/v1/affiliates/workspace/` (owner-scoped), `/api/v1/affiliates/referrals/` (owner-scoped, paginated), and `/api/v1/admin/affiliates/` (backoffice-only).

Digital product onboarding & variant enhancements:
- **Redundant Cover Photo Elimination & Auto-Cover**: For digital image products (artwork, wallpapers, photography), uploading a digital file automatically populates `product.image_url` if no custom cover was specified, removing redundant cover uploads. Custom promotional banners remain optional.
- **Automatic Preview Watermark Protection**: Digital image files default `digital_preview_watermark = True` to protect artwork on public storefronts with the `PROACE PREVIEW` overlay. Non-image files (PDFs, ZIPs) coerce watermark to `False`. The raw unwatermarked file is securely served only after authorized purchase via `/api/v1/orders/<id>/download/`.
- **Digital Product Options & Variants**: Digital products support options/variants (e.g., 4K Wallpaper, Mobile HD, Print-Ready Vector) with unlimited digital inventory, variant-specific prices/deltas, and gallery image mappings without physical inventory deduction during checkout.


### Performance benchmark validation

Catalog pagination now selects ordered IDs before hydrating the 24 product graphs, supported by created/ID and category/created/ID indexes (`product.0015`). Public snapshot misses use a two-second builder lease with at most 200 ms follower waiting, retaining authoritative price/stock/visibility checks; waiting falls back to an ordinary rebuild rather than stale data. Catalog image URLs are resolved once per product per response. Elasticsearch's reusable connection pool defaults to 32 per worker (`ELASTICSEARCH_CONNECTIONS_PER_NODE`, range 1–64); fuzzy search behavior and exact totals are unchanged, and partial/timed-out results use the existing database fallback.

Compose now isolates notification SSE in the internal `notification-stream` service, defaulting to one process × 32 threads (`STREAM_WORKERS` / `STREAM_THREADS`). The browser still uses `/api/notifications/stream`; Next.js routes only that exact path to `NOTIFICATION_STREAM_URL`, while authentication refresh remains on `API_URL` and shares refresh deduplication with ordinary requests. The stream process exposes only SSE and health probes, uses the same JWT/access-revocation rules, has no public port, runs no migrations, and uses a separate metrics directory. API threads remain at 2 × 32 until workload tests justify changing them. Start/rebuild the stream service with the API; non-Compose development can leave the stream URL unset to retain the single-process path. See [performance](docs/performance.md) and [deployment](docs/deployment.md).

Authenticated stream contention testing confirmed that the reduced 2-process/8-thread candidate is not a safe global default: with 20 requested notification streams it established at most 13 and timed out 51 of 1,099 catalog requests; the default 2-process/32-thread configuration established all 20 and completed 974 requests without errors. The default is retained. This local test exercised Redis-backed streams and dependency I/O, not live carrier providers or production capacity. See [performance guidance](docs/performance.md) for scope and limitations.

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

Anonymous, nontransactional Elasticsearch searches explicitly opt into the shard request cache (`SEARCH_REQUEST_CACHE_ENABLED=true`; set false to compare or disable). This caches only ID/count search results and invalidates at Elasticsearch refresh; Django still hydrates current database records for every response, including current ownership, visibility, price, stock and variants. Authenticated and transactional requests do not opt in. No additional Redis search-response TTL is introduced, fuzzy matching and exact total-hit counting are unchanged, and search requests omit unused Elasticsearch document sources. Indexing remains eventually consistent; the cache does not make search totals transactionally current.

API responses expose a generated `X-Request-ID` and bounded `Server-Timing` durations (`app`, `db`). The same-origin proxy forwards only validated diagnostics plus `X-Catalog-Cache`, appending an inclusive `proxy` duration (not proxy-only overhead). Internal request logs include bounded catalog `stage_durations_ms`, with corresponding OpenTelemetry spans when tracing is enabled. See [performance guidance](docs/performance.md) for measurement boundaries and worker/thread trials.

Cached landing and product payloads prefetch images and tags and aggregate wishlist counts in the product query. Serializer methods use an annotated count without evaluating an unnecessary per-product fallback query.

USPS live rating uses HTTPX async I/O with one bounded three-connection pool: authenticate once, then request Ground Advantage, Priority Mail and Priority Mail Express concurrently. Failure cancels sibling requests before closing the pool and returns a sanitized shipping error without invented rates. Other carriers retain their existing adapters. Tests use mock transports; live carrier latency and credentials are not established by these tests.

The API runs two Gunicorn processes with 32 request threads each by default. Async USPS calls are bridged into the synchronous request stack; the request thread waits while network operations overlap. Celery already runs background work in separate processes. Async is appropriate for independent network waits; CPU-heavy work needs process workers, and checkout/payment/inventory transactions stay synchronous and atomic. A full ASGI migration would also require async-compatible middleware/authentication, native async I/O, database connection-pooling review, and benchmarks; merely changing `def` to `async def` does not provide that migration. See [Django async guidance](https://docs.djangoproject.com/en/5.2/topics/async/) and [HTTPX async clients](https://www.python-httpx.org/async/).



Product-page interaction hooks, including share-link feedback state, are initialized before loading/error returns. This keeps hook order stable when asynchronous catalog data arrives and prevents the product page from crashing during guest browsing and checkout.

Collection refetches retain visible results and controls while a compact, accessible spinner indicates that fresh data is loading in shopper search, seller, store, backoffice, and notification listings. The staff user directory reserves space for active-filter controls so filtering does not shift results on mobile.

Catalog full-text search spans product title, brand, category, tags, and description. Multiword searches require all terms; Elasticsearch ranks title and brand matches higher and applies fuzzy matching. Searches shorter than three characters use database substring matching so a query like `k` can find `k` inside a product word; longer searches use Elasticsearch with a database fallback when it is unavailable. Product saves/deletes sync through signals, and store status or verification changes reindex the store's products after commit so public search eligibility stays current. Repair an older stale index with `python server/manage.py rebuild_product_index`. Elasticsearch search reuses one thread-safe client and its persistent connection pool per process; forked workers reset inherited clients and configuration changes replace the local pool. See [the official Python client's connection/thread guarantees](https://github.com/elastic/elasticsearch-py).

The backoffice overview shows pending merchant payouts, recent requests with detail dialogs, and the affiliate/referral board directly below the summary cards. Payout details remain available for pending, completed, and rejected requests. Authorized staff, business administrators, and technical administrators can inspect, complete, or decline pending requests from the list or details dialog. Account and routing numbers show only their first two and last two characters; legacy last-four-only values show only their final two characters. Approval initiates a Stripe Connect transfer. Bank transfers are sent outside the app and must be confirmed before marking the request completed.

Store creation includes optional store profile picture and Store label (banner/cover) uploads with cropping and previews. JPEG, PNG, and WebP images up to 5 MB use the existing protected branding endpoints after the store is created. Failed image uploads can be retried without creating another store. Creating an additional store selects it before opening the first-product editor. Creating a merchant's first store also initializes their unified merchant wallet in the same transaction; later stores share it. Stripe Express account IDs are committed before onboarding-link creation, so a temporary link failure can be retried against the same account.

Notification operations: see [worker settings and troubleshooting](docs/getting-started.md#notification-worker-settings-and-troubleshooting) and [local-to-production transition](docs/deployment.md#transitioning-notifications-from-local-to-production), including sender verification, effective backend checks, scheduler startup and production Compose environment wiring. Push retries are scoped to devices still registered to the notification recipient, so a token moved to another account will not receive the prior account's queued notice.

All example environment files include fictional format samples. Follow [the example environment guide](docs/getting-started.md#reading-the-example-environment-files) to replace them with real credentials or clear unused integrations before running the app.

Social signup imports a missing Google profile image from the verified credential into configured media storage (MinIO/S3 when enabled), preserving user-selected avatars. When tokeninfo omits the picture, the accepted ID token supplies that claim after provider verification. Google/Apple sign-in with an empty phone number prompts for a phone number and saves it through the authenticated profile endpoint before continuing; existing phones are preserved. Referral codes from the signup field, URL or remembered auth-page referral remain attached to new social signups only; existing-account logins do not create or reassign referrals. A missing Google image or unavailable image service does not block authentication and is retried on the next sign-in while the avatar remains empty.

Logout immediately aborts pending API requests and cancels account queries before push cleanup or server revocation. The proxy propagates cancellation to backend and refresh requests so a late token-refresh response cannot restore auth cookies. It expires both root-path auth cookies even when Django returns its empty HTTP 204 logout response, updates the observed session query to an anonymous value, and removes other cached account data without detaching the session observer. Unauthorized profile responses clear the displayed identity instead of retaining a previous signed-in greeting.

Customers can manage Google/Apple connections and password sign-in in profile/settings. Provider subjects resolve to a single account, verified matching emails link existing customer profiles, and disconnect preserves at least one login method. See [social account linking](docs/social-account-linking.md) for the schema, authenticated API routes, legacy account migration, security rules and frontend flow.

Settings use compact expandable sections for appearance, browser alerts, optional email preferences and sign-in methods. Signed-in users can enable or disable push alerts for the current device in App Settings or the backoffice notification menu; both controls stay synchronized and wait for the Firebase service worker to activate before registering the device. Unsupported browsers and blocked permissions are explained in the UI. Authentication pages remain viewable while signed in, with email/password above horizontal Google/Apple alternatives. Sign-in and registration controls are disabled during session loading or an active session; an explicit sign-out action permits account switching. The backend rejects login, registration and public social sign-in attempts carrying a valid current session with HTTP 409, while expired/revoked credentials can recover through normal sign-in. Existing authentication throttling remains active. Password recovery and authenticated provider linking remain available.

Treasury destination selectors keep bank and Stripe account management available even when no default is selected or no accounts are saved. Choose account opens the selector; empty states stay inside it, with compact add/manage actions and edit/default/delete controls for saved accounts.

Treasury withdrawal references expose a hover/focus summary and open a printable details dialog. The Payout accounts page uses explicit default badges and compact per-account Actions menus for editing, deleting, and setting the default.

Saved bank and Stripe account lists share a compact filtering toolbar: debounced search with field-specific placeholders, default-account selection, recent/name sorting, matched counts, and a conditional Clear filters action. Filtering uses the complete owner-scoped saved collection.

Bank account list requests return both default and non-default accounts when `is_default` is omitted. The default-account filter is applied only when explicitly supplied; switching a default remains visible after list refresh.

Payout account actions prevent overlapping mutations and report successful default/deletion changes. Pickers discard selections that disappear from refreshed account lists. Unified merchant payout history applies search, status, method, date and amount criteria before pagination, with deterministic creation/ID ordering.

Merchant bank-transfer payout requests require an owner-scoped saved bank account or legacy bank-name/account-number details before reserving funds. Bank account IDs are rejected for other payout methods.

Open payout-account Actions menus layer above neighboring account controls so Edit/Delete/Set default remain clickable in multi-account lists.

Merchant payout requests use the treasury-style compact amount/note form and shared bank destination picker. Change/Choose account opens the saved-account management popup instead of embedding full account cards in the withdrawal form. Saved bank accounts are user-provided destinations, not independently bank-verified accounts.

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


The admin dashboard Refund operations preview uses a full-width, horizontally scrollable
refund table: refund/order links open their detail dialogs, with customer, amount, method,
status, reason, created date and existing approve/decline actions in separate columns.
The preview retains the latest five requests; View all refunds opens the searchable,
filterable full history. Styling uses shared table, button and status primitives in both themes.


The dashboard operations previews are stacked at full width: Refund operations first,
then Coupon operations. Coupons use a scrollable table with code/detail link, discount,
usage, status, validity dates, creator email and existing toggle/delete controls.
Used-coupon deletion protection and the full searchable coupon history are unchanged.
Backoffice refund listings (overview and full history) and refund detail dialogs show the processing staff or administrator's email under “Processed by” after an action. Attribution comes from the backend's recorded refund processor; pending or older records without a processor show no invented identity. This field is exposed only through the existing backoffice refund serializer and access controls.
App-wide audit fixes (2026-10-15): merchant order history resolves recorded snapshot/fulfillment membership, with live-cart fallback for legacy records. Merchant shipment events are store-scoped; delivery addresses appear only for that store's physical items. Digital download links include an encoded `variant` selector when required and resolve only purchased order lines; legacy single-item links remain supported. Guest physical carts display “Calculated at checkout” and keep totals limited to item costs until the backend quotes delivery. Failed refund attempts retain the operator email, timestamp and reason, while customer/backoffice payloads use safe failure text, including for older failed records. Malformed password-reset identifiers return validation errors. The security runner requires expected live response statuses, uses the current protected routes, treats unreachable probes as failures and exits nonzero on failure. Run `.venv/bin/pytest scripts/qa/test_security_reports.py` for offline runner regressions in addition to the standard test suites.
The security runner, its offline regression tests and shared report helper are explicitly exempted from the local `scripts/` ignore rule so their fixes can be versioned; generated `qa-reports/` output remains ignored.
Order-list latency optimization (2026-10-15): customer and merchant histories batch related refunds and fulfillments per page, and snapshot-backed merchant orders avoid current-cart reads. Query counts remain bounded as page size grows, without shared caching of private data. See [latency and query performance](docs/performance.md) for the offline regression command and live-measurement limits.


Checkout address dialogs use the shared address form in embedded mode, without a
second card or repeated heading. Address rows share label/input/error tracks to keep
controls aligned when labels or validation messages wrap, and stack on narrow screens.
Standalone address forms retain their heading and card; both modes use theme tokens.

The dedicated notification-stream image installs `server/requirements-stream.txt`
and returns database connections to a PostgreSQL pool capped at four physical
connections per stream worker (three-second acquisition timeout). Non-Compose
dedicated stream deployments must install this extra dependency as well.

Guest cart and saved-item persistence is optional: blocked/full browser storage
keeps the active in-memory session usable. Public catalog GETs can recover
anonymously from refresh-service transport or parsing failures without clearing
still-valid refresh cookies; private reads and writes never receive that fallback.
Malformed affiliate product paths return 404, malformed review moderation IDs
return 400, and listing end dates must be earlier than `9999-12-31`. See
[frontend](docs/frontend.md) and [backend](docs/backend.md) for regression coverage.


Signed-out visitors to `/orders/<id>` are redirected to `/login?next=...` after the
session check, then returned to that order after authentication. A signed-in viewer
without access sees an unavailable-order message with Your orders and an explicit
Switch account action. Switching uses normal logout before opening sign-in and retains
the order return path. Missing and inaccessible orders share the same safe 404 response;
no owner identity is revealed. Expired-session 401s return to sign-in, while other order
loading failures show a generic retry message without exposing backend internals.

The customer order detail header centers the order status above the Print receipt action, with consistent spacing on desktop and mobile.

Order refund forms use compact item rows with separate titles, quantities and amounts, theme-aware separators, and wrapping actions. The shopping action is hidden while a refund request is being edited.
