# ProAce Commerce

ProAce is a multi-vendor marketplace with a customer storefront, merchant workspace,
and staff backoffice. The repository contains a Next.js frontend and a Django REST
API, with PostgreSQL, Redis, Elasticsearch, object storage, and optional monitoring.

## Start here

- [Getting started](docs/getting-started.md): installation, environment, and demo accounts.
- [Documentation index](docs/README.md): guides organized by responsibility.
- [Architecture](docs/architecture.md): application boundaries, modules, and API map.
- [Backend](docs/backend.md): commerce rules, persistence, and background processing.
- [Frontend](docs/frontend.md): routes, components, API access, and UI conventions.
- [Infrastructure](docs/infrastructure.md): containers, storage, and service configuration.
- [Deployment](docs/deployment.md): HostGator deployment, secrets, and backups.
- [Performance](docs/performance.md): tracing, caching, worker sizing, and load testing.

## Repository layout

| Directory | Responsibility |
| --- | --- |
| `client/` | Next.js 15 App Router, React 19, React Query, and browser tests |
| `server/` | Django REST Framework domain apps, migrations, workers, and tests |
| `monitoring/` | Prometheus, Grafana, Loki, Alloy, Tempo, and exporters |
| `deploy/hostgator/` | Production Compose, HTTPS gateway, deployment, and backups |
| `scripts/qa/` | Local load, stress, volume, and security runners |
| `docs/` | Engineering and operational documentation |
| `qa-reports/` | Generated local evidence; ignored by Git |

Django is authoritative for identity, ownership, prices, discounts, tax, stock,
payment state, and access control. Frontend validation helps users but never
replaces server validation.

Browser requests follow one path:

```text
Browser → Next.js /api/* proxy → Django /api/v1/* → domain services → PostgreSQL
```

JWTs remain in secure HTTP-only cookies managed by the proxy. Browser code must
not call the backend origin directly or store tokens in browser storage.

## Run locally

Use Node.js 22, Python 3.11 or newer, and Docker Desktop for the container setup.
Run commands from the repository root.

```sh
npm ci
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.txt
```

Create `server/.env` and `client/.env` from their tracked examples, then configure
your development secrets. Keep real credentials out of Git. See
[getting started](docs/getting-started.md) for host-run services and email setup.

For all local container stacks:

```sh
.venv/bin/python monitoring/init_local.py
npm run docker:up
docker compose -f server/compose.yaml exec -T api python manage.py populate_fake_data
```

The frontend is normally available at `http://127.0.0.1:3000`; the backend at
`http://127.0.0.1:8000`. Configure frontend `API_URL` with the backend's
`/api/v1` suffix and backend `FRONTEND_URL` with the frontend origin.
Compose supplies internal service addresses through its container settings.

For host-run application processes, with their configured database, Redis, and
storage dependencies available:

```sh
.venv/bin/python server/manage.py migrate
.venv/bin/python server/manage.py populate_fake_data
.venv/bin/python server/manage.py runserver 127.0.0.1:8000
```

Start `npm run dev` in another terminal. The host-run database can use SQLite;
Compose uses PostgreSQL. Do not use SQLite results to establish row-lock behavior.

## Development data

`populate_fake_data` is the canonical development seed command. It creates role
accounts, stores, products, orders, reviews, wallets, and related history.
It refuses to run when Django debug mode is disabled.

| Account | Purpose |
| --- | --- |
| `admin@proace.local` | Technical super admin |
| `business-admin@proace.local` | Business administrator |
| `staff@proace.local` | Staff backoffice |
| `seller@proace.local` | Single-store seller |
| `merchant@proace.local` | Multi-store merchant |
| `shopper@proace.local`, `buyer@proace.local` | Customer workflows |

The password comes from `--password`, then `DEFAULT_ADMIN_PASSWORD` or
`TECHNICAL_ADMIN_PASSWORD`, then the development fallback `ProaceDemo2026!`.
An existing technical-super-admin password is never overwritten. Rerunning the
command can refresh other known demo accounts and scenarios.

To append at least 10,000 primary commerce records:

