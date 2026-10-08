from io import StringIO

from django.contrib.auth.hashers import make_password
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.management.commands.populate_fake_data import Command
from core.models import User
from product.models import Product
from store.models import Store, StoreEarningsLedger
from store.services import calculate_store_tier


@override_settings(DEBUG=True)
class DemoScenarioTests(TestCase):
    def test_accounts_ownership_badges_and_repeated_scenarios(self):
        command = Command(stdout=StringIO())
        users = command.seed_users(12, make_password('Demo-password-123!'))
        stores = command.seed_stores(3, users)
        command.seed_scenarios(users)
        client = APIClient()
        self.assertEqual(client.post('/api/v1/auth/login/', {
            'email': 'shopper@proace.local', 'password': 'Demo-password-123!',
        }, format='json').status_code, 200)
        admin = User.objects.get(email='admin@proace.local')
        self.assertTrue(admin.is_superuser and admin.is_staff and not admin.is_business_admin)
        biz_admin = User.objects.get(email='business-admin@proace.local')
        self.assertTrue(biz_admin.is_business_admin and biz_admin.is_staff and not biz_admin.is_superuser)
        staff = User.objects.get(email='staff@proace.local')
        self.assertTrue(staff.is_staff and not staff.is_superuser and not staff.is_business_admin)
        for email in ['blocked-staff@proace.local', 'unverified@proace.local']:
            self.assertFalse(User.objects.get(email=email).is_active)
            self.assertEqual(client.post('/api/v1/auth/login/', {
                'email': email, 'password': 'Demo-password-123!',
            }, format='json').status_code, 401)
        self.assertEqual(Store.objects.filter(user__email='seller@proace.local').count(), 1)
        self.assertEqual(Store.objects.filter(user__email='shopper@proace.local').count(), 0)
        self.assertGreater(Store.objects.filter(user__email='merchant@proace.local').count(), 1)
        for tier in ['starter', 'booster', 'accelerator', 'power', 'mega', 'legendary']:
            self.assertEqual(calculate_store_tier(Store.objects.get(username='demo-' + tier))['tier'], tier)
        self.assertTrue(stores[0].is_official)
        self.assertEqual(Store.objects.get(username='demo-pending').status, Store.STATUS_PENDING)
        self.assertIsNone(Store.objects.get(username='demo-unverified').verified_at)
        self.assertEqual(Store.objects.get(username='demo-blocked').status, Store.STATUS_BLOCKED)
        self.assertFalse(Product.objects.filter(store__username='demo-empty').exists())
        self.assertTrue(Product.objects.filter(visibility=False).exists())
        self.assertTrue(Product.objects.filter(available=0).exists())
        counts = (Store.objects.count(), Product.objects.count(), StoreEarningsLedger.objects.count())
        command.seed_scenarios(users)
        self.assertEqual(counts, (Store.objects.count(), Product.objects.count(), StoreEarningsLedger.objects.count()))
