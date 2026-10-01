# Monitoring and observability

The application exposes `/health/live/`, `/health/ready/`, `/health/status/`,
and `/metrics/`. The first two support probes; status and metrics require
`Authorization: Bearer $OBSERVABILITY_TOKEN`. Health checks cover every configured
database and cache alias using a temporary random cache key. The result is never
cached.

Each API request gets a request ID and sampled trace ID. JSON logs include the
method, route template, status, duration, database query count and database time.
SQL text, query parameters, authorization headers, cookies and bodies are excluded.
Prometheus records request rate, status counts, p50/p95/p99 latency, in-flight
work, database workload and Elasticsearch exporter metrics. Route labels use
Django route templates to avoid user-ID cardinality.

Monitoring, log aggregation and observability are related, but they are not the
same thing. Monitoring answers "is it healthy and how loaded is it?" with metrics,
dashboards and alerts. Log aggregation collects application and infrastructure
logs into one searchable place. Observability is the bigger production practice:
metrics, logs, traces, health checks and profiling together.

## Local

### Container stack

From the repository root:

```sh
cd server
../.venv/bin/python monitoring/init_local.py
docker compose --env-file .env -f compose.yaml up --build -d
docker compose --env-file .env -f monitoring/compose.yaml up -d
```

The API is at `http://127.0.0.1:8000`, Grafana is at
`http://127.0.0.1:3002`, and Prometheus is at `http://127.0.0.1:9090`. The API
uses the official Redis service at `redis://redis:6379/0`. Elasticsearch runs at
`http://127.0.0.1:9200` in the app stack. The generated Grafana password and
metrics token are in `server/.env`.

Both projects share `commerce-network` (override `COMMERCE_NETWORK` in `.env`).
`monitoring/init_local.py` creates the external network when it is missing.
Always pass the same `--env-file` to both projects so database credentials and
scrape tokens match. The collectors connect through Docker service names, not
host-published ports. The API's container configuration allows the `api` hostname.

PostgreSQL, Redis, Elasticsearch, node-exporter and the Docker metrics exporter
all start by default.
The **Commerce Infrastructure** dashboard shows scrape status, database
connections/transactions/cache hits/deadlocks/size, Redis operations/memory/hits/
evictions, container CPU/memory/limits, host CPU/memory/disk, and firing alerts.
**Commerce API Overview** keeps request, query, dependency and search metrics.
Prometheus also scrapes Grafana, Loki and Tempo themselves.

The Docker metrics exporter reads the Docker socket through a read-only mount and
exports CPU, memory, limit, OOM and last-seen metrics. Exporter ports are private
to the Docker network. Only Compose project/service labels are exported as
container labels.
On Docker Desktop, host metrics describe the Linux VM running Docker, not macOS
or Windows. Container disk metrics depend on the Docker storage driver. Memory
limit alerts require an actual container limit; use host memory alerts as well.

The PostgreSQL exporter defaults to the same local credentials as the app.
For production, set `POSTGRES_EXPORTER_USER` / `POSTGRES_EXPORTER_PASSWORD` to a
dedicated role with `pg_monitor` and database CONNECT permission. Redis can use
`REDIS_EXPORTER_PASSWORD` when authentication is enabled.

Validate configuration and confirm actual coverage:

```sh
docker compose --env-file .env -f compose.yaml config --quiet
docker compose --env-file .env -f monitoring/compose.yaml config --quiet
docker compose --env-file .env -f monitoring/compose.yaml exec prometheus promtool check config /tmp/prometheus.yml
../.venv/bin/python monitoring/check_monitoring.py
```

The verification command fails on missing/down scrape targets, disconnected
database/cache exporters, or missing API/container/host metrics. It does not
assume that a running exporter has successfully connected to its dependency.
Alerts are evaluated in Prometheus and shown in Grafana; email/chat/paging
delivery requires configuring a real notification destination separately.

Alloy collects Docker container stdout through the Docker socket and sends it to
Loki. Django writes JSON logs to stdout, so request IDs, route templates, status
codes, duration, database query counts and exception stack metadata are searchable
without needing a side file. Kafka log publishing is optional and disabled unless
`KAFKA_LOGGING_ENABLED=true`.

