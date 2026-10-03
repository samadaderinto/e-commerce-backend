# Backend documentation

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

### Product Variants & Flash Sales
- **Product Variants (`Product.variants`)**: JSON-based array storing option names (e.g. Size, Color), price deltas (`price_delta`), and dedicated stock allocation (`available`).
- **Flash Deals (`Product.flash_sale_end`)**: Optional expiration timestamp powering urgency badges and live countdown timers across storefronts.
- **Store Announcements (`StoreInfo.announcement`)**: Marquee banner text displayed on the public store showcase page.
- **Verified Buyer Reviews (`Review.images`)**: Restricts review posting to verified purchasers and validates up to 3 attached photo URLs.

### Merchant escrow and payouts
- **Platform Commission (4%)**: Automatically items and deducts a 4% platform fee (`PLATFORM_FEE_PERCENT = 4.00`) from gross item sales.
- **7-Day Review Escrow**: Net sales from customer orders placed within the 7-day refund window (`REFUND_WINDOW_DAYS = 7`) are held in `in_review` status.
- **Cleared Balance**: Once orders surpass the 7-day refund deadline, funds unlock to `cleared_net` and become available for merchant withdrawal requests via `/api/v1/stores/<id>/payouts/`.
- **Fulfillment & USPS Tracking**: Merchants update carrier, tracking number, and milestone descriptions on store orders via `/api/v1/stores/<id>/orders/<order_id>/tracking/`, which triggers customer notifications and provides live tracking links.

## ProAce User Wallet and 7-day refunds

- **Customer Wallet (`/api/v1/wallet/`)**: Every registered customer has an integrated store balance for instant 1-click checkout purchases and instant store credit refund resolution.
- **7-Day Refund Policy (`/api/v1/orders/<id>/refund/`)**: Customers can request refunds for physical items within 7 days of order placement. Refund destinations can be selected as ProAce Store Credit (instant wallet credit upon staff approval) or original payment method. Digital goods are non-refundable once delivered.

## USPS Tracking Engine

- `server/payment/usps.py`: Integrates with the USPS XML TrackV2 API with simulated fallback for local/offline testing.
- Orders dynamically generate live tracking links (`https://tools.usps.com/go/TrackConfirmAction?tLabels=<tracking_number>`).
- Live tracking milestones are queryable by customers, merchants, staff, and superusers via `/api/v1/orders/<id>/tracking/`.

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

Rebuild locally after seeding or importing products:

```sh
docker compose -f compose.yaml exec api python manage.py rebuild_product_index
```

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

Backend tools added or wired:

- `gunicorn`: production-style WSGI server used by the container.
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

## Local commands

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.txt
.venv/bin/python server/manage.py migrate --settings=codematics.storefront_settings
.venv/bin/python server/manage.py seed_demo --settings=codematics.storefront_settings --password 'ProaceDemo2026!'
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