```sh
docker compose -f server/compose.yaml exec -T api python manage.py populate_fake_data \
  --scale huge --products 6000 --orders 4000 \
  --users 1000 --stores 50 --reviews 3000 --seed 20261020
```

Products and orders are appended; some known accounts and scenarios are reused.
The invocation also creates supporting records. Do not add `--clear` unless you
intend to delete commerce data throughout a disposable database. Generation is
transactional, and search indexing runs after commit.

## Main workflows

Customers browse and search the catalog, use optional local
[picture search](docs/visual-search.md), select variants, manage saved items and
carts, check out, track orders, request refunds, and access purchased digital files.

Merchants manage stores, teams, product drafts, variants, CSV imports, scheduled
drops, fulfillment, refunds, earnings, and payout requests. Store permissions
separate ownership, administration, catalog work, and fulfillment.

Backoffice operators manage customer access, merchant verification, product
moderation, orders, refunds, coupons, tax rules, payout approvals, and platform
finances. Financial and moderation actions retain the responsible operator.

## Commerce rules

- Physical purchases have a seven-day post-delivery return window. Physical
  proceeds stay in review until seven days after recorded store delivery and
  no earlier than the sale hold; undelivered proceeds cannot fund payouts.
  Digital proceeds retain the seven-day sale hold.
- Unshipped orders can be cancelled within 12 hours. Cancellation restocks
  eligible inventory atomically and returns customer store credit to the wallet.
- Standard stores pay a 4% platform fee; Official Partner stores pay 0%.
- Native payment supports Stripe cards, Apple Pay, Google Pay, ProAce Wallet,
  and split-tender checkout. Payment confirmation is checked on the backend.
- Destination tax uses local jurisdiction/ZIP rules with Stripe Tax fallback.
  Orders retain immutable tax and item snapshots.
- Physical rates support USPS, UPS, FedEx, and DHL Express. Military APO/FPO/DPO
  destinations require USPS; digital goods have no delivery charge.
- ClickBank listings use external checkout, never enter native carts, and follow
  the vendor's fulfillment and 60-day satisfaction policy with affiliate disclosure.
- Seller tiers progress through Starter, Booster, Accelerator, Power, Mega,
  Legendary, and Official Partner. Thresholds and verification are documented
  in [backend](docs/backend.md).

See [shipping](docs/shipping-integrations.md) and
[access control](docs/access-control.md) for configuration and role details.

## Background services

The API handles interactive requests. Celery workers process queued work;
Celery Beat schedules recovery and periodic jobs. The notification stream runs
separately so long-lived connections do not occupy ordinary API threads.
Transactional outbox records connect business events to email and push delivery.

Elasticsearch accelerates catalog search; PostgreSQL remains authoritative.
Redis provides shared cache, broker, and notification transport. MinIO provides
local S3-compatible media storage. The optional vision service performs local
CPU inference after its initial model download.

## Verification

```sh
npm run typecheck
npm run test:unit
.venv/bin/pytest server/
```

With seeded frontend and backend services running:

```sh
npm run test:integration
npm run test:e2e
```

Performance and security runners write ignored output under `qa-reports/`:

```sh
npm run test:load
npm run test:stress
npm run test:volume
npm run test:security
```

A 10,000-record dataset does not establish 5,000 requests/second capacity.
The current load runner sets concurrency, not a fixed arrival rate. Measure
achieved throughput, errors, and p95/p99 with a defined endpoint mix and a
separate load generator before making capacity claims. See
[performance testing](docs/performance.md#planning-a-5000-requestssecond-test).

## Deployment and updates

Production deployment uses `deploy/hostgator/`, private service networking, and
an HTTPS gateway. Keep database, Redis, search, storage administration, and
monitoring off the public application interface.

Rebuild only services affected by a source/configuration change:

```sh
docker compose -f client/compose.yaml up -d --build --no-deps client
docker compose -f server/compose.yaml up -d --build --no-deps api
```

Shared backend changes may also require `notification-worker`, `celery-beat`,
and `notification-stream`. Apply migrations, check container health, and verify
the running application. Documentation-only edits do not need a rebuild.
Never delete volumes to refresh application code.
