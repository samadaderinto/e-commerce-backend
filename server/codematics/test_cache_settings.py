from __future__ import annotations

from django.conf import settings

import codematics.settings as runtime_settings


def test_runtime_cache_backend_is_redis() -> None:
    default_cache = runtime_settings.CACHES["default"]

    assert default_cache["BACKEND"] == "django_redis.cache.RedisCache"
    assert default_cache["LOCATION"].startswith(("redis://", "rediss://", "unix://"))
    assert default_cache["OPTIONS"]["IGNORE_EXCEPTIONS"] is False


def test_test_settings_keep_cache_isolated_from_redis() -> None:
    assert settings.CACHES["default"]["BACKEND"] == "django.core.cache.backends.locmem.LocMemCache"
