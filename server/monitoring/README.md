# Monitoring and observability

The application exposes `/health/live/`, `/health/ready/`, `/health/status/`,
and `/metrics/`. The first two support probes; status and metrics require
`Authorization: Bearer $OBSERVABILITY_TOKEN`. Health checks cover every configured
database and cache alias using a temporary random cache key. The result is never
cached.

Each API request gets a request ID and sampled trace ID. JSON logs include the
method, route template, status, duration, database query count and database time.
SQL text, query parameters, authorization headers, cookies and bodies are excluded.
Prometheus records request rate, status counts, p50/p95/p99 latency, in-flight work,
and database workload. Route labels use Django route templates to avoid user-ID
cardinality.

## Local

### Container stack

From the repository root:

```sh
cd server
../.venv/bin/python monitoring/init_local.py
export OBSERVABILITY_TOKEN="$(tr -d '\n' < monitoring/secrets/metrics-token)"
docker compose -f compose.yaml up --build -d api redis postgres
docker compose -f monitoring/compose.yaml up -d
```

The API is at `http://127.0.0.1:8000`, Grafana is at
`http://127.0.0.1:3002`, and Prometheus is at `http://127.0.0.1:9090`. The API
uses the official Redis service at `redis://redis:6379/0`. The generated Grafana
password is in `monitoring/.env`.

Inspect or stop both stacks:

```sh
docker compose -f compose.yaml ps
docker compose -f monitoring/compose.yaml ps
docker compose -f compose.yaml logs -f api redis
docker compose -f compose.yaml down
docker compose -f monitoring/compose.yaml down
```

The container API binds Gunicorn to `0.0.0.0:8000` internally so the host and
Prometheus can reach it. Local uploads persist in the `media-data` volume.

Kafka and RabbitMQ are optional messaging dependencies and are disabled by
default. Start them only when testing the queue consumers:

```sh
docker compose -f monitoring/compose.yaml --profile messaging up -d kafka rabbitmq
```

The default monitoring command does not pull or require either messaging image.

```sh
cd server
../.venv/bin/python monitoring/init_local.py
DJANGO_SETTINGS_MODULE=codematics.storefront_settings \
DJANGO_DEBUG=true \
OBSERVABILITY_TOKEN=$(tr -d '\n' < monitoring/secrets/metrics-token) \
PROMETHEUS_MULTIPROC_DIR=/tmp/commerce-prometheus \
GUNICORN_BIND=0.0.0.0:8000 \
../.venv/bin/gunicorn -c gunicorn.conf.py codematics.wsgi:application
```

Create a fresh, empty multiprocess directory for each Gunicorn master. For a
simple Django run, omit the Gunicorn variables and use `manage.py runserver`.

Start the local stack:

```sh
docker compose -f monitoring/compose.yaml up -d
```

Grafana is at `http://127.0.0.1:3002`, with the generated password in
`monitoring/.env`; Prometheus is at `http://127.0.0.1:9090`. The dashboard is
provisioned as “Commerce API Overview”. Set `OTEL_TRACING_ENABLED=true`,
`OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318`, and
`OTEL_TRACES_SAMPLER_ARG=1.0` for local traces.

For local line profiling, install `requirements-local.txt`, set
`LOCAL_PROFILING_ENABLED=true`, and sign in as a Django superuser. Silk is then
available at `/silk/`; it is disabled unless explicitly enabled and cannot start
when `DJANGO_DEBUG=false`.

## Production

Run the API behind Nginx/Gunicorn. Set a strong secret and a separate metrics
token in the secret manager. Set `DJANGO_DEBUG=false`,
`LOCAL_PROFILING_ENABLED=false`, and use a small trace sampling ratio such as
`OTEL_TRACES_SAMPLER_ARG=0.05`. Point `OTEL_EXPORTER_OTLP_ENDPOINT` at a private
collector or Tempo endpoint.

Prometheus should scrape `/metrics/` over a private network. Replace
`targets/app.json` with production targets and add node, Postgres or Redis
exporters to `targets/exporters.json` as needed. The dashboard and alerts cover
API workload, errors, latency, DB/cache state and host disk capacity when the
corresponding exporter is enabled. Configure Alertmanager or Grafana Alerting
for paging.

The local stack retains 15 days of metrics, 48 hours of traces and 7 days of logs.
The included Loki/Tempo configuration is compact local infrastructure; use a
durable, authenticated, highly available deployment for production.

Production profiling is low overhead: request histograms, in-flight requests,
DB query counts/time, error rate and sampled traces. Use a log trace ID to open a
Tempo trace. Use Silk only in local or a short-lived private debugging environment.
