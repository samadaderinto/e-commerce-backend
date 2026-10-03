from .celery import app as celery_app

try:
    import rest_framework.serializers as _serializers
    if not hasattr(_serializers, 'NullBooleanField'):
        _serializers.NullBooleanField = _serializers.BooleanField
except ImportError:
    pass

__all__ = ('celery_app',)
