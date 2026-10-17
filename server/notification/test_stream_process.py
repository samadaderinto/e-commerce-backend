from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient
from notification.realtime import _release_stream_connection
import yaml


@override_settings(ROOT_URLCONF='notification.stream_urls')
class RestrictedStreamProcessTests(SimpleTestCase):
    @override_settings(NOTIFICATION_STREAM_PROCESS=True)
    def test_dedicated_stream_releases_idle_database_connections(self) -> None:
        with patch('notification.realtime.close_old_connections') as close:
            _release_stream_connection()
            close.assert_called_once()

    def test_stream_still_requires_authentication_and_other_api_routes_are_absent(self) -> None:
        client = APIClient()
        self.assertEqual(client.get('/api/v1/notifications/stream/').status_code, 401)
        for path in ('/api/v1/products/', '/api/v1/auth/refresh/', '/admin/', '/metrics/'):
            self.assertEqual(client.get(path).status_code, 404)

    def test_stream_configuration_is_internal_and_migrations_are_disabled(self) -> None:
        root = Path(__file__).resolve().parents[2]
        services = yaml.safe_load((root / 'server/compose.yaml').read_text())['services']
        stream = services['notification-stream']
        self.assertEqual(stream['ports'], [])
        self.assertEqual(stream['environment']['RUN_MIGRATIONS'], 'false')
        self.assertEqual(stream['environment']['DJANGO_SETTINGS_MODULE'], 'codematics.stream_settings')
        self.assertEqual(stream['build']['args']['INSTALL_STREAM_POOL'], 'true')
        self.assertNotEqual(stream['environment']['PROMETHEUS_MULTIPROC_DIR'],
                            services['api']['environment']['PROMETHEUS_MULTIPROC_DIR'])
