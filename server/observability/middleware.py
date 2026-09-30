from contextlib import ExitStack
import logging
from time import perf_counter
from uuid import uuid4

from django.db import connections
from opentelemetry.trace import SpanKind, StatusCode

from .logging import request_context
from .metrics import DB_DURATION, DB_QUERIES, DURATION, INFLIGHT, REQUESTS
from .tracing import tracer

logger = logging.getLogger('codematics.requests')
EXCLUDED = {'/metrics/', '/health/live/', '/health/ready/', '/health/status/'}
METHODS = {'GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'}


class ObservabilityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in EXCLUDED:
            return self.get_response(request)
        method = request.method if request.method in METHODS else 'OTHER'
        request_id = uuid4().hex
        request.request_id = request_id
        started = perf_counter()
        queries = 0
        sql_seconds = 0
        status = 500
        instrument = tracer()

        def execute(executor, sql, params, many, context):
            nonlocal queries, sql_seconds
            queries += 1
            before = perf_counter()
            try:
                if queries <= 100 and span.is_recording():
                    with instrument.start_as_current_span('database.query', record_exception=False,
                                                          set_status_on_exception=False) as query_span:
                        query_span.set_attribute('db.system', context['connection'].vendor)
                        try:
                            return executor(sql, params, many, context)
                        except Exception:
                            query_span.set_status(StatusCode.ERROR)
                            raise
                return executor(sql, params, many, context)
            finally:
                sql_seconds += perf_counter() - before

        with instrument.start_as_current_span('HTTP', kind=SpanKind.SERVER,
                                              record_exception=False, set_status_on_exception=False) as span:
            trace_id = span.get_span_context().trace_id
            token = request_context.set({'request_id': request_id, 'trace_id': f'{trace_id:032x}' if trace_id else None})
            INFLIGHT.inc()
            try:
                with ExitStack() as stack:
                    for connection in connections.all():
                        stack.enter_context(connection.execute_wrapper(execute))
                    result = self.get_response(request)
                status = result.status_code
                result['X-Request-ID'] = request_id
                return result
            finally:
                elapsed = perf_counter() - started
                match = getattr(request, 'resolver_match', None)
                route = match.route if match else '__unmatched__'
                span.update_name(f'{method} {route}')
                span.set_attribute('http.route', route)
                span.set_attribute('http.request.method', method)
                span.set_attribute('http.response.status_code', status)
                span.set_attribute('commerce.db.queries', queries)
                span.set_attribute('commerce.db.duration_ms', sql_seconds * 1000)
                span.set_attribute('commerce.request_id', request_id)
                if status >= 500:
                    span.set_status(StatusCode.ERROR)
                REQUESTS.labels(method, route, str(status)).inc()
                DURATION.labels(method, route).observe(elapsed)
                DB_QUERIES.labels(route).inc(queries)
                DB_DURATION.labels(route).observe(sql_seconds)
                INFLIGHT.dec()
                logger.info('request_complete', extra={
                    'route': route, 'method': method, 'status_code': status,
                    'duration_ms': round(elapsed * 1000, 3), 'db_queries': queries,
                    'db_duration_ms': round(sql_seconds * 1000, 3),
                })
                request_context.reset(token)
