from copy import deepcopy
from functools import lru_cache, wraps
from time import monotonic
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache


def invalidate_revision(namespace):
    cache.set(f'{namespace}:revision', uuid4().hex, timeout=None)


def versioned_lru_cache(namespace):
    """Bound local entries by time and a revision shared through Django's cache."""
    def decorate(function):
        @lru_cache(maxsize=getattr(settings, 'CACHE_MAX_ENTRIES', 256))
        def cached(revision, window, args):
            return function(*args)

        @wraps(function)
        def wrapped(*args):
            timeout = max(1, getattr(settings, 'CACHE_TIMEOUT', 300))
            revision = cache.get(f'{namespace}:revision')
            return deepcopy(cached(revision, int(monotonic() // timeout), args))

        wrapped.cache_clear = cached.cache_clear
        return wrapped
    return decorate
