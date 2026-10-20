from __future__ import annotations

from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

from django.apps import apps
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings

from notification.delivery import queue_email_delivery
from core.models import User
from notification.models import NotificationDelivery, PushDevice
from notification.tasks import deliver_notification_task
from notification.views import create_notification


class DeliveryLeaseAuditTests(TestCase):
    @override_settings(FCM_ENABLED=True)
    def test_stale_push_worker_cannot_replace_newer_retry_token_metadata(self) -> None:
        user = User.objects.create_user(email='push-lease@test.local', password='test')
        notification = create_notification(user, 'Fixture', data={'email': False})
        delivery = NotificationDelivery.objects.create(
            channel=NotificationDelivery.CHANNEL_PUSH, notification=notification, recipient=user,
        )
        PushDevice.objects.create(user=user, token='fixture-token')

        def provider_call(*args: object, **kwargs: object) -> SimpleNamespace:
            NotificationDelivery.objects.filter(pk=delivery.pk).update(
                attempts=2, status=NotificationDelivery.STATUS_PROCESSING,
                metadata={'pending_tokens': ['newer-token']},
            )
            return SimpleNamespace(success_count=1, responses=[SimpleNamespace(success=True)])

        with patch('notification.tasks._firebase_app', return_value=object()), patch(
            'firebase_admin.messaging.send_each_for_multicast', side_effect=provider_call,
        ):
            result = deliver_notification_task(delivery.pk)
        self.assertEqual(result['status'], 'stale')
        delivery.refresh_from_db()
        self.assertEqual(delivery.metadata, {'pending_tokens': ['newer-token']})
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_PROCESSING)

    def test_stale_worker_cannot_overwrite_a_newer_processing_attempt(self) -> None:
        for fails in (False, True):
            with self.subTest(fails=fails):
                delivery = queue_email_delivery(
                    'lease@test.local', 'Fixture', 'Fixture body', delivery_key=str(fails),
                )

                def newer_attempt(_delivery: NotificationDelivery) -> None:
                    NotificationDelivery.objects.filter(pk=delivery.pk).update(
                        attempts=2, status=NotificationDelivery.STATUS_PROCESSING,
                        last_error='Newer attempt owns this row',
                    )
                    if fails:
                        raise RuntimeError('Controlled old worker failure')

                with patch('notification.tasks._deliver_email', side_effect=newer_attempt):
                    deliver_notification_task(delivery.pk)
                delivery.refresh_from_db()
                self.assertEqual(delivery.status, NotificationDelivery.STATUS_PROCESSING)
                self.assertEqual(delivery.attempts, 2)
                self.assertEqual(delivery.last_error, 'Newer attempt owns this row')


@skipUnless(connection.vendor == 'postgresql', 'Worker interleaving requires PostgreSQL.')
class DeliveryConcurrencyAuditTests(TransactionTestCase):
    available_apps = [config.name for config in apps.get_app_configs()]

    def test_late_failed_worker_cannot_reopen_successfully_retried_delivery(self) -> None:
        with patch('notification.delivery._dispatch_delivery'):
            delivery = queue_email_delivery('parallel-delivery@test.local', 'Fixture', 'Fixture')
        entered = Event()
        release = Event()

        def provider_call(claim: NotificationDelivery) -> None:
            if claim.attempts == 1:
                entered.set()
                if not release.wait(timeout=20):
                    raise AssertionError('Retry fixture did not release the old worker.')
                raise RuntimeError('Controlled delayed failure')

        def old_worker() -> None:
            close_old_connections()
            try:
                deliver_notification_task(delivery.pk)
            finally:
                connection.close()

        with patch('notification.tasks._deliver_email', side_effect=provider_call), ThreadPoolExecutor(max_workers=1) as pool:
            old = pool.submit(old_worker)
            try:
                self.assertTrue(entered.wait(timeout=20))
                NotificationDelivery.objects.filter(pk=delivery.pk).update(status=NotificationDelivery.STATUS_QUEUED)
                deliver_notification_task(delivery.pk)
            finally:
                release.set()
            old.result(timeout=20)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_SENT)
        self.assertEqual(delivery.attempts, 2)
        self.assertEqual(delivery.last_error, '')
