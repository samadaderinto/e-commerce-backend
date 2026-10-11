# Proace Commerce

`client/tests/filter-stability.spec.ts` exercises delayed filter responses for guests, shoppers, buyers, sellers, merchants, staff, business administrators, and technical administrators on desktop and mobile. It verifies retained results, typing focus, mounted controls, same-document shop history, and customer profile stability.

Notification search, tabs, and category filters retain results within the same account and store. Backoffice filter caches and private product previews include the viewer identity; login cancels outstanding queries and clears the prior query cache before activating the new account. External payment and onboarding redirects remain full navigations.

Shop filters update browser history without route navigation. Filtered catalog, merchant, and backoffice queries retain current results while fetching and show a local update status; store and account detail queries discard previous results when the selected entity changes.

Catalog responses expose the backend `visibility` flag. The product page shows the draft preview banner only for explicit `visibility: false`; missing metadata is not evidence of a draft. Hidden products return 404, and unverified-store previews require the store owner or an authorized operator, even with `?preview=1`.

Shared frontend styling in `client/src/app/design-system.css` standardizes form controls, buttons, cards, dialogs, catalog typography, and ClickBank partner badges across light and dark themes. Mobile controls use readable input sizes, touch devices expose quick product actions, and reduced-motion preferences are respected.

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

Run the API and client in separate terminals:

```sh
.venv/bin/python server/manage.py runserver 127.0.0.1:8000 --settings=codematics.storefront_settings
```

```sh
npm run dev
```

Open <http://127.0.0.1:3000>. The client defaults to
`http://127.0.0.1:8000/api/v1`; override `API_URL` in `client/.env` when needed.
Customer email verification and password-reset links print to the API terminal with the local console email backend. Staff credential issuance requires a private email backend such as Resend or SMTP.
Set `FRONTEND_URL=http://127.0.0.1:3000` to keep email links on that exact host.

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
docker compose -f server/compose.yaml up --build -d api redis postgres elasticsearch
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
- **Product Variants**: Selectable size, color, and material options with real-time price delta and inventory updates.
- **Verified Reviews & Photos**: In-place review submission and 1–3 photo uploads exclusively for verified product purchasers, with real-time rating updates and photo gallery lightbox.
- **Flash Deals & Live Countdowns**: Urgency badges and real-time countdown clocks on limited-time discounts.
- **Store Profiles & Announcements**: Dedicated merchant showcase pages with marquee announcements, pinned items, and direct "Message Store" contact actions.
- **Seller Tier Badges**: Dynamic verification tick and rank badges (Starter 🔵, Booster ⚪, Accelerator 🟣, Power 🟢, Mega 🟠, Legendary 👑, and Official 🟡).
- **ClickBank Affiliate & Partner Offers**: Seamless integration of external ClickBank partner products coexisting alongside native marketplace listings. Features partner badges, custom CTA labels ("Buy on Partner Site"), and transparent partner fulfillment notes. Secure outbound routing via `/api/affiliates/clickbank/outbound/<id>` attaches tracking tokens (`tid=cb_*`) and logs outbound clicks while blocking local cart checkout.
- Saved items and persistent guest bag with automatic guest-to-account merge on sign-in.
- Email-verified registration, sign-in, password reset, and session management.
- **Google & Apple Social Authentication**: One-click customer registration and sign-in with Google or Apple identity tokens, dual-theme WCAG high-contrast buttons, strict security guardrails (administrative and staff accounts cannot sign in via social providers), and seamless affiliate referral synchronization awarding \$25 promotional store credit to referring marketers on new customer social signups.
- **Product Sharing & Instant Link Copy**: One-click Share button integrated into product purchase actions, rating header, and operator/merchant preview banners. Supports native Web Share API with clipboard copy fallback, dynamic "Copied!" feedback, and toast notifications across both public product pages and draft preview modes.
- Profile, personal avatars with circular 512x512 crop dialog, delivery addresses, order history, and detailed order pages.
- **User Avatar & Photo Management**: Profile picture upload with client-side circular crop tool (`UserAvatarCropDialog`), 512x512 server validation, MinIO media persistence, managed centrally in Personal details (`/account/profile`) with instant reflection across customer account, merchant workspaces, and backoffice staff tables.
- **App Settings & Email Preferences**: Global `/settings` page supporting theme customization (Light / Dark / System) with an authenticated user section for **Email communication preferences** (opting in/out of product recommendations and promotional marketing emails via `/api/v1/me/`).
- **Order Tracking & Dual-Theme Milestone Tracker**: Dynamic 3-stage fulfillment tracker (Confirmed, Shipped, Delivered) with WCAG-compliant high-contrast rendering across light and dark modes, and official USPS, UPS, FedEx, and DHL tracking links. Shipping service and carrier quotes are preserved in each order.
- **In-App Password Management**: In-dialog password updates (`/api/v1/password/change/`) verifying current passwords and enforcing secure credential hygiene.
- **ProAce Wallet, Top-Ups & Refunds**: Integrated customer wallet balance with Stripe Checkout top-up sessions (`/api/v1/wallet/topup-session/`), 7-day physical return window with per-product claim idempotency (declined and processed items cannot be re-requested), and instant store credit refund resolution.
- **Order Cancellation**: Self-service shopper cancellation for unfulfilled physical orders within 12 hours of placement, with atomic variant inventory restock, merchant earnings reversal, and refunds limited to actual wallet/card payments (instant digital downloads are non-cancellable).
- **Flexible Checkout**: Supports Cash-on-Delivery, ProAce Wallet balance, and Stripe Wallet payments with transactional stock deductions and idempotent retry handling.

