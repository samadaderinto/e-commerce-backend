# Proace Commerce

A Next.js marketplace and Django API in one base repository.

```text
client/       Next.js App Router, TypeScript, React Query and responsive UI
server/       Existing Django project and the integrated storefront API
.github/      Backend and frontend CI
package.json  npm workspace and root frontend commands
```

The previous `codematics/` backend directory is now `server/`. The Python settings
package inside it is still named `codematics`. Existing backend work was moved,
not replaced. The runnable commerce configuration is
`codematics.storefront_settings`; the legacy settings remain available separately.

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
`http://127.0.0.1:8000/api/v1`; override `API_URL` in `client/.env.local` when needed.
Email verification and password-reset links print to the API terminal locally.
Set `FRONTEND_URL=http://127.0.0.1:3000` to keep email links on that exact host.

## Run The Container Stack

The container stack runs the Django API, official Redis cache, and the local
monitoring tools. Local Compose uses the persistent `media-data` volume for
uploads, so it does not require MinIO or another object-storage registry.

From the repository root:

```sh
cd server
../.venv/bin/python monitoring/init_local.py
export OBSERVABILITY_TOKEN="$(tr -d '\n' < monitoring/secrets/metrics-token)"
docker compose -f compose.yaml up --build -d api redis postgres
docker compose -f monitoring/compose.yaml up -d
```

The API uses `redis://redis:6379/0` inside Compose. The API is available at
<http://127.0.0.1:8000>, Redis is bound to `127.0.0.1:6379`, Grafana is at
<http://127.0.0.1:3002>, and Prometheus is at <http://127.0.0.1:9090>. PostgreSQL
is available at `127.0.0.1:5432` and persists in the `postgres-data` volume. The
generated Grafana password is stored in `server/monitoring/.env`.

Check both stacks and follow their logs:

```sh
docker compose -f compose.yaml ps
docker compose -f monitoring/compose.yaml ps
docker compose -f compose.yaml logs -f api redis
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

For production, set `DJANGO_DEBUG=false`, replace all local secrets, use a
managed PostgreSQL database and S3-compatible object storage, and run migrations
as a release job before starting multiple API replicas. Full deployment details
are in [`server/deployment.md`](server/deployment.md) and
[`server/monitoring/README.md`](server/monitoring/README.md).

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

- Storefront with product photography, categories and deals.
- Search, category/price filters, sorting and pagination.
- Product details, photo gallery, stock availability and customer reviews.
- Saved items and a persistent guest bag; sign-in merges available guest items.
- Email-verified registration, sign-in, reset password and sign-out.
- Profile, delivery addresses, order history and order detail pages.
- Cash-on-delivery checkout with stock revalidation, immutable item/address
  snapshots, transactional stock deductions and idempotent retry handling.
- Responsive layouts, form validation, loading/error/empty states and 404s.

## Seller Experience

Visit `/merchant` after signing in. New sellers can create a store and pickup
address, then create drafts, publish listings, upload images, set pricing and stock,
edit specifications and export the current product page to CSV. The workspace
includes date-filtered dashboard statistics, daily order activity, inventory alerts,
seller-specific order lists and store settings. Existing owners can select among
their stores. Blocked stores cannot publish through the merchant product API.

## API And Authentication

All browser API calls use the Next.js `/api/*` server proxy. Access and refresh
tokens live in HTTP-only, SameSite cookies, not browser local storage. Mutating
requests require a same-origin `Origin` header. The proxy refreshes expired access
tokens, excludes credentials from JSON responses, and clears cookies on sign-out.
Production cookies require HTTPS.

The Django API uses `/api/v1/`. It reuses existing users, stores, products, carts and
orders. Ownership is derived from authentication. Public catalog responses exclude
drafts and blocked sellers. The new runtime excludes optional legacy notification,
profiler, Elasticsearch and shipping integrations that previously blocked startup.

The OpenAPI schema is available at `http://127.0.0.1:8000/api/schema/` (YAML by
default; request `application/vnd.oai.openapi+json` for JSON), with interactive
Swagger UI at `/api/docs/` and ReDoc at `/api/redoc/`. Authenticated API operations
use a JWT bearer access token; the browser storefront keeps those tokens in HTTP-only
cookies and calls the API through its same-origin Next.js proxy.

## Verification

```sh
npm run build
npm run typecheck
npm run test:unit
npm run test:integration
npm run test:e2e
.venv/bin/python server/manage.py test storefront --settings=codematics.storefront_settings --noinput
```

Unit tests exercise frontend API serialization/error handling, currency formatting,
categories, and backend price rounding without making external service calls.
Integration tests exercise the Next.js API proxy against the Django API, including
catalog access, authentication, token-cookie handling, and same-origin protection.
Integration and end-to-end browser tests require both local servers and the seeded
accounts. On macOS they use installed Google Chrome. On other systems run
`npx playwright install chromium` first; `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` can specify another executable.
`E2E_BASE_URL` and `E2E_DEMO_PASSWORD` override the test URL and password. Tests place
sample orders and create unpublished test products in the local database.
Screenshots and failure traces go in `artifacts/` (ignored by Git).

## Deployment Boundaries

- Set `DJANGO_DEBUG=false`, a strong `SECRET_KEY`, `ALLOWED_HOSTS`, `FRONTEND_URL`,
  SMTP configuration and persistent media/database storage. Build the client with
  `npm run build` and run `npm run start --workspace=client` behind HTTPS.
- The included API is ready for local integration, not a claim of production
  marketplace certification. Review operator-specific privacy, returns and support
  policies before launch; no legal policy or merchant identity verification service
  is supplied.
- Cash on delivery works end to end. Card charging, payouts, shipping labels and
  tracking-carrier integrations are not connected. No checkout screen accepts card
  details or claims to have charged a customer.
- Merchant fulfillment status updates remain read-only because the legacy order
  has one shared status for a potentially multi-seller cart. Seller fulfillment
  records are needed before enabling independent shipment updates.
- Dashboard monetary figures are explicitly estimates from current catalog prices,
  not settled revenue. New customer orders preserve historical prices; old orders
  without snapshots remain readable but cannot reconstruct historic line amounts.
- Legacy migration drift outside the integrated routes, including `Refund`, still
  requires a separate data migration before those older workflows can be deployed.
- Product photos and fonts use external providers. Image-load failures have a
  fallback; production sellers can upload photographs into configured media storage.

The existing [merchant API notes](server/store/README.md) document the underlying
seller routes; they are mounted under `/api/v1/stores/` in the integrated runtime.
