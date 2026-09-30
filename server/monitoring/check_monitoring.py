"""Verify live scrape targets and core metrics; exit nonzero for coverage gaps."""
import argparse
import json
import sys
from urllib.parse import urlencode
from urllib.request import urlopen


def verify(base_url):
    def get(path):
        with urlopen(base_url.rstrip('/') + path, timeout=10) as response:
            result = json.load(response)
        if result.get('status') != 'success':
            raise ValueError('Prometheus returned an unsuccessful response')
        return result['data']

    errors = []
    targets = get('/api/v1/targets')['activeTargets']
    for service in ['api', 'postgres', 'redis', 'elasticsearch', 'host', 'containers', 'grafana', 'loki', 'tempo']:
        matches = [target for target in targets if target['labels'].get('service') == service]
        if not matches or any(target['health'] != 'up' for target in matches):
            errors.append(f'{service}: scrape target missing or unhealthy')
    checks = {
        'PostgreSQL connection': 'pg_up == 1',
        'Redis connection': 'redis_up == 1',
        'Elasticsearch health': 'elasticsearch_cluster_health_status{color=~"green|yellow"} == 1',
        'API dependency health': 'commerce_dependency_up',
        'host CPU': 'node_cpu_seconds_total',
        'host memory': 'node_memory_MemTotal_bytes',
        'host filesystem': 'node_filesystem_size_bytes',
    }
    for service in ['api', 'postgres', 'redis', 'elasticsearch']:
        for metric in ['container_cpu_usage_seconds_total', 'container_memory_working_set_bytes']:
            checks[f'{service} {metric}'] = metric + '{container_label_com_docker_compose_service="' + service + '"}'
    for label, query in checks.items():
        result = get('/api/v1/query?' + urlencode({'query': query}))['result']
        if not result:
            errors.append(f'{label}: no matching live metric')
        elif label == 'API dependency health' and any(float(row['value'][1]) != 1 for row in result):
            errors.append('API dependency health: an application dependency is unavailable')
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:9090')
    args = parser.parse_args()
    try:
        failures = verify(args.url)
    except (OSError, ValueError, KeyError) as error:
        print(f'Monitoring verification failed: {error}', file=sys.stderr)
        sys.exit(1)
    for failure in failures:
        print(f'FAIL: {failure}', file=sys.stderr)
    if failures:
        sys.exit(1)
    print('All required scrape targets and API, database, cache, search, host and container metrics are healthy.')
