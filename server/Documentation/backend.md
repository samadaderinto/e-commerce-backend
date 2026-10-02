# Backend

The backend is a Django API under `server/`. The deployable marketplace settings
module is `codematics.storefront_settings`.

## Key apps

- `storefront`: integrated `/api/v1/` customer and merchant API.
- `product`: products, images, catalog data and Elasticsearch search helpers.
- `store`: seller stores, merchant profile, moderation and media services.
- `cart`: cart models, serializers and cart API.
- `payment`: checkout, orders and coupon logic.
- `observability`: health, metrics, JSON logs, tracing and profiling hooks.
- `notification`: persisted in-app notifications and optional FCM push devices.

## Search

Elasticsearch powers public catalog search when `ELASTICSEARCH_ENABLED=true`.
Product saves and deletes sync through signals, and the API falls back to database
search if Elasticsearch is unavailable.

Rebuild the index:

```sh
docker compose -f compose.yaml exec api python manage.py rebuild_product_index
```

## API docs

- Swagger UI: `http://127.0.0.1:8000/api/docs/`
- ReDoc: `http://127.0.0.1:8000/api/redoc/`
- Schema: `http://127.0.0.1:8000/api/schema/`

## Notifications and FCM

The authenticated `/api/v1/notifications/` endpoints back the in-app inbox.
Email and push deliveries are persisted to the outbox and sent asynchronously
by the Celery worker. The worker retries transient errors and periodically
recovers stale deliveries. Set `CELERY_BROKER_URL` identically for the API and
worker; local Compose uses Redis DB 1. Email uses the console backend locally
and SMTP in production. To enable browser push, set `FCM_ENABLED=true` and
`FIREBASE_PROJECT_ID`, provide Firebase credentials outside the repository,
and configure the Firebase Web app and VAPID key in the client. Apply database
migrations before deploying and run the worker alongside the API.
