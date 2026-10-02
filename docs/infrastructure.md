# Infrastructure documentation

This project supports local development through Docker Compose and has production
building blocks for Gunicorn, Nginx, PostgreSQL, Redis, object storage and
observability.

The repository contains two deployable apps:

- `client/`: frontend, deployable to a frontend host or as `client/Dockerfile`.
- `server/`: backend API, deployable to Render with service dependencies.

The bridge between them is `API_URL` on the frontend and `FRONTEND_URL` on the
backend.

## Environment files

Local development uses exactly one server env file and one client env file:

- `server/.env`: server, Docker Compose, Elasticsearch and monitoring values for
  local work.
- `server/.env.example`: tracked template for server values.
- `client/.env`: frontend and test values for local work.
- `client/.env.example`: tracked template for frontend values.

Production does not use repo env files. GitHub Actions reads production values
from repository or environment secrets in the `production` environment. The
deployment platform should receive values as environment variables or managed
secrets. Do not recreate `server/.env.prod`, `server/monitoring/.env`, or
`server/monitoring/secrets/metrics-token`.

For Render, the deploy workflow uses these control secrets:

- `RENDER_API_KEY`;
- `RENDER_SERVICE_ID`;
- `RENDER_WORKER_SERVICE_ID`;
- `RENDER_DEPLOY_HOOK_URL`.

The workflow syncs production `PROD_*` GitHub Actions secrets into the Render
service environment variables before triggering the deploy hook. The sync script
is `.github/scripts/render-sync-env.py`. For the complete required and optional
secret inventory and deployment sequence, see
[`server/deployment.md`](../server/deployment.md).

## Local containers

From `server/`:

```sh
../.venv/bin/python monitoring/init_local.py
docker compose -f compose.yaml up --build -d api redis postgres elasticsearch
docker compose -f monitoring/compose.yaml up -d
docker compose -f compose.yaml exec api python manage.py rebuild_product_index
```

Run the frontend container separately from the repository root:

```sh
docker compose -f client/compose.yaml up --build -d
```

Application services:

- `api`: Django/Gunicorn container built from `server/Dockerfile`.
- `postgres`: official `postgres:17-alpine`, persisted in `postgres-data`.
- `redis`: official `redis:7.4-alpine`, persisted in `redis-data`.
- `elasticsearch`: official Elasticsearch `8.15.5`, persisted in
  `elasticsearch-data`.
- `media-data`: local uploaded media volume.
- `prometheus-multiproc`: Prometheus multiprocess metrics directory for Gunicorn.

Monitoring services:

- `prometheus`: metrics scraping and alert evaluation.
- `grafana`: dashboards and Explore UI.
- `loki`: log storage.
- `alloy`: Docker log collector for Loki.
- `tempo`: local trace storage.

## Tool and config inventory

Application container files:

- `server/Dockerfile`: Python 3.12 slim API image. Installs
  `requirements.txt`, optionally installs `requirements-storage.txt` when
  `INSTALL_OBJECT_STORAGE=true`, runs as a non-root `app` user and starts
  Gunicorn through `docker-entrypoint.sh`.
- `server/docker-entrypoint.sh`: prepares runtime directories, optionally runs
  migrations and collectstatic, then starts the container command.
- `server/compose.yaml`: local API, PostgreSQL, Redis and Elasticsearch stack.
- `server/.env`: local server/runtime env file. It is ignored by Git.
- `server/.env.example`: documented server env template.
- `server/requirements.txt`: base API dependencies.
- `server/requirements-storage.txt`: optional object-storage dependencies.

Monitoring and operations files:

- `server/monitoring/compose.yaml`: Prometheus, Grafana, Loki, Alloy, Tempo and
  optional messaging/exporter services.
- `server/monitoring/init_local.py`: ensures local `OBSERVABILITY_TOKEN` and
  `GRAFANA_ADMIN_PASSWORD` values exist in `server/.env`.
- `server/monitoring/prometheus.yml`: scrape configuration.
- `server/monitoring/alerts.yml`: alert rules, including p95 and p99 latency.
- `server/monitoring/alloy.alloy`: Docker log collection into Loki.
- `server/monitoring/loki.yml`: local Loki retention/storage configuration.
- `server/monitoring/tempo.yml`: local Tempo trace storage configuration.
- `server/monitoring/grafana/provisioning/`: Grafana datasources and dashboard
  provisioning.
- `server/monitoring/grafana/dashboards/commerce-overview.json`: API overview
  dashboard.
- `server/monitoring/targets/`: Prometheus file discovery targets.
- `server/nginx/`: Nginx proxy hardening, IP allow/deny lists and Kubernetes
  manifests.

