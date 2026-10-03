# Observability documentation

Observability covers metrics, logs, traces, health checks and profiling. Monitoring
is the metrics/health/dashboard part. Log aggregation is the central collection
and search of application and infrastructure logs.

## Health endpoints

The backend exposes:

- `/health/live/`: process liveness.
- `/health/ready/`: readiness check.
- `/health/status/`: detailed dependency status, protected by
  `Authorization: Bearer $OBSERVABILITY_TOKEN`.
- `/metrics/`: Prometheus metrics, protected by
  `Authorization: Bearer $OBSERVABILITY_TOKEN`.

Health checks cover configured database and cache aliases. Results are generated
per request and are not cached. When `ELASTICSEARCH_ENABLED=true`, health checks
also include `search:elasticsearch`.

## Metrics

Metrics are defined in `server/observability/metrics.py` and recorded by
`server/observability/middleware.py`.

Important metrics:

- `commerce_http_requests_total`: request count by method, route and status.
- `commerce_http_duration_seconds`: request latency histogram by method and route.
- `commerce_http_inflight`: in-flight request gauge.
- `commerce_db_queries_total`: SQL query count by route.
- `commerce_db_duration_seconds`: SQL time histogram by route.
- `commerce_dependency_up`: dependency health from health checks.
- `commerce_dependency_check_seconds`: dependency check latency.

The latency histogram supports p50, p95 and p99 queries. Prometheus alerts include
high error rate, p95 latency and p99 tail latency.

Metric config files:

- `server/observability/metrics.py`: metric definitions and Prometheus rendering.
- `server/observability/middleware.py`: request timing, in-flight tracking,
  request IDs, trace IDs and database query timing.
- `server/observability/health.py`: database/cache dependency checks.
- `server/observability/views.py`: health and metrics HTTP views.
- `server/observability/config.py`: settings hook that enables middleware,
  JSON logging, optional Kafka logging, tracing and local profiling.
- `server/monitoring/prometheus.yml`: Prometheus scrape config.
- `server/monitoring/targets/app.json`: local application scrape target.
- `server/monitoring/targets/exporters.json`: optional exporter scrape targets.

## Dashboards and alerts

Grafana is available locally at `http://127.0.0.1:3002`. Its admin username and
password are `DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD` in
`server/.env`, matching the Django admin superuser.

The dashboard is provisioned from
`server/monitoring/grafana/dashboards/commerce-overview.json` and includes:

- request rate;
- 4xx/5xx error rate;
- API latency p50, p95 and p99;
- requests in flight;
- database queries and database time by route;
- dependency health and dependency check latency.
- Elasticsearch cluster health, search query rate and JVM heap usage.

Prometheus alert rules live in `server/monitoring/alerts.yml`.

Default alerts:

| Alert | Signal | Threshold |
| --- | --- | --- |
| `CommerceScrapeUnavailable` | `up{job="commerce"}` | down for 2 minutes |
| `CommerceDependencyUnavailable` | `commerce_dependency_up` | any dependency down for 1 minute |
| `CommerceHighErrorRate` | 5xx request ratio | more than 5% over 5 minutes with traffic |
| `CommerceSlowRequests` | API p95 latency | above 1 second for 10 minutes |
| `CommerceTailLatencyHigh` | API p99 latency | above 2.5 seconds for 10 minutes |
| `CommerceHostDiskLow` | node filesystem free ratio | below 10% for 10 minutes |
| `CommerceElasticsearchExporterUnavailable` | Elasticsearch exporter scrape | down for 2 minutes |
| `CommerceElasticsearchClusterRed` | Elasticsearch cluster status | red for 2 minutes |
| `CommerceElasticsearchHeapHigh` | Elasticsearch JVM heap usage | above 85% for 10 minutes |

Optional exporters:

- `node-exporter`: enabled with the `linux-host` Compose profile.
- `postgres-exporter`: enabled with the `postgres` Compose profile and
  `POSTGRES_EXPORTER_DSN`.
