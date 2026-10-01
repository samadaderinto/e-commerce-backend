# Server observability

The backend owns the main observability stack.

## Endpoints

- `/health/live/`
- `/health/ready/`
- `/health/status/`
- `/metrics/`

Detailed health and metrics require `Authorization: Bearer $OBSERVABILITY_TOKEN`.

## Stack

- Prometheus: metrics and alerts.
- Grafana: dashboards and Explore.
- Loki: logs.
- Alloy: Docker stdout log collector.
- Tempo: local traces.
- Elasticsearch exporter: search health and JVM metrics.

## Logs

Django logs JSON to stdout. Alloy collects container logs into Loki. In Grafana
Explore:

```logql
{service_name="api"}
{service_name="api"} | json | level="ERROR"
{service_name="elasticsearch"}
```

## Alerts

Alerts cover scrape health, dependency health, error rate, p95/p99 latency, disk,
Elasticsearch exporter availability, Elasticsearch red cluster health and high JVM
heap.
