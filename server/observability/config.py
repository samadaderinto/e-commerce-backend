"""Shared settings for both the legacy API and the storefront."""
import os

from django.core.exceptions import ImproperlyConfigured


def configure(namespace):
    namespace['OBSERVABILITY_TOKEN'] = os.environ.get('OBSERVABILITY_TOKEN', '')
    namespace['KAFKA_BOOTSTRAP_SERVERS'] = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    namespace['KAFKA_LOG_TOPIC'] = os.environ.get('KAFKA_LOG_TOPIC', 'commerce.logs')
    namespace['OTEL_TRACING_ENABLED'] = os.environ.get('OTEL_TRACING_ENABLED', 'false').lower() == 'true'
    namespace['LOCAL_PROFILING_ENABLED'] = os.environ.get('LOCAL_PROFILING_ENABLED', 'false').lower() == 'true'
    if namespace['LOCAL_PROFILING_ENABLED'] and not namespace['DEBUG']:
        raise ImproperlyConfigured('LOCAL_PROFILING_ENABLED requires DJANGO_DEBUG=true.')
    apps = namespace['INSTALLED_APPS']
    middleware = namespace['MIDDLEWARE']
    apps[:] = [app for app in apps if app != 'silk']
    middleware[:] = [item for item in middleware if item not in (
        'silk.middleware.SilkyMiddleware', 'observability.middleware.ObservabilityMiddleware',
    )]
    if namespace['LOCAL_PROFILING_ENABLED']:
        apps.append('silk')
        middleware.insert(0, 'silk.middleware.SilkyMiddleware')
    middleware.insert(0, 'observability.middleware.ObservabilityMiddleware')
    namespace['SILKY_AUTHENTICATION'] = True
    namespace['SILKY_AUTHORISATION'] = True
    namespace['SILKY_PERMISSIONS'] = lambda user: user.is_active and user.is_superuser
    namespace['SILKY_MAX_RECORDED_REQUESTS'] = 1000
    namespace['SILKY_MAX_REQUEST_BODY_SIZE'] = 0
    namespace['SILKY_MAX_RESPONSE_BODY_SIZE'] = 0
    namespace['SILKY_PYTHON_PROFILER'] = namespace['LOCAL_PROFILING_ENABLED']
    namespace['SILKY_PYTHON_PROFILER_BINARY'] = False
    namespace['SILKY_INTERCEPT_PERCENT'] = 10
    namespace['SILKY_IGNORE_PATHS'] = ['/health/live/', '/health/ready/', '/health/status/', '/metrics/']
    namespace['LOGGING']['formatters']['standard'] = {'()': 'observability.logging.JsonFormatter'}
    namespace['LOGGING']['handlers']['kafka'] = {
        'class': 'observability.logging.KafkaLogHandler',
    }
    namespace['LOGGING']['loggers']['codematics']['handlers'].append('kafka')