Inspect or stop both stacks:

```sh
docker compose -f compose.yaml ps
docker compose -f monitoring/compose.yaml ps
docker compose -f compose.yaml logs -f api redis
docker compose -f monitoring/compose.yaml down
docker compose -f compose.yaml down
```

To restart only the log aggregation path after changing Alloy or Loki:

```sh
docker compose --env-file .env -f monitoring/compose.yaml up -d --force-recreate loki alloy grafana
```

In Grafana, go to Explore and choose the Loki data source. Useful local queries:

```logql
{service_name="api"}
{service_name="api"} | json | level="ERROR"
{service_name="api"} | json | status_code >= 500
{service_name="postgres"}
{service_name="redis"}
{service_name="elasticsearch"}
```

For one request, copy the `request_id` from an API response header or log line:

```logql
{service_name="api"} | json | request_id="paste-request-id-here"
```

The container API binds Gunicorn to `0.0.0.0:8000` internally so the host and
Prometheus can reach it. Local uploads persist in the `media-data` volume.

Kafka and RabbitMQ are optional messaging dependencies and are disabled by
default. Start them only when testing the queue consumers:

```sh
docker compose --env-file .env -f monitoring/compose.yaml --profile messaging up -d kafka rabbitmq
```

The default monitoring command does not pull or require either messaging image.

### Running the API outside Docker

The default scrape target is `api:8000`. For a host-run API, change
`targets/app.json` to `host.docker.internal:8000`, add that hostname to
`ALLOWED_HOSTS`, and keep the infrastructure stack running. Use:

```sh
DJANGO_SETTINGS_MODULE=codematics.storefront_settings \
DJANGO_DEBUG=true \
PROMETHEUS_MULTIPROC_DIR=/tmp/commerce-prometheus \
GUNICORN_BIND=0.0.0.0:8000 \
../.venv/bin/gunicorn -c gunicorn.conf.py codematics.wsgi:application
```

Create a fresh, empty multiprocess directory for each Gunicorn master. For a
simple Django run, omit the Gunicorn variables and use `manage.py runserver`.

Start the local stack:

```sh
docker compose --env-file .env -f monitoring/compose.yaml up -d
```

Grafana is at `http://127.0.0.1:3002`, with the password in `server/.env`;
Prometheus is at `http://127.0.0.1:9090`. The dashboard is
provisioned as “Commerce API Overview”. Set `OTEL_TRACING_ENABLED=true`,
`OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318`, and
`OTEL_TRACES_SAMPLER_ARG=1.0` for local traces.

For local line profiling, install `requirements-local.txt`, set
`LOCAL_PROFILING_ENABLED=true`, and sign in as a Django superuser. Silk is then
available at `/silk/`; it is disabled unless explicitly enabled and cannot start
when `DJANGO_DEBUG=false`.

## Production

Run the API behind Nginx/Gunicorn. Set a strong secret and a separate metrics
token through GitHub Actions secrets or the deployment platform secret manager.
Set `DJANGO_DEBUG=false`,
`LOCAL_PROFILING_ENABLED=false`, and use a small trace sampling ratio such as
`OTEL_TRACES_SAMPLER_ARG=0.05`. Point `OTEL_EXPORTER_OTLP_ENDPOINT` at a private
collector or Tempo endpoint.

Prometheus should scrape `/metrics/` over a private network. Replace
`targets/app.json` and exporter connection settings with production targets as
needed. Configure Alertmanager or Grafana Alerting for paging.

The local stack retains 15 days of metrics, 48 hours of traces and 7 days of logs.
The included Loki/Tempo/Alloy configuration is compact local infrastructure. In
production, collect container logs with the platform collector, Alloy, Fluent Bit
or an equivalent agent, and send them to a durable, authenticated Loki-compatible
or managed logging backend. Keep labels low-cardinality: service, environment,
version and container are good labels; request IDs and user IDs should stay inside
the JSON log body.

Production profiling is low overhead: request histograms, in-flight requests,
DB query counts/time, error rate and sampled traces. Use a log trace ID to open a
Tempo trace. Use Silk only in local or a short-lived private debugging environment.
