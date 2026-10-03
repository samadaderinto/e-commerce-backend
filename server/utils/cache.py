from __future__ import annotations

from copy import deepcopy
from functools import lru_cache, wraps
from time import monotonic
from typing import Any, Callable, TypeVar
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache

F = TypeVar('F', bound=Callable[..., Any])


def invalidate_revision(namespace: str) -> None:
    cache.set(f'{namespace}:revision', uuid4().hex, timeout=None)


def versioned_lru_cache(namespace: str) -> Callable[[F], F]:
    """Bound local entries by time and a revision shared through Django's cache."""
    def decorate(function: F) -> F:
        @lru_cache(maxsize=getattr(settings, 'CACHE_MAX_ENTRIES', 256))
        def cached(revision: Any, window: int, args: tuple[Any, ...]) -> Any:
            return function(*args)

        @wraps(function)
        def wrapped(*args: Any) -> Any:
            timeout = max(1, getattr(settings, 'CACHE_TIMEOUT', 300))
            revision = cache.get(f'{namespace}:revision')
            return deepcopy(cached(revision, int(monotonic() // timeout), args))

        wrapped.cache_clear = cached.cache_clear  # type: ignore[attr-defined]
        return wrapped  # type: ignore[return-value]
    return decorate

