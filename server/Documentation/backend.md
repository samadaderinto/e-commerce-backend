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
Optional browser push delivery uses Firebase Cloud Messaging and the
authenticated `/api/v1/notifications/devices/` endpoint. Set `FCM_ENABLED=true`
and `FIREBASE_PROJECT_ID`, provide Google Application Default Credentials outside
the repository, configure the Firebase Web app and VAPID key in the client, and
run the Celery worker. Apply database migrations before deploying. Push delivery
supplements, and does not replace, persisted inbox or email notifications.
