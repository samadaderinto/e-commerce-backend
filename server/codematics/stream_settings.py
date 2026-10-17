"""Restricted notification-stream process using the normal auth/security stack."""
from .storefront_settings import *  # noqa: F403

ROOT_URLCONF = 'notification.stream_urls'
NOTIFICATION_STREAM_PROCESS = True
# SSE generators must not retain one idle database socket per stream thread.
DATABASES = {  # noqa: F405
    alias: {**config, 'CONN_MAX_AGE': 0}
    for alias, config in DATABASES.items()  # noqa: F405
}
for _database in DATABASES.values():
    if _database['ENGINE'].endswith('postgresql'):
        # Returning a connection must not create a new authenticated DB socket
        # on every heartbeat. A small process-wide pool bounds physical sockets.
        _database['OPTIONS'] = {
            **_database.get('OPTIONS', {}),
            'pool': {'min_size': 0, 'max_size': 4, 'timeout': 3},
        }
