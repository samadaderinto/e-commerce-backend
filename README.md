# Proace Commerce

A Next.js marketplace and Django API in one base repository.

```text
client/                 Next.js frontend app, client docs and client container
client/Documentation/   Frontend-local docs
server/                 Django API and backend containers
docs/                   Root architecture and cross-project docs
.github/                CI/CD and HostGator VPS deployment workflow
package.json            npm workspace and root frontend commands
```

The previous `codematics/` backend directory is now `server/`. The Python settings
package inside it is still named `codematics`. Existing backend work was moved,
not replaced. The runnable commerce configuration is
`codematics.storefront_settings`; the legacy settings remain available separately.

## Code Documentation

Backend and cross-project documentation is centralized in [`docs/`](docs/README.md).
The client also has frontend-local docs:

- client docs: [`client/README.md`](client/README.md)

New contributors should start with the
[getting-started guide](docs/getting-started.md), then read the
[architecture and API map](docs/architecture.md). The `docs/` pages are the
canonical guides for the backend and cross-project details.

When changing code, update the matching doc in the same pass:

- frontend routes/components/API behavior: [`docs/frontend.md`](docs/frontend.md);
- backend apps/models/serializers/views/auth/tests: [`docs/backend.md`](docs/backend.md);
- Docker, Postgres, Redis, Kafka, Nginx, storage or deployment:
  [`docs/infrastructure.md`](docs/infrastructure.md);
- health, metrics, logs, traces, profiling, Grafana, Loki, Prometheus, Tempo or
  Alloy: [`docs/observability.md`](docs/observability.md).
- client-specific changes should also update `client/Documentation/`;

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
Email verification and password-reset links print to the API terminal locally.
Set `FRONTEND_URL=http://127.0.0.1:3000` to keep email links on that exact host.

## Run The Container Stack

You can run the entire application (Next.js frontend, Django API, Celery worker, PostgreSQL, Redis, and Elasticsearch) with the unified Compose stack, or run individual stacks independently:

### Option A: Full Application Stack (Frontend + Backend + Datastores)
From the repository root:

```sh
# Build and run the entire stack
docker compose up --build -d

# Check services status
docker compose ps
```

The Next.js storefront will be available at <http://127.0.0.1:3000>, and the Django API at <http://127.0.0.1:8000>.

### Option B: Backend Stack Only
From the `server/` directory:

```sh
cd server
../.venv/bin/python monitoring/init_local.py
docker compose --env-file .env -f compose.yaml up --build -d api redis postgres elasticsearch
docker compose --env-file .env -f monitoring/compose.yaml up -d
docker compose --env-file .env -f compose.yaml exec api python manage.py rebuild_product_index
```

### Option C: Frontend Stack Only
From the repository root:

```sh
docker compose -f client/compose.yaml up --build -d
```

The API uses `redis://redis:6379/0` inside Compose. The API is available at
<http://127.0.0.1:8000>, Redis is bound to `127.0.0.1:6379`, Grafana is at
<http://127.0.0.1:3002>, and Prometheus is at <http://127.0.0.1:9090>. PostgreSQL
is available at `127.0.0.1:5432`, Elasticsearch is at `127.0.0.1:9200`, and both
persist in named Docker volumes. The Grafana password and metrics token live in
`server/.env`. Log aggregation is part of this stack too: Alloy collects Docker
container stdout and sends it to Loki, which is available in Grafana Explore.

Check both stacks and follow their logs:

```sh
docker compose -f compose.yaml ps
docker compose -f monitoring/compose.yaml ps
docker compose -f compose.yaml logs -f api redis
```

In Grafana, open Explore, select Loki, and query API logs with:

```logql
{service_name="api"}
{service_name="api"} | json | level="ERROR"
```

The API health endpoint is <http://127.0.0.1:8000/health/live/>. Stop the
application and monitoring stacks with:

```sh
docker compose -f compose.yaml down
docker compose -f monitoring/compose.yaml down
```

Kafka and RabbitMQ are optional and are disabled by default. Start them only for
queue-consumer work with:

```sh
docker compose -f monitoring/compose.yaml --profile messaging up -d kafka rabbitmq
```

For production, use the HostGator VPS environment and GitHub Actions secrets,
not checked-in env files. Full deployment details are in [`server/deployment.md`](server/deployment.md) and
[`server/monitoring/README.md`](server/monitoring/README.md).

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
- **Order Tracking**: Real-time USPS package tracking with dynamic carrier links (`https://tools.usps.com/...`), live status badges, and shipping milestones.
- **ProAce Wallet & Refunds**: Integrated customer wallet balance with 7-day physical return window, supporting instant store credit refund resolution.
- **Flexible Checkout**: Supports Cash-on-Delivery, ProAce Wallet balance, and Stripe Wallet payments with transactional stock deductions and idempotent retry handling.

## Seller Experience

Visit `/merchant` after signing in:
- **Seller Workspace Dashboard**: Daily order activity trend bar charts, low-stock inventory alerts, top-selling products, and tier milestone celebration banners.
- **Product Management & Variants**: Create physical and digital goods, define customizable variant options with price deltas and individual stock allocations, set flash sale timers, and upload image galleries.
- **Bulk CSV Catalog Import**: High-volume merchant catalog batch upload with automatic variant and tag parsing.
- **Storefront Customization**: Configure store announcement banner, banner covers, avatars, bio, and direct customer inquiry channels.
- **Escrow & Wallet Management**: 7-day review escrow holding net sales from new orders, transparent 4% platform commission calculation, available balance release, and withdrawal requests (`/merchant/payouts`).
- **Order Fulfillment**: Review store-specific customer orders, assign carrier & tracking numbers, update fulfillment milestones, and trigger instant buyer notifications.

## Admin & Staff Experience

Visit `/admin` (Platform Intelligence) and `/admin/staff` (Team Administration):
- **Executive Analytics Dashboard**: Platform gross revenue, order volume, active user growth, and store fleet health across 7/30/90/365-day periods.
- **Order Status Distribution Chart**: Visual fulfillment pipeline breakdown across order lifecycle stages.
- **Moderation Queues**: Review 7-day customer refund requests (approve to wallet store credit or decline with reasons) and merchant payout requests.
- **Store Moderation**: Review pending store onboardings, approve verified sellers, or suspend non-compliant stores with instant catalog cache invalidation.
- **Staff Provisioning (Superusers)**: Create new staff accounts, manage access levels, or block compromised accounts.

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

## Verification & Testing

```sh
# Frontend build & typechecks (from root or via prefix)
npm run build                     # or npm --prefix client run build
npm run typecheck
npm run test:unit

# Backend test suite (Django & Pytest)
PYTHONPATH=server .venv/bin/pytest server/storefront/tests.py server/store/tests.py
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
  `server/monitoring/compose.yaml` with centralized dashboards at `http://127.0.0.1:3002`.
- Product photos and media uploads are persisted in named volumes or S3-compatible
  object storage (MinIO/AWS S3).
