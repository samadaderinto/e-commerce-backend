from datetime import datetime, timezone as datetime_timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase
from django.utils import timezone
from store.serializers import DashboardQuerySerializer


class DisplayTimezoneTests(SimpleTestCase):
    def test_dashboard_accepts_iana_zones_and_rejects_invalid_zones(self) -> None:
        for zone in ('UTC', 'America/Los_Angeles', 'Africa/Lagos', 'Asia/Tokyo'):
            serializer = DashboardQuerySerializer(data={'time_zone': zone})
            self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer = DashboardQuerySerializer(data={'time_zone': 'Not/AZone'})
        self.assertFalse(serializer.is_valid())

    def test_local_dashboard_day_changes_without_changing_utc_clock(self) -> None:
        instant = datetime(2026, 10, 8, 2, tzinfo=datetime_timezone.utc)
        with patch('django.utils.timezone.now', return_value=instant):
            with timezone.override(ZoneInfo('America/Los_Angeles')):
                self.assertEqual(timezone.localdate().isoformat(), '2026-10-07')
                self.assertEqual(timezone.now(), instant)
            with timezone.override(ZoneInfo('Asia/Tokyo')):
                self.assertEqual(timezone.localdate().isoformat(), '2026-10-08')
