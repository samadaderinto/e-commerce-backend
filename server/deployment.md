# Server ingress

See [Nginx security and deployment](nginx/README.md) for IP blocking, suspected-IP
limits, operator whitelisting, proxy trust, logging, and host/Kubernetes setup.

See [Monitoring and observability](monitoring/README.md) for health probes,
database/cache checks, Prometheus metrics, Grafana dashboards, traces, logs, and
local/production profiling.

The application container, official Redis cache, official PostgreSQL database and
Elasticsearch search service are defined in
`server/compose.yaml`. For local development, copy `.env.example` to `.env` or
use the included local `.env`, then run from `server/`:

```sh
docker compose -f compose.yaml up --build -d api redis postgres elasticsearch
docker compose -f compose.yaml exec api python manage.py rebuild_product_index
```

The API is available at `http://127.0.0.1:8000`; Redis and PostgreSQL are bound
to localhost only. The API container runs migrations on startup, stores
PostgreSQL data in the `postgres-data` volume, stores local uploads in
`media-data`, stores product search data in `elasticsearch-data`, and uses
`redis://redis:6379/0` and `http://elasticsearch:9200` inside Compose. Local
Compose does not depend on MinIO or any external object-storage registry.

For production, do not create `.env.prod` or service-specific env files. Set
production values through GitHub Actions secrets or the deployment platform
secret manager. Required production values include `DJANGO_DEBUG=false`,
`SECRET_KEY`, `ALLOWED_HOSTS`, `FRONTEND_URL`, PostgreSQL credentials,
`CACHE_URL`, `OBSERVABILITY_TOKEN`, `ELASTICSEARCH_URL`, and object-storage
credentials when `OBJECT_STORAGE_ENABLED=true`. Set `RUN_MIGRATIONS=false` when
more than one API replica starts at once. Run migrations and
`rebuild_product_index` as release jobs, then start the API replicas.

## Render deployment

The GitHub Actions deploy job is Render-specific. It reads production values from
GitHub Actions secrets, syncs them to the Render service through the Render API,
then triggers the Render deploy hook. Do not commit production env files.

Required Render control secrets:

| Secret | Purpose |
| --- | --- |
| `RENDER_API_KEY` | Render API token used to update service environment variables |
| `RENDER_SERVICE_ID` | Render service ID for the backend service |
| `RENDER_WORKER_SERVICE_ID` | Render service ID for the notification worker |
| `RENDER_DEPLOY_HOOK_URL` | Render deploy hook URL for that service |

Required production app secrets:

| Secret | Render env var |
| --- | --- |
| `PROD_API_URL` | `API_URL` |
| `PROD_SECRET_KEY` | `SECRET_KEY` |
| `PROD_ALLOWED_HOSTS` | `ALLOWED_HOSTS` |
| `PROD_FRONTEND_URL` | `FRONTEND_URL` |
| `PROD_POSTGRES_HOST` | `POSTGRES_HOST` |
| `PROD_POSTGRES_DB` | `POSTGRES_DB` |
| `PROD_POSTGRES_USER` | `POSTGRES_USER` |
| `PROD_POSTGRES_PASSWORD` | `POSTGRES_PASSWORD` |
| `PROD_CACHE_URL` | `CACHE_URL` |
| `PROD_CELERY_BROKER_URL` | `CELERY_BROKER_URL` |
| `PROD_OBSERVABILITY_TOKEN` | `OBSERVABILITY_TOKEN` |
| `PROD_S3_BUCKET_NAME` | `MINIO_BUCKET_NAME` |
| `PROD_S3_ACCESS_KEY` | `MINIO_ACCESS_KEY` |
| `PROD_S3_SECRET_KEY` | `MINIO_SECRET_KEY` |

Required when Elasticsearch is enabled:

| Secret | Render env var |
| --- | --- |
| `PROD_ELASTICSEARCH_URL` | `ELASTICSEARCH_URL` |

`PROD_CELERY_BROKER_URL` must point to the production Redis broker and is
synced to both the API and worker. Configure the worker service to run
`celery -A codematics worker --beat --loglevel=INFO`. Email is sent using SMTP
values supplied as `PROD_EMAIL_HOST`, `PROD_EMAIL_HOST_USER`,
`PROD_EMAIL_HOST_PASSWORD`, and `PROD_DEFAULT_FROM_EMAIL`; FCM credentials are
required as `PROD_FIREBASE_PROJECT_ID` and `PROD_FIREBASE_CREDENTIALS_JSON`
only when `PROD_FCM_ENABLED=true`. Production app configuration is sourced
from GitHub Actions secrets and synchronized to both Render services.

Optional production secrets such as `PROD_POSTGRES_PORT`,
`PROD_DB_REQUIRE_SSL`, `PROD_OBJECT_STORAGE_ENABLED`, `PROD_S3_ENDPOINT_URL`,
`PROD_S3_PUBLIC_URL`, `PROD_S3_REGION`, OpenTelemetry, Kafka, Celery and SMTP
settings are also synced when present.

The local image does not install AWS SDK packages because local uploads use the
`media-data` volume. For an S3-compatible production deployment, set
`OBJECT_STORAGE_ENABLED=true` and `INSTALL_OBJECT_STORAGE=true` before building;
the matching AWS SDK pair is then installed from `requirements-storage.txt`.
