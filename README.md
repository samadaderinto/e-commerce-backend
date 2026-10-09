# Proace Commerce

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
- **Seller Tier Badges**: Dynamic verification tick and rank badges (Starter 🔵, Booster ⚪, Accelerator 🟣, Power 🟢, Mega 💎, Legendary 👑, and Official 🟡).
- **ClickBank Affiliate & Partner Offers**: Seamless integration of external ClickBank partner products coexisting alongside native marketplace listings. Features partner badges, custom CTA labels ("Buy on Partner Site"), and transparent partner fulfillment notes. Secure outbound routing via `/api/affiliates/clickbank/outbound/<id>` attaches tracking tokens (`tid=cb_*`) and logs outbound clicks while blocking local cart checkout.
- Saved items and persistent guest bag with automatic guest-to-account merge on sign-in.
- Email-verified registration, sign-in, password reset, and session management.
- Profile, delivery addresses, order history, and detailed order pages.
- **Order Tracking**: Recorded fulfillment milestones and official USPS, UPS, FedEx, and DHL tracking links. Shipping service and carrier quotes are preserved in each order.
- **In-App Password Management**: In-dialog password updates (`/api/v1/password/change/`) verifying current passwords and enforcing secure credential hygiene.
- **ProAce Wallet, Top-Ups & Refunds**: Integrated customer wallet balance with Stripe Checkout top-up sessions (`/api/v1/wallet/topup-session/`), 7-day physical return window, and instant store credit refund resolution.
- **Order Cancellation**: Self-service shopper cancellation for unfulfilled orders with atomic variant inventory restock, merchant earnings reversal, and refunds limited to actual wallet/card payments.
- **Flexible Checkout**: Supports Cash-on-Delivery, ProAce Wallet balance, and Stripe Wallet payments with transactional stock deductions and idempotent retry handling.

## Seller Experience

Visit `/merchant` after signing in:
- **Seller Workspace Dashboard**: Daily order activity trend bar charts, low-stock inventory alerts, top-selling products, and tier milestone celebration banners.
- **Product Management & Variants**: Create physical goods, digital assets, or ClickBank affiliate offers. Configure custom variant matrices with price deltas and individual stock allocations, flash sale timers, HopLink targets, and MinIO photo galleries.
- **Partner Offer Configuration**: Publish ClickBank affiliate listings with direct HopLink URLs, vendor account nicknames, and custom landing CTA buttons, with automatic bypassing of physical shipping and variant restrictions.
- **Bulk CSV Catalog Import**: RFC 4180-compliant batch upload supporting quotes, multiline values, variants, and tags.
- **Storefront Customization**: Configure store announcement banner, banner covers, avatars, bio, and direct customer inquiry channels.
- **Escrow & Wallet Management**: 7-day review escrow holding net sales from new orders, transparent 4% platform commission calculation, available balance release, and withdrawal requests (`/merchant/payouts`). Official company stores automatically consolidate 100% of retail sales into Platform Treasury.
- **Order Fulfillment**: Review store-specific customer orders, assign carrier & tracking numbers, update fulfillment milestones, and trigger instant buyer notifications.

## Admin & Staff Experience

Visit `/admin` (Platform Intelligence), `/admin/commission` (Platform Treasury), and `/admin/staff` (Team Administration):
- **Executive Analytics Dashboard**: Platform gross revenue, order volume, active user growth, and store fleet health across 7/30/90/365-day periods.
- **Order Status Distribution Chart**: Visual fulfillment pipeline breakdown across order lifecycle stages.
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

# 2. Frontend Unit Tests (24 tests via Node native runner)
npm run test:unit

# 3. Backend Test Suite (Django / Pytest: 294 tests; 286 passed, 8 environment-dependent skips offline)
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

Transactional service emails cover store verification, blocking (including the review reason), and restoration; administrative account suspension/restoration and backoffice permission changes; successful password changes/resets; and low physical stock for the store owner and authorized operators. Store, account-security, and inventory notices use branded HTML templates through the existing delivery outbox. No-op moderation/access requests do not resend notices. When a dedicated receipt is sent for checkout, shipment/delivery, refund decisions, cancellation, wallet top-ups, or payout decisions, the companion inbox notification suppresses its generic email while retaining inbox and push delivery. Delivery requires the configured email provider and notification worker; local console delivery does not send real email.

Inbox notifications and their email/push outbox rows are persisted in one database transaction. Worker dispatch waits until commit, so rollback removes both and broker outages leave persisted deliveries available for recovery.

Store settings use plain customer-facing labels for store branding, the logo URL, cover image URL, and store announcement. Design references are kept out of the settings interface.

Email receipts display actual order snapshot and recipient data. Missing personal details are omitted; digital-only orders omit delivery address sections and physical-shipment language. Delivery notices report recorded status and never include sample verification codes, names, addresses, phone numbers, carrier values, or product photos.
