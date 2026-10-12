"""Public photos are served separately from paid digital originals."""

from pathlib import PurePosixPath
from typing import Any

from django.http import Http404, HttpRequest, HttpResponse
from django.views.static import serve


def serve_public_media(request: HttpRequest, path: str, **kwargs: Any) -> HttpResponse:
    parts = PurePosixPath(path).parts
    if not parts or parts[0] not in {'images', 'store-branding', 'user-profiles'} or '..' in parts:
        raise Http404
    return serve(request, path, **kwargs)