## Seller Experience

Visit `/merchant` after signing in:
- **Seller Workspace Dashboard**: Daily order activity trend bar charts, low-stock inventory alerts, top-selling products, and tier milestone celebration banners.
- **Product Management & Variants**: Create physical goods, digital assets, or ClickBank affiliate offers. Configure custom variant matrices with price deltas and individual stock allocations, flash sale timers, HopLink targets, and MinIO photo galleries.
- **Partner Offer Configuration**: Publish ClickBank affiliate listings with direct HopLink URLs, vendor account nicknames, and custom landing CTA buttons, with automatic bypassing of physical shipping and variant restrictions. Partner listings enforce partner-controlled pricing (locking platform discounts to 0% and omitting flash sale countdowns to avoid fictitious price discrepancies).
- **Bulk CSV Catalog Import**: RFC 4180-compliant batch upload supporting quotes, multiline values, variants, and tags.
- **Storefront Customization**: Configure store announcement banner, banner covers, avatars, bio, and direct customer inquiry channels.
- **Escrow & Wallet Management**: 7-day review escrow holding net sales from new orders, transparent 4% platform commission calculation, available balance release, and withdrawal requests (`/merchant/payouts`). Official company stores automatically consolidate 100% of retail sales into Platform Treasury.
- **Order Fulfillment**: Review store-specific customer orders, assign carrier & tracking numbers, update fulfillment milestones, and trigger instant buyer notifications.

## Admin & Staff Experience

Visit `/admin` (Platform Intelligence), `/admin/commission` (Platform Treasury), and `/admin/staff` (Team Administration):
- **Executive Analytics Dashboard**: Platform gross revenue, order volume, active user growth, and store fleet health across 7/30/90/365-day periods.
- **Order Status Distribution Chart**: Visual fulfillment pipeline breakdown across order lifecycle stages.
- **Customer Order Audit & Emergency Controls**: Centralized order management (`/admin/orders`) with status overrides, tracking inspection, and multi-dimensional filtering across order status, payment tender, and delivery courier (USPS, UPS, FedEx, DHL, Digital).
- **Moderation & Payout Queues**: Review 7-day customer refund requests, moderate or remove abusive product reviews, and approve/reject third-party merchant payout requests (`/admin/payouts`).
- **Platform Treasury & Commission Wallet**: Unified corporate finance ledger (`/admin/commission`) consolidating marketplace 4% fee commissions and 100% of official company store retail sales with audited withdrawal workflows.
- **Store Moderation**: Review pending store onboardings, approve verified sellers, or suspend non-compliant stores with instant catalog cache invalidation.
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

# 2. Frontend Unit Tests (28 tests via Node native runner)
npm run test:unit