- `redis-exporter`: enabled with the `redis` Compose profile and
  `REDIS_EXPORTER_ADDR`.
- `elasticsearch-exporter`: enabled by default in the monitoring Compose stack
  and points at `ELASTICSEARCH_EXPORTER_URI`.

## Logs

Django writes JSON logs to stdout through `observability.logging.JsonFormatter`.
Each request includes a request ID and sampled trace ID. Request logs include
method, route template, status, duration, database query count and database time.
Exception logs include exception type and stack metadata without request bodies,
cookies, authorization headers, SQL parameters or provider credentials.

Alloy collects Docker container stdout through the Docker socket and sends logs
to Loki. In Grafana Explore, choose the Loki data source and use queries like:

```logql
{service_name="api"}
{service_name="api"} | json | level="ERROR"
{service_name="api"} | json | status_code >= 500
{service_name="api"} | json | request_id="paste-request-id-here"
{service_name="postgres"}
{service_name="redis"}
```

Keep Loki labels low-cardinality. Service, environment, version and container are
good labels. Request IDs, user IDs and order IDs should stay in the JSON body.

Log config files:

- `server/observability/logging.py`: JSON formatter, request context and optional
  best-effort Kafka log handler.
- `server/monitoring/alloy.alloy`: Docker discovery, relabeling and Loki output.
- `server/monitoring/loki.yml`: Loki local config and retention.
- `server/monitoring/grafana/provisioning/datasources/datasources.yml`:
  Grafana datasource registration for Loki, Prometheus and Tempo.

Alloy labels Docker logs with:

- `service_name`: Docker Compose service name such as `api`, `postgres` or
  `redis`;
- `container`: Docker container name without the leading slash;
- `compose_project`: Compose project name;
- `image`: container image;
- `environment`: `local`;
- `platform`: `docker`.

Kafka logging config is intentionally opt-in:

| Variable | Purpose |
| --- | --- |
| `KAFKA_LOGGING_ENABLED` | Adds the Kafka log handler when `true` |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka brokers |
| `KAFKA_LOG_TOPIC` | Topic used by the Kafka log handler |

## Traces

Tempo is included for local trace storage. Enable tracing with:

```sh
OTEL_TRACING_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
OTEL_TRACES_SAMPLER_ARG=1.0
```

Use a lower sampling ratio in production, such as `0.05`, and send traces to a
private collector or managed tracing backend.

Trace config files:

- `server/observability/tracing.py`: tracing setup helper.
- `server/monitoring/tempo.yml`: local Tempo config.
- `server/monitoring/compose.yaml`: exposes Tempo OTLP HTTP on
  `127.0.0.1:4318`.

Trace variables:

| Variable | Purpose |
| --- | --- |
| `OTEL_TRACING_ENABLED` | Enables tracing setup |
| `OTEL_SERVICE_NAME` | Service name shown in tracing backend |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint |
| `OTEL_TRACES_SAMPLER_ARG` | Sampling ratio |

## Profiling

Local request profiling uses Silk and is disabled by default. Enable it only with
`DJANGO_DEBUG=true`:

```sh
LOCAL_PROFILING_ENABLED=true
```

Silk is available at `/silk/` for active superusers. It must stay disabled in
normal production.

Profiling config:

| Variable | Purpose |
| --- | --- |
| `LOCAL_PROFILING_ENABLED` | Enables Silk and Python profiling hooks |
| `DJANGO_DEBUG` | Must be `true` for local profiling |

The settings hook refuses to start with `LOCAL_PROFILING_ENABLED=true` when
`DJANGO_DEBUG=false`.

## Documentation maintenance

Update this file when changing health endpoints, metrics, histogram buckets,
alert thresholds, dashboard panels, log fields, Loki/Alloy behavior, trace
settings, profiling behavior or observability environment variables.
