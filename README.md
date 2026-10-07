# Proace Commerce

A Next.js marketplace and Django API in one base repository.

```text
client/                 Next.js 15 App Router frontend and browser UI
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
.venv/bin/python server/manage.py seed_demo --settings=codematics.storefront_settings --password 'ProaceDemo2026!'
# Or generate realistic high-volume marketplace load (~150 products, ~350 orders):
# .venv/bin/python server/manage.py populate_fake_data --scale standard
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
- Saved items and persistent guest bag with automatic guest-to-account merge on sign-in.
- Email-verified registration, sign-in, password reset, and session management.
- Profile, delivery addresses, order history, and detailed order pages.
- **Order Tracking**: Recorded fulfillment milestones and official USPS, UPS, FedEx, and DHL tracking links. Shipping service and carrier quotes are preserved in each order.
- **In-App Password Management**: In-dialog password updates (`/api/v1/password/change/`) verifying current passwords and enforcing secure credential hygiene.
- **ProAce Wallet, Top-Ups & Refunds**: Integrated customer wallet balance with Stripe Checkout top-up sessions (`/api/v1/wallet/topup-session/`), 7-day physical return window, and instant store credit refund resolution.
- **Order Cancellation**: Self-service shopper cancellation for unfulfilled orders with atomic physical inventory restock and wallet balance refund.
- **Flexible Checkout**: Supports Cash-on-Delivery, ProAce Wallet balance, and Stripe Wallet payments with transactional stock deductions and idempotent retry handling.

## Seller Experience

Visit `/merchant` after signing in:
- **Seller Workspace Dashboard**: Daily order activity trend bar charts, low-stock inventory alerts, top-selling products, and tier milestone celebration banners.
- **Product Management & Variants**: Create physical and digital goods, define customizable variant options with price deltas and individual stock allocations, set flash sale timers, and upload image galleries.
- **Bulk CSV Catalog Import**: RFC 4180-compliant batch upload supporting quotes, multiline values, variants, and tags.
- **Storefront Customization**: Configure store announcement banner, banner covers, avatars, bio, and direct customer inquiry channels.
- **Escrow & Wallet Management**: 7-day review escrow holding net sales from new orders, transparent 4% platform commission calculation, available balance release, and withdrawal requests (`/merchant/payouts`).
- **Order Fulfillment**: Review store-specific customer orders, assign carrier & tracking numbers, update fulfillment milestones, and trigger instant buyer notifications.

## Admin & Staff Experience

Visit `/admin` (Platform Intelligence) and `/admin/staff` (Team Administration):
- **Executive Analytics Dashboard**: Platform gross revenue, order volume, active user growth, and store fleet health across 7/30/90/365-day periods.
- **Order Status Distribution Chart**: Visual fulfillment pipeline breakdown across order lifecycle stages.
- **Moderation Queues**: Review 7-day customer refund requests, moderate or remove abusive product reviews, and approve/reject merchant payout requests (`/admin/staff/payouts`).
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
Production cookies require HTTPS.

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

# 2. Frontend Unit Tests (19 tests via Node native runner)
npm run test:unit

# 3. Backend Test Suite (Django / Pytest — 184 passing tests)
.venv/bin/pytest server/
```

### Tier 2: Integration & End-to-End Suites (Live Dev Servers)
Run with the backend (`python server/manage.py runserver 127.0.0.1:8000`) and frontend (`npm run dev`) running with seeded demo data (`manage.py seed_demo`):

```bash
# Next.js API proxy integration tests
npm run test:integration

# Playwright browser end-to-end test suite (Desktop & Mobile)
npm run test:e2e
```

Unit tests exercise frontend API serialization/error handling, currency formatting,
categories, and backend price rounding without making external service calls.
Backend tests cover authentication, permissions, cart atomicity, coupon redemption,
wallet transactions, 7-day refund escrow, USPS tracking, review photo validations,
variants serialization, flash sale countdowns, and merchant payouts.

## Deployment Boundaries

- Set `DJANGO_DEBUG=false`, a strong `SECRET_KEY`, `ALLOWED_HOSTS`, `FRONTEND_URL`,
  Resend API/sender configuration, and persistent media/database storage. Build
  the client with `npm run build` (or `npm --prefix client run build`) and run `npm run start --workspace=client`
  behind HTTPS.
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
