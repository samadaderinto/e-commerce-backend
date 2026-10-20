from io import StringIO
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.test import TestCase, override_settings
from django.core.management import call_command, CommandError
from rest_framework.test import APIClient

from core.management.commands.populate_fake_data import Command
from cart.models import CartItem
from core.models import User
from product.models import Product
from staff.models import Post
from store.models import MerchantWallet, Store, StoreEarningsLedger
from store.services import calculate_store_tier


@override_settings(DEBUG=True)
class DemoScenarioTests(TestCase):
    def test_full_seed_includes_blog_tags_and_guaranteed_accounts(self) -> None:
        output = StringIO()
        call_command(
            "populate_fake_data",
            scale="small",
            password="Seed-regression-password-123!",
            stdout=output,
        )

        self.assertFalse(CartItem.objects.filter(
            product__product_type=Product.PRODUCT_TYPE_AFFILIATE_CLICKBANK,
        ).exists())
        self.assertTrue(Post.objects.filter(tags__name="engineering").exists())
        self.assertGreaterEqual(Product.objects.count(), 45)
        for email in (
            "admin@proace.local",
            "business-admin@proace.local",
            "staff@proace.local",
            "seller@proace.local",
            "merchant@proace.local",
            "shopper@proace.local",
            "buyer@proace.local",
        ):
            self.assertTrue(User.objects.filter(email=email).exists())
        self.assertNotIn("Seed-regression-password-123!", output.getvalue())

    def test_seeded_wallets_do_not_claim_stripe_is_connected(self):
        command = Command(stdout=StringIO())
        users = command.seed_users(12, make_password('Demo-password-123!'))
        command.seed_stores(3, users)
        merchant = User.objects.get(email='merchant@proace.local')
        wallet = MerchantWallet.objects.get(user=merchant)
        self.assertEqual(wallet.stripe_account_id, '')
        self.assertFalse(wallet.stripe_details_submitted)
        self.assertFalse(wallet.stripe_payouts_enabled)

        wallet.stripe_account_id = 'acct_mock_00001'
        wallet.stripe_details_submitted = True
        wallet.stripe_payouts_enabled = True
        wallet.save()
        command.seed_stores(3, users)
        wallet.refresh_from_db()
        self.assertEqual(wallet.stripe_account_id, '')
        self.assertFalse(wallet.stripe_details_submitted)
        self.assertFalse(wallet.stripe_payouts_enabled)

    def test_product_seed_builds_clickbank_links_with_demo_vendor(self):
        command = Command(stdout=StringIO())
        users = command.seed_users(12, make_password('Demo-password-123!'))
        stores = command.seed_stores(3, users)
        products = command.seed_products(20, stores)
        affiliate = next(
            product for product in products
            if product.product_type == Product.PRODUCT_TYPE_AFFILIATE_CLICKBANK
        )
        self.assertEqual(affiliate.affiliate_vendor_nickname, 'proace-demo-vendor')
        self.assertIn('vendor=proace-demo-vendor', affiliate.affiliate_hoplink)

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

    def test_populate_fake_data_preserves_existing_superuser_password(self):
        command = Command(stdout=StringIO())
        # First seed initial accounts
        command.seed_users(12, make_password('Initial-password-123!'))
        admin = User.objects.get(email='admin@proace.local')
        self.assertTrue(admin.check_password('Initial-password-123!'))

        # Change admin password to a custom password
        admin.set_password('Custom-admin-secret-999!')
        admin.save()
        self.assertTrue(admin.check_password('Custom-admin-secret-999!'))

        # Run clear_existing_data
        command.clear_existing_data()
        # Admin must NOT be deleted
        admin.refresh_from_db()
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password('Custom-admin-secret-999!'))

        # Run seed_users again with a different seed password
        command.seed_users(12, make_password('Overwriting-seed-password-456!'))
        admin.refresh_from_db()
        # Admin password must remain untouched
        self.assertTrue(admin.check_password('Custom-admin-secret-999!'))
        self.assertFalse(admin.check_password('Overwriting-seed-password-456!'))

        # Non-superusers should have the new seed password
        shopper = User.objects.get(email='shopper@proace.local')
        self.assertTrue(shopper.check_password('Overwriting-seed-password-456!'))

    def test_failed_seed_rolls_back_and_never_prints_password(self):
        output = StringIO()
        with patch.object(Command, 'seed_stores', side_effect=RuntimeError('fixture failure')):
            with self.assertRaisesRegex(RuntimeError, 'fixture failure'):
                call_command(
                    'populate_fake_data',
                    scale='small',
                    password='Hidden-seed-password-123!',
                    stdout=output,
                )

        self.assertFalse(User.objects.filter(email='shopper@proace.local').exists())
        self.assertNotIn('Hidden-seed-password-123!', output.getvalue())

    def test_seed_refuses_to_promote_regular_account_to_technical_admin(self):
        User.objects.create_user(
            email='admin@proace.local',
            password='Existing-user-password-123!',
            first_name='Existing',
            last_name='Account',
            gender='male',
        )

        with self.assertRaisesRegex(CommandError, 'was not promoted'):
            Command(stdout=StringIO()).seed_users(
                12,
                make_password('Seed-password-123!'),
            )

        admin = User.objects.get(email='admin@proace.local')
        self.assertFalse(admin.is_superuser)
        self.assertTrue(admin.check_password('Existing-user-password-123!'))

    def test_seed_rejects_user_count_below_guaranteed_account_set(self):
        with self.assertRaisesRegex(CommandError, 'At least 11 users'):
            call_command('populate_fake_data', scale='small', users=10)

    def test_seed_does_not_replace_zero_volume_override_with_preset(self):
        with self.assertRaisesRegex(CommandError, 'overrides must be positive'):
            call_command('populate_fake_data', scale='small', products=0)

