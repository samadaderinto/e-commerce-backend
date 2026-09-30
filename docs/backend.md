# Backend documentation

The backend lives in `server/`. It is a Django project whose Python settings
package is still named `codematics`. The integrated marketplace runtime uses
`codematics.storefront_settings`.

## Code map

- `server/manage.py`: Django management entrypoint.
- `server/codematics/settings.py`: base legacy settings.
- `server/codematics/storefront_settings.py`: integrated commerce runtime.
- `server/codematics/urls.py`: legacy URL tree.
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
should continue to validate owner, store state, price and stock server-side.

## Search

Public catalog search uses Elasticsearch when `ELASTICSEARCH_ENABLED=true`.
Product saves and deletes sync to Elasticsearch through Django signals on a
best-effort basis. If Elasticsearch is disabled or a search request fails, the
catalog falls back to database `icontains` filtering for title, brand and
description.

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

## Documentation maintenance

Update this file when changing Django apps, model ownership rules, serializers,
API responses, permissions, auth, cache/database/media behavior, seed data,
management commands or backend tests.
