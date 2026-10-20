"""Account-scoped authentication limits do not merge unrelated proxy clients."""

import hashlib
from collections.abc import Mapping
from typing import Any
from rest_framework.request import Request
from rest_framework.settings import api_settings
from rest_framework.throttling import ScopedRateThrottle


class AccountAuthThrottle(ScopedRateThrottle):
    def get_rate(self) -> str | None:
        return self.THROTTLE_RATES.get(self.scope)

    def get_cache_key(self, request: Request, view: Any) -> str | None:
        if not isinstance(request.data, Mapping):
            return None
        action = getattr(view, 'kwargs', {}).get('action')
        email = request.data.get('email')
        if action in {'login', 'register', 'forgot'} and isinstance(email, str) and email.strip():
            email = email.strip().lower()
            identity = hashlib.sha256(email.encode()).hexdigest()
            return self.cache_format % {"scope": self.scope, "ident": identity}
        # Without an explicit proxy policy, forwarded headers are caller-controlled.
        identity = (
            self.get_ident(request)
            if api_settings.NUM_PROXIES is not None
            else request.META.get('REMOTE_ADDR')
        )
        if not identity:
            return None
        return self.cache_format % {'scope': f'{self.scope}_peer', 'ident': identity}


class ClientAuthThrottle(AccountAuthThrottle):
    """Add an independent limit only with an explicitly configured client boundary."""

    def get_cache_key(self, request: Request, view: Any) -> str | None:
        if api_settings.NUM_PROXIES is None:
            return None
        identity = self.get_ident(request)
        if not identity:
            return None
        return self.cache_format % {'scope': f'{self.scope}_client', 'ident': identity}