## Application Compose config

`server/compose.yaml` starts four default services:

- `api`: built from `server/Dockerfile`; exposes `${API_PORT:-8000}` on
  `${API_BIND_ADDRESS:-127.0.0.1}`; waits for healthy Postgres, Redis and
  Elasticsearch; writes logs to stdout; mounts `media-data` and
  `prometheus-multiproc`.
- `redis`: official `redis:7.4-alpine`; enables append-only persistence and an
  RDB save rule; exposes `${REDIS_PORT:-6379}` locally; persists `redis-data`.
- `postgres`: official `postgres:17-alpine`; exposes
  `${POSTGRES_PORT_HOST:-5432}` locally; persists `postgres-data`; health checks
  with `pg_isready`.
- `elasticsearch`: official `docker.elastic.co/elasticsearch/elasticsearch:8.15.5`;
  runs as a single-node local cluster with security disabled; exposes
  `${ELASTICSEARCH_PORT:-9200}` locally; persists `elasticsearch-data`.

Important API environment variables:

| Variable | Purpose | Local default |
| --- | --- | --- |
| `DJANGO_SETTINGS_MODULE` | Django settings module | `codematics.storefront_settings` |
| `DJANGO_DEBUG` | Enables debug behavior | `true` |
| `SECRET_KEY` | Django signing secret | local placeholder |
| `ALLOWED_HOSTS` | Accepted hostnames | `127.0.0.1,localhost` |
| `FRONTEND_URL` | Browser app origin for links and CORS-style checks | `http://127.0.0.1:3000` |
| `DATABASE_ENGINE` | Database backend selector | `postgres` |
| `POSTGRES_HOST` | Database hostname inside Compose | `postgres` |
| `CACHE_URL` | Django cache URL inside Compose | `redis://redis:6379/0` |
| `OBJECT_STORAGE_ENABLED` | Enables S3-compatible media storage | `false` |
| `OBSERVABILITY_TOKEN` | Bearer token for `/metrics/` and detailed health | generated/local placeholder |
| `OTEL_TRACING_ENABLED` | Enables OTLP tracing | `false` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Trace exporter endpoint | `http://tempo:4318` |
| `PROMETHEUS_MULTIPROC_DIR` | Gunicorn Prometheus multiprocess directory | `/tmp/prometheus` |
| `RUN_MIGRATIONS` | Run migrations at container startup | `true` |
| `RUN_COLLECTSTATIC` | Run collectstatic at container startup | `false` |
| `ELASTICSEARCH_ENABLED` | Enables product search indexing/search | `true` in Compose |
| `ELASTICSEARCH_URL` | Elasticsearch HTTP endpoint for host-run Django | `http://127.0.0.1:9200` |
| `ELASTICSEARCH_PRODUCTS_INDEX` | Product index name | `commerce-products` |
| `ELASTICSEARCH_JAVA_OPTS` | Local JVM memory sizing | `-Xms512m -Xmx512m` |

Host bind variables:

| Variable | Purpose |
| --- | --- |
| `API_BIND_ADDRESS`, `API_PORT` | Host address and port for the API container |
| `REDIS_BIND_ADDRESS`, `REDIS_PORT` | Host address and port for Redis |
| `POSTGRES_BIND_ADDRESS`, `POSTGRES_PORT_HOST` | Host address and port for PostgreSQL |
| `ELASTICSEARCH_BIND_ADDRESS`, `ELASTICSEARCH_PORT` | Host address and port for Elasticsearch |

Do not keep placeholder secrets in production. Use the platform secret manager
or GitHub Actions secrets and inject values at runtime. Do not add `.env.prod`
or service-specific env files.

## Elasticsearch

Elasticsearch powers catalog search when enabled. Local Compose starts it by
default, and Django falls back to database search if it is disabled or temporarily
unavailable.

The API container uses `http://elasticsearch:9200` internally. Host-run Django can
use `ELASTICSEARCH_URL=http://127.0.0.1:9200` from `server/.env`.

Useful local commands from `server/`:

```sh
docker compose -f compose.yaml up -d elasticsearch
docker compose -f compose.yaml exec api python manage.py rebuild_product_index
curl http://127.0.0.1:9200/_cluster/health?pretty
```

Production should use a managed Elasticsearch/OpenSearch-compatible deployment
or a secured self-hosted cluster. Set `ELASTICSEARCH_URL` through GitHub Actions
secrets or the deployment platform secret manager. Keep local `xpack.security`
settings out of production.

## Messaging and notification delivery

