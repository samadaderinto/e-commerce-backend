"""Commit-only live events; database notifications remain the durable inbox."""
import json
import logging
import time
from collections.abc import Iterator
from django.conf import settings
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.http import StreamingHttpResponse
from redis import Redis, RedisError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def _release_stream_connection() -> None:
    if getattr(settings, 'NOTIFICATION_STREAM_PROCESS', False) and not connection.in_atomic_block:
        close_old_connections()


def broker():
    return Redis.from_url(getattr(settings, 'REALTIME_REDIS_URL', None) or getattr(settings, 'CACHE_URL', None) or 'redis://127.0.0.1:6379/0',
                          socket_connect_timeout=2, socket_timeout=3, decode_responses=True)


def user_channel(user_id):
    return f'commerce:events:user:{user_id}'


def publish(user_id, payload):
    def committed():
        try:
            client = broker()
            try:
                client.publish(user_channel(user_id), json.dumps(payload))
            finally:
                client.close()
        except RedisError:
            logger.warning('Live event delivery unavailable; durable inbox retained.')
    transaction.on_commit(committed)


def encode_event(name, payload):
    return f'event: {name}\ndata: {json.dumps(payload)}\n\n'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stream(request):
    """No client-selected rooms: each connection can receive its own inbox only."""
    client = broker()
    subscription = client.pubsub(ignore_subscribe_messages=True)
    try:
        subscription.subscribe(user_channel(request.user.pk))
    except RedisError:
        subscription.close()
        client.close()
        return Response({'detail': 'Live events temporarily unavailable.'}, status=503)
    user_id = request.user.pk
    credential_version = request.user.credential_version
    def events() -> Iterator[str]:
        try:
            _release_stream_connection()
            yield 'retry: 3000\n\n' + encode_event('ready', {'resync': True})
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                # Recheck account access during a live connection, not just at reconnect.
                from core.models import User
                allowed = User.objects.filter(
                    pk=user_id, is_active=True, must_change_password=False,
                    credential_version=credential_version,
                ).exists()
                _release_stream_connection()
                if not allowed:
                    return
                message = subscription.get_message(timeout=1)
                if message and message['type'] == 'message':
                    yield encode_event('state', json.loads(message['data']))
                else:
                    yield ': heartbeat\n\n'
        except RedisError:
            yield encode_event('resync', {'reason': 'broker_unavailable'})
        except DatabaseError:
            logger.warning('Stream access check unavailable.', exc_info=True)
            yield encode_event('resync', {'reason': 'access_check_unavailable'})
        finally:
            subscription.close()
            client.close()
            _release_stream_connection()
    response = StreamingHttpResponse(events(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache, no-transform'
    response['X-Accel-Buffering'] = 'no'
    return response
