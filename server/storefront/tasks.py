"""Background preparation of the most common public catalog request."""

from celery import shared_task
from django.core.cache import cache
from django.http import HttpRequest
from urllib.parse import urlsplit


@shared_task(ignore_result=True)
def warm_catalog_snapshot() -> None:
    from .views import ProductsView
    from .catalog_cache import WARM_LOCK_KEY, WARM_URL_KEY

    cache.delete(WARM_LOCK_KEY)
    url = cache.get(WARM_URL_KEY)
    if not isinstance(url, str):
        return
    origin = urlsplit(url)
    request = HttpRequest()
    request.method = "GET"
    request.path = "/api/v1/products/"
    request.META["HTTP_HOST"] = origin.netloc
    request.META["SERVER_NAME"] = origin.hostname or "localhost"
    request.META["SERVER_PORT"] = str(origin.port or (443 if origin.scheme == "https" else 80))
    request.META["wsgi.url_scheme"] = origin.scheme
    response = ProductsView.as_view()(request)
    if response.status_code != 200:
        raise RuntimeError("Catalog snapshot warming failed")