The notification outbox uses Celery with Redis as its broker. The API persists
email and FCM push deliveries before enqueueing them; the Compose
`notification-worker` processes them and runs periodic recovery for stale
deliveries. Configure `CELERY_BROKER_URL` to the same Redis broker for the API
and worker. In Compose, Redis DB 1 is reserved for Celery and DB 0 backs Django
cache. Email delivery uses the configured email backend (console locally, SMTP
in production); push delivery uses Firebase Cloud Messaging.

Kafka and RabbitMQ remain optional development services for Kafka log
publishing and other explicitly configured consumers. Start them only when
needed:

```sh
docker compose -f monitoring/compose.yaml --profile messaging up -d kafka rabbitmq
```

Kafka bootstrap servers:

- from the Mac host: `127.0.0.1:9092`;
- from another Compose service on the monitoring network: `kafka:9092`.

Kafka log publishing is disabled unless `KAFKA_LOGGING_ENABLED=true`. Normal log
aggregation does not need Kafka; Django writes JSON logs to stdout and Alloy sends
Docker logs to Loki.

Messaging config:

| Variable | Purpose | Local default |
| --- | --- | --- |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker list for Django/consumers | `127.0.0.1:9092` on host |
| `KAFKA_LOGGING_ENABLED` | Enables best-effort Kafka log publishing | `false` |
| `KAFKA_LOG_TOPIC` | Kafka topic for app logs | `commerce.logs` |
| `KAFKA_LOG_GROUP` | Consumer group for log indexing helpers | `commerce-log-indexer` |
| `KAFKA_CLUSTER_ID` | Local KRaft cluster ID for the Kafka container | generated default |
| `CELERY_BROKER_URL` | Celery broker used by both API and worker | `redis://127.0.0.1:6379/1` on host; Compose uses `redis://redis:6379/1` |
| `NOTIFICATION_DELIVERY_MAX_ATTEMPTS` | Maximum attempts before a delivery is marked failed | `8` |
| `NOTIFICATION_DELIVERY_STALE_SECONDS` | Age after which an in-flight delivery is recovered | `300` |
| `EMAIL_BACKEND` | Email sender backend | Console locally; SMTP in production |
| `FCM_ENABLED` | Enables Firebase Cloud Messaging push delivery | `false` locally |

## Nginx

Nginx security and IP allow/deny configuration lives in `server/nginx/`. Use it
for proxy hardening, suspected IP handling and operator allowlists. Keep the
operator allowlist narrow and environment-specific.

Nginx files:

- `server/nginx/nginx.conf`: main reverse-proxy config, security headers and
  request handling.
- `server/nginx/upstream.conf`: API upstream definition.
- `server/nginx/allowed-ips.conf`: explicit operator/client allowlist.
- `server/nginx/blocked-ips.conf`: denylist for malicious IPs.
- `server/nginx/suspected-ips.conf`: separate list for suspected IP handling.
- `server/nginx/trusted-proxies.conf`: trusted proxy ranges for real client IP
  handling.
- `server/nginx/test_security.py`: config/security validation helper.
- `server/nginx/deployment.yaml` and `kustomization.yaml`: Kubernetes deployment
  manifests for the Nginx layer.

## Object storage

Local Compose does not require MinIO. It uses the `media-data` volume so local
image uploads work without pulling an object-storage registry image. Production
can use S3-compatible object storage by enabling the storage requirements and
setting the object storage environment variables.

Object storage config:

| Variable | Purpose |
| --- | --- |
| `INSTALL_OBJECT_STORAGE` | Docker build arg that installs `requirements-storage.txt` |
| `OBJECT_STORAGE_ENABLED` | Enables S3-compatible storage in Django |
| `MINIO_ENDPOINT_URL` | Internal S3-compatible endpoint |
| `MINIO_PUBLIC_URL` | Browser-reachable media base URL |
| `MINIO_BUCKET_NAME` | Media bucket |
| `MINIO_REGION` | Bucket region |
| `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` | Storage credentials |

The `MINIO_*` names are kept for local compatibility, but the same settings can
point at any S3-compatible provider.

## Production boundaries

For production:

- set `DJANGO_DEBUG=false`;
- use a strong `SECRET_KEY`;
- replace all local passwords and generated tokens;
- use managed PostgreSQL or a backed-up PostgreSQL deployment;
- use managed Redis or a secured Redis deployment;
- use durable object storage for media;
- run migrations as a release job before starting multiple API replicas;
- put the API behind HTTPS and a hardened proxy;
- ship logs, metrics and traces to durable backends.

## Documentation maintenance

Update this file when changing Dockerfiles, Compose services, service images,
ports, volumes, environment variables, Kafka/RabbitMQ, Redis, PostgreSQL, Nginx,
object storage or production deployment instructions.
