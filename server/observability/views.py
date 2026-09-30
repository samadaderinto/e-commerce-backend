import secrets

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_safe
from prometheus_client import CONTENT_TYPE_LATEST

from .health import check_dependencies
from .metrics import render_metrics


def authorized(request):
    token = settings.OBSERVABILITY_TOKEN
    return bool(token) and secrets.compare_digest(
        request.headers.get('Authorization', ''), f'Bearer {token}',
    )


def response(data, status=200):
    result = JsonResponse(data, status=status)
    result['Cache-Control'] = 'no-store'
    return result


@require_safe
def live(request):
    return response({'status': 'ok'})


@require_safe
def ready(request):
    healthy = all(item['status'] == 'ok' for item in check_dependencies().values())
    return response({'status': 'ok' if healthy else 'unavailable'}, 200 if healthy else 503)


@require_safe
def health_status(request):
    if not authorized(request):
        return response({'error': 'forbidden'}, 403)
    dependencies = check_dependencies()
    healthy = all(item['status'] == 'ok' for item in dependencies.values())
    return response({'status': 'ok' if healthy else 'unavailable', 'dependencies': dependencies},
                    200 if healthy else 503)


@require_safe
def metrics(request):
    if not authorized(request):
        return response({'error': 'forbidden'}, 403)
    result = HttpResponse(render_metrics(check_dependencies()), content_type=CONTENT_TYPE_LATEST)
    result['Cache-Control'] = 'no-store'
    return result
