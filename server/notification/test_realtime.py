from unittest.mock import MagicMock, patch
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from core.models import User
from store.models import Store
from product.models import Product
from notification.models import Notification
from notification.events import operators
from notification.realtime import publish, user_channel


@override_settings(ROOT_URLCONF='notification.tests')
class RealtimeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email='owner@events.test', password='test')
        self.staff = User.objects.create_user(email='staff@events.test', password='test', is_staff=True)
        self.unassigned = User.objects.create_user(email='other@events.test', password='test', is_staff=True)
        self.admin = User.objects.create_user(email='admin@events.test', password='test', is_business_admin=True)
        self.store = Store.objects.create(user=self.owner, name='Live shop')
        self.store.assigned_staff.add(self.staff)

    def test_publish_happens_only_after_commit(self):
        with patch('notification.realtime.broker') as broker:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                publish(self.owner.pk, {'event': 'store.changed'})
                broker.assert_not_called()
            self.assertEqual(len(callbacks), 1)
            broker.return_value.publish.assert_called_once()
            self.assertEqual(broker.return_value.publish.call_args.args[0], user_channel(self.owner.pk))

    def test_low_stock_alert_is_tenant_scoped(self):
        product = Product.objects.create(store=self.store, title='Item', price=10, discount=0, description='Item', available=9, category='electronics')
        with patch('notification.realtime.broker'), patch('notification.views._send_external_notification'), patch('notification.search.schedule_index_notification'):
            with self.captureOnCommitCallbacks(execute=True):
                product.available = 4
                product.save()
        recipients = set(Notification.objects.filter(data__event='inventory_low').values_list('recipient_id', flat=True))
        self.assertEqual(recipients, {self.owner.pk, self.staff.pk, self.admin.pk})
        self.assertNotIn(self.unassigned.pk, set(operators(self.store).values_list('pk', flat=True)))

    def test_stream_requires_authentication_and_ignores_requested_rooms(self):
        client = APIClient()
        self.assertEqual(client.get('/notifications/stream/').status_code, 401)
        client.force_authenticate(self.owner)
        fake = MagicMock()
        with patch('notification.realtime.broker', return_value=fake):
            response = client.get('/notifications/stream/?room=admin:notifications')
            self.assertEqual(response.status_code, 200)
            fake.pubsub.return_value.subscribe.assert_called_once_with(user_channel(self.owner.pk))
            self.assertIn(b'event: ready', next(iter(response.streaming_content)))
            response.close()
            fake.pubsub.return_value.close.assert_called_once()

    def test_rolled_back_event_is_not_published(self):
        from django.db import transaction
        with patch('notification.realtime.broker') as broker:
            with self.captureOnCommitCallbacks(execute=True):
                try:
                    with transaction.atomic():
                        publish(self.owner.pk, {'event': 'store.changed'})
                        raise ValueError('rollback')
                except ValueError:
                    pass
            broker.assert_not_called()

    def test_open_stream_closes_when_account_access_is_revoked(self) -> None:
        client = APIClient()
        client.force_authenticate(self.owner)
        fake = MagicMock()
        fake.pubsub.return_value.get_message.return_value = None
        with patch('notification.realtime.broker', return_value=fake):
            response = client.get('/notifications/stream/')
            iterator = iter(response.streaming_content)
            self.assertIn(b'event: ready', next(iterator))
            self.assertIn(b'heartbeat', next(iterator))
            User.objects.filter(pk=self.owner.pk).update(is_active=False)
            with self.assertRaises(StopIteration):
                next(iterator)
            fake.pubsub.return_value.close.assert_called_once()

    @override_settings(NOTIFICATION_STREAM_PROCESS=True)
    def test_stream_cleanup_never_closes_an_enclosing_transaction(self) -> None:
        from notification.realtime import _release_stream_connection

        with patch('notification.realtime.close_old_connections') as close:
            _release_stream_connection()
            close.assert_not_called()

    def test_new_store_reaches_both_administrator_roles_and_staff(self):
        with patch('notification.realtime.broker'), patch('notification.views._send_external_notification'), patch('notification.search.schedule_index_notification'):
            with self.captureOnCommitCallbacks(execute=True):
                Store.objects.create(user=self.owner, name='Another store')
        self.assertEqual(set(Notification.objects.filter(data__event='store_created').values_list('recipient_id', flat=True)), {self.staff.pk, self.unassigned.pk, self.admin.pk})
        self.assertEqual(set(Notification.objects.filter(data__event='verification_submitted').values_list('recipient_id', flat=True)), {self.admin.pk})
