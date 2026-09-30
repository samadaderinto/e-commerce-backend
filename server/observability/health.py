from time import perf_counter
from uuid import uuid4

from django.conf import settings
from django.core.cache import caches
from django.db import connections


def check_dependencies():
    results = {}
    for alias in settings.DATABASES:
        started = perf_counter()
        backend = settings.DATABASES[alias]['ENGINE'].rsplit('.', 1)[-1]
        status = 'ok'
        try:
            with connections[alias].cursor() as cursor:
                cursor.execute('SELECT 1')
                if cursor.fetchone()[0] != 1:
                    status = 'error'
        except Exception:
            status = 'error'
        results[f'database:{alias}'] = {
            'status': status, 'backend': backend, 'duration_seconds': perf_counter() - started,
        }
    for alias in settings.CACHES:
        started = perf_counter()
        backend = settings.CACHES[alias]['BACKEND'].rsplit('.', 1)[-1]
        status = 'ok'
        key = f'observability:health:{uuid4().hex}'
        cache = caches[alias]
        try:
            cache.set(key, 'ok', timeout=10)
            # Detect Redis outages even with IGNORE_EXCEPTIONS enabled.
            if cache.get(key) != 'ok':
                status = 'error'
        except Exception:
            status = 'error'
        finally:
            try:
                cache.delete(key)
            except Exception:
                status = 'error'
        results[f'cache:{alias}'] = {
            'status': status, 'backend': backend, 'duration_seconds': perf_counter() - started,
        }
    return results