# 3. Backend Test Suite (Django / Pytest: 386 tests; 377 passed, 9 environment-dependent skips offline)
.venv/bin/pytest server/
```

### Tier 2: Integration & End-to-End Suites (Live Dev Servers)
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

The unsaved product preview displays variant options with selectable prices and images, plus the configured flash deal countdown in the product price block. Expired draft deals show an explanation instead of disappearing.

Anonymous API failures cannot clear cookies set by a concurrent successful login; authenticated failures still expire invalid sessions.

Backoffice navigation uses a dedicated responsive icon navigation row with active-page highlighting, separate from account controls. Overview destinations appear once in the same horizontally scrollable navigation row, including merchant payouts, users, administrator commission withdrawals, and technical-admin Grafana metrics. Required admin and staff password changes use a focused security card with password confirmation and a visibility toggle.

Store onboarding requires a complete business address (street, city, state/region, country and postal code). Products may be saved as drafts, but manual and scheduled publication require that address for both digital and physical listings.

Purchase validation also rejects existing stores without a complete default business address, including digital-only stores. Missing physical shipment origins return a validation error rather than silently using Tampa.

Time handling: Django stores timezone-aware UTC instants (`TIME_ZONE=UTC`, `USE_TZ=True`). Browser date/time inputs display local time and submit ISO UTC timestamps. Dashboard requests accept a validated IANA `time_zone` (UTC by default); the browser supplies its timezone for local calendar-day reporting. Date-only chart labels are preserved without timezone shifts. Cron and carrier request clocks use aware UTC; flash countdowns include minutes.

Military postal delivery: APO/FPO/DPO destinations use USPS only with the currently supported integrations. Checkout disables other carrier options and the server rejects unsupported carriers in both demo and live rating and payment flows. Address city/state/ZIP must agree: AA uses 340xx, AE uses 090xx–098xx, AP uses 962xx–966xx, with country United States. This is a supported-service policy, not a claim that all commercial postal handoff services are prohibited: UPS Ground Saver and Mail Innovations have military-address support but are not integrated here. See [USPS military addressing standards](https://pe.usps.com/text/dmm300/703.htm) and [UPS supported services](https://www.ups.com/us/en/support/shipping-support/print-shipping-labels/how-to-write-address). ZIP blocks alone do not guarantee an active destination or eligibility for every USPS service; live carrier availability and military mail content/customs requirements still apply.

Commerce safety: split-tender checkout reserves wallet funds and records recoverable Stripe attempts with 30-minute expiry; Celery Beat retries failed refunds and releases abandoned holds. Cart lines persist variants, merchant refund debt is retained, destination sales tax is computed via a hybrid database & Stripe Tax engine, and buyer digital downloads are authenticated streams. Apply the new cart/payment migrations before running the updated app. See [audit remediation](docs/security-audit-remediation.md) for recovery behavior, import limits and verification boundaries.

Commerce bug-audit fixes persist settled tender amounts, allocated coupon/tax line totals, cumulative refunds, store-scoped fulfillment, and unique wallet funding receipts. Apply `python server/manage.py migrate` before running the updated backend, then restart API/Celery processes. COD supports physical goods only and never grants paid balances or digital access. See [the remediation and verification record](docs/bug-audit-2026-10-08.md) and [backend accounting rules](docs/backend.md).

Transactional service emails cover store verification, blocking (including the review reason), and restoration; administrative account suspension/restoration and backoffice permission changes; successful password changes/resets; and low physical stock for the store owner and authorized operators. Store, account-security, and inventory notices use branded HTML templates through the existing delivery outbox. No-op moderation/access requests do not resend notices. When a dedicated receipt is sent for checkout, confirmation, shipment/delivery/pickup, refund decisions, cancellation, wallet top-ups, or payout decisions, the companion inbox notification suppresses its generic email while retaining inbox and push delivery. Delivery requires the configured email provider and notification worker; local console delivery does not send real email.

Inbox notifications and their email/push outbox rows are persisted in one database transaction. Worker dispatch waits until commit, so rollback removes both and broker outages leave persisted deliveries available for recovery.

Store settings use plain customer-facing labels for store branding, the logo URL, cover image URL, and store announcement. Design references are kept out of the settings interface.

Email receipts display actual order snapshot and recipient data. Missing personal details are omitted; digital-only orders omit delivery address sections and physical-shipment language. Delivery notices report recorded status and never include sample verification codes, names, addresses, phone numbers, carrier values, or product photos.

ClickBank offer prices are retained only as internal catalog references. Public product cards, detail pages, and listing previews direct shoppers to check the current price on the partner site. Selecting the ClickBank listing type hides ProAce discount and flash-deal controls; the server rejects those promotions and clears them when converting a standard listing.

Store profile pages (`/shop?store=<id>`) list only that store’s products. Filter resets retain the store and any `preview=1` mode; previews remain read-only.

The catalog supports 29 departments shared by homepage category tiles, shop/store filters, and merchant product forms: Electronics, Fashion, Phones, Computing, Sports & outdoors, Books, Toys & games, Kids & baby, Home & living, Kitchen & dining, Beauty & personal care, Health & wellness, Pet supplies, Gaming, Tablets, Fishing, Lingerie & sleepwear, Coffee, tea & drinks, Garden & tools, Automotive, Jewelry & watches, Software & apps, Courses & learning, Templates & planners, Design assets, Photos & video, Music & audio, Business resources, Digital tools & presets. New department keys are validated by Django product choices; apply product migrations before using them. Existing product category keys are preserved.

Backoffice user profiles use a compact identity card with contact and activity details, three financial summary cards, and bordered wallet, activity, and order panels. The layout stacks on smaller screens and respects the active theme.

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

Customer order tracking reflects backend Pending, Confirmed, Shipped, Delivered, Picked up, Cancelled, and Refunded states. Terminal states replace the fulfillment tracker with a status notice; digital orders omit shipping. Digital orders are fulfilled electronically immediately into Delivered status upon purchase and cannot be transitioned to physical delivery statuses (shipped, picked up) or reverted from delivered in backoffice or merchant tools. Customer order lists and detail views refresh every 15 seconds while active to reflect staff changes. Cancellation and return actions retain the existing backend rules.

Customer payment labels derive Paid, Awaiting payment, Partial payment, and refund outcomes from authoritative `paid_total`, `refunded_total`, and `total` amounts, rather than labelling every order as paid.

Transactional email contacts use `SUPPORT_EMAIL` (default `admin@proaceintl.com`) and `ORDER_SUPPORT_EMAIL` (default `productace@proaceintl.com`), matching the storefront contacts. Sender identity uses `RESEND_FROM_EMAIL` separately. Order/refund replies go to order support; other replies go to general support. Missing contacts omit their labeled template rows.

The referral workspace at `/account/affiliates` supports enrollment, copyable `/register?ref=…` invite links, credited-signup progress, and searchable/filterable paginated referral history. Registration accepts the invite code visibly in an optional field. The server grants $25 non-withdrawable ProAce Wallet credit for up to four referred signups; additional referrals remain pending without credit. The displayed earned total is cumulative promotional credit, not a cash balance or ClickBank commission. `/admin/affiliates` lets backoffice operators search/filter enrolled affiliates and review referral totals, credit earned, and account status, with links to existing user management. Customer history omits referred users’ personal information. API endpoints: `/api/v1/affiliates/workspace/` (owner-scoped) and `/api/v1/admin/affiliates/` (backoffice-only).

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

The inventory check uses 20 separate buyers making real checkout requests against five units in a uniquely named PostgreSQL test database. It asserts five successful orders, fifteen stock rejections, and zero remaining stock. It never uses live commerce carts or products. The database is created and removed by Django's test runner. Run it through the existing API container:

```bash
.venv/bin/python scripts/qa/inventory_check.py
INVENTORY_TEST_JUNIT=qa-reports/performance-testing/stress/inventory-check-<timestamp>.xml npm run test:stress
.venv/bin/pytest scripts/qa/test_performance_reports.py
```

The stress runner accepts only a completed matching inventory test case from a JUnit artifact less than one hour old. Missing or skipped inventory evidence yields INCOMPLETE when performance otherwise passes. SQLite offline runs skip the PostgreSQL contention test explicitly.


Catalog review counts use a scalar subquery so page totals do not group the full catalog. Worker-count tuning must be benchmarked against the actual deployment: increasing local workers did not improve tail latency in this environment, so the shipped two-worker, 32-thread configuration is retained.


Product-page interaction hooks, including share-link feedback state, are initialized before loading/error returns. This keeps hook order stable when asynchronous catalog data arrives and prevents the product page from crashing during guest browsing and checkout.
