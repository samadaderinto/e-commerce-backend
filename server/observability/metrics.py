import os

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, REGISTRY, generate_latest, multiprocess
from prometheus_client.core import GaugeMetricFamily


REQUESTS = Counter('commerce_http_requests_total', 'Completed API requests', ['method', 'route', 'status'])
DURATION = Histogram('commerce_http_duration_seconds', 'Time until response headers (not stream consumption)',
                     ['method', 'route'], buckets=(.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10))
INFLIGHT = Gauge('commerce_http_inflight', 'Requests currently being handled', multiprocess_mode='livesum')
DB_QUERIES = Counter('commerce_db_queries_total', 'SQL calls by API route', ['route'])
DB_DURATION = Histogram('commerce_db_duration_seconds', 'Total SQL time per request', ['route'],
                        buckets=(.001, .005, .01, .025, .05, .1, .25, .5, 1, 5))


def render_metrics(health):
    if os.environ.get('PROMETHEUS_MULTIPROC_DIR'):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    else:
        registry = REGISTRY
    # Dependency checks describe this scrape, not a stale worker-local gauge.
    dependency_registry = CollectorRegistry()

    class Dependencies:
        def collect(self):
            up = GaugeMetricFamily('commerce_dependency_up', 'Dependency check result', labels=['dependency', 'backend'])
            latency = GaugeMetricFamily('commerce_dependency_check_seconds', 'Dependency check latency', labels=['dependency'])
            for name, result in health.items():
                up.add_metric([name, result['backend']], int(result['status'] == 'ok'))
                latency.add_metric([name], result['duration_seconds'])
            yield up
            yield latency

    dependency_registry.register(Dependencies())
    return generate_latest(registry) + generate_latest(dependency_registry)
