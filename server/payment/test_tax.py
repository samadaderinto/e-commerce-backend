"""
Tests for the Enterprise Hybrid Tax Engine.
Verifies LocalTaxProvider, StripeTaxProvider fallback, jurisdiction resolution,
product digital taxability, and shipping fee taxability.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Address, User
from payment.models import Order, TaxJurisdiction
from payment.tax import (
    DEFAULT_JURISDICTIONS_DICT,
    LocalTaxProvider,
    StripeTaxProvider,
    TaxBreakdown,
    calculate_tax,
    normalize_us_state,
)
from product.models import Product
from store.models import Store, StoreAddress


class TaxEngineUnitTests(TestCase):
    def test_normalize_us_state(self):
        self.assertEqual(normalize_us_state("california"), "CA")
        self.assertEqual(normalize_us_state("CA"), "CA")
        self.assertEqual(normalize_us_state("New York"), "NY")
        self.assertEqual(normalize_us_state("ny"), "NY")
        self.assertEqual(normalize_us_state("Texas"), "TX")
        self.assertEqual(normalize_us_state("Washington DC"), "DC")
        self.assertEqual(normalize_us_state("Unknown"), "UNKNOWN")

    def test_local_tax_provider_no_address(self):
        provider = LocalTaxProvider()
        items = [{'unit_price': '50.00', 'quantity': 1, 'is_digital': False}]
        breakdown = provider.calculate_tax(items, Decimal('50.00'), Decimal('10.00'), None)
        self.assertEqual(breakdown.country, "US")
        self.assertEqual(breakdown.taxable_merchandise, Decimal('50.00'))
        self.assertEqual(breakdown.taxable_shipping, Decimal('0.00'))

    def test_local_tax_provider_international_zero_rated(self):
        provider = LocalTaxProvider()
        items = [{'unit_price': '50.00', 'quantity': 1, 'is_digital': False}]
        addr = {'country': 'CA', 'state': 'ON', 'zip': 'K1A0B1', 'address': '1 Main St', 'city': 'Ottawa'}
        breakdown = provider.calculate_tax(items, Decimal('50.00'), Decimal('10.00'), addr)
        self.assertEqual(breakdown.amount, Decimal('0.00'))
        self.assertEqual(breakdown.rate, Decimal('0.00'))
        self.assertTrue(breakdown.is_exempt)
        self.assertIn("International", breakdown.jurisdiction)

    def test_local_tax_provider_non_tax_states(self):
        provider = LocalTaxProvider()
        items = [{'unit_price': '100.00', 'quantity': 1, 'is_digital': False}]
        for state in ['OR', 'DE', 'MT', 'NH']:
            addr = {'country': 'US', 'state': state, 'zip': '97201', 'address': '123 Pine St', 'city': 'Portland'}
            breakdown = provider.calculate_tax(items, Decimal('100.00'), Decimal('15.00'), addr)
            self.assertEqual(breakdown.amount, Decimal('0.00'))
            self.assertEqual(breakdown.rate, Decimal('0.00'))
            self.assertTrue(breakdown.is_exempt)

    def test_local_tax_provider_with_database_record(self):
        TaxJurisdiction.objects.create(
            country="US",
            state="TX",
            postal_code="",
            name="Texas Combined Rate",
            rate=Decimal("0.0825"),
            tax_shipping=True,
            tax_digital=True,
            is_active=True,
        )
        provider = LocalTaxProvider()
        items = [{'unit_price': '100.00', 'quantity': 1, 'is_digital': False}]
        addr = {'country': 'US', 'state': 'Texas', 'zip': '75001', 'address': '123 Elm St', 'city': 'Dallas'}
        breakdown = provider.calculate_tax(items, Decimal('100.00'), Decimal('10.00'), addr)
        # 100 * 0.0825 = 8.25 merchandise tax; 10 * 0.0825 = 0.825 -> 0.83 shipping tax
        # Total = 8.25 + 0.83 = 9.08
        self.assertEqual(breakdown.taxable_merchandise, Decimal('100.00'))
        self.assertEqual(breakdown.taxable_shipping, Decimal('10.00'))
        self.assertEqual(breakdown.amount, Decimal('9.08'))
        self.assertEqual(breakdown.rate, Decimal('0.0825'))
        self.assertEqual(breakdown.jurisdiction, "Texas Combined Rate")

    def test_local_tax_provider_zip_override_priority(self):
        # State base rate
        TaxJurisdiction.objects.create(
            country="US",
            state="NY",
            postal_code="",
            name="New York State Base",
            rate=Decimal("0.0800"),
            tax_shipping=False,
            tax_digital=True,
            is_active=True,
        )
        # Specific NYC ZIP with higher municipal rate
        TaxJurisdiction.objects.create(
            country="US",
            state="NY",
            postal_code="10001",
            name="New York City (Manhattan Special)",
            rate=Decimal("0.08875"),
            tax_shipping=False,
            tax_digital=True,
            is_active=True,
        )
        provider = LocalTaxProvider()
        items = [{'unit_price': '100.00', 'quantity': 1, 'is_digital': False}]

        # Address with ZIP 10001 gets NYC rate
        addr_nyc = {'country': 'US', 'state': 'NY', 'zip': '10001', 'address': '1 5th Ave', 'city': 'New York'}
        breakdown_nyc = provider.calculate_tax(items, Decimal('100.00'), Decimal('5.00'), addr_nyc)
        self.assertEqual(breakdown_nyc.rate, Decimal('0.08875'))
        self.assertEqual(breakdown_nyc.jurisdiction, "New York City (Manhattan Special)")

        # Address with other NY ZIP gets state base rate
        addr_albany = {'country': 'US', 'state': 'NY', 'zip': '12201', 'address': '1 State St', 'city': 'Albany'}
        breakdown_albany = provider.calculate_tax(items, Decimal('100.00'), Decimal('5.00'), addr_albany)
        self.assertEqual(breakdown_albany.rate, Decimal('0.0800'))
        self.assertEqual(breakdown_albany.jurisdiction, "New York State Base")

    def test_local_tax_provider_digital_goods_exemption(self):
        # California: digital goods exempt
        TaxJurisdiction.objects.create(
            country="US",
            state="CA",
            postal_code="",
            name="California State",
            rate=Decimal("0.0885"),
            tax_shipping=False,
            tax_digital=False,
            is_active=True,
        )
        # Washington: digital goods taxable
        TaxJurisdiction.objects.create(
            country="US",
            state="WA",
            postal_code="",
            name="Washington State",
            rate=Decimal("0.0938"),
            tax_shipping=True,
            tax_digital=True,
            is_active=True,
        )
        provider = LocalTaxProvider()
        items = [{'unit_price': '50.00', 'quantity': 1, 'is_digital': True}]

        # In CA: digital goods are not taxable -> 0.00
        addr_ca = {'country': 'US', 'state': 'CA', 'zip': '90210', 'address': '1 Sunset Blvd', 'city': 'Beverly Hills'}
        breakdown_ca = provider.calculate_tax(items, Decimal('50.00'), Decimal('0.00'), addr_ca)
        self.assertEqual(breakdown_ca.amount, Decimal('0.00'))
        self.assertEqual(breakdown_ca.taxable_merchandise, Decimal('0.00'))

        # In WA: digital goods are taxable -> 50.00 * 0.0938 = 4.69
        addr_wa = {'country': 'US', 'state': 'WA', 'zip': '98101', 'address': '1 Pike St', 'city': 'Seattle'}
        breakdown_wa = provider.calculate_tax(items, Decimal('50.00'), Decimal('0.00'), addr_wa)
        self.assertEqual(breakdown_wa.amount, Decimal('4.69'))
        self.assertEqual(breakdown_wa.taxable_merchandise, Decimal('50.00'))


class StripeTaxProviderTests(TestCase):
    @override_settings(STRIPE_TAX_ENABLED=False)
    def test_stripe_tax_disabled_falls_back_to_local(self):
        provider = StripeTaxProvider()
        items = [{'unit_price': '100.00', 'quantity': 1, 'is_digital': False}]
        addr = {'country': 'US', 'state': 'CA', 'zip': '90210', 'address': '1 Sunset Blvd', 'city': 'Beverly Hills'}
        breakdown = provider.calculate_tax(items, Decimal('100.00'), Decimal('5.00'), addr)
        self.assertEqual(breakdown.provider, "local")

    @override_settings(STRIPE_TAX_ENABLED=True, STRIPE_SECRET="sk_test_mock")
    @patch('stripe.tax.Calculation.create')
    def test_stripe_tax_success(self, mock_create):
        mock_calc = MagicMock()
        mock_calc.id = "taxcalc_123"
        mock_calc.tax_amount_exclusive = 825  # $8.25
        mock_jurisdiction = MagicMock()
        mock_jurisdiction.display_name = "California State and Local"
        mock_breakdown = MagicMock()
        mock_breakdown.jurisdiction = mock_jurisdiction
        mock_calc.tax_breakdown = [mock_breakdown]
        mock_create.return_value = mock_calc

        provider = StripeTaxProvider()
        items = [{'unit_price': '100.00', 'quantity': 1, 'is_digital': False}]
        addr = {'country': 'US', 'state': 'CA', 'zip': '90210', 'address': '1 Sunset Blvd', 'city': 'Beverly Hills'}
        breakdown = provider.calculate_tax(items, Decimal('100.00'), Decimal('0.00'), addr)

        self.assertEqual(breakdown.provider, "stripe")
        self.assertEqual(breakdown.amount, Decimal('8.25'))
        self.assertEqual(breakdown.jurisdiction, "California State and Local")
        self.assertEqual(breakdown.details.get('stripe_calculation_id'), "taxcalc_123")

    @override_settings(STRIPE_TAX_ENABLED=True, STRIPE_SECRET="sk_test_mock")
    @patch('stripe.tax.Calculation.create', side_effect=Exception("Stripe API down"))
    def test_stripe_tax_api_failure_gracefully_degrades_to_local(self, mock_create):
        TaxJurisdiction.objects.create(
            country="US",
            state="CA",
            postal_code="",
            name="California Base",
            rate=Decimal("0.0885"),
            tax_shipping=False,
            tax_digital=True,
            is_active=True,
        )
        provider = StripeTaxProvider()
        items = [{'unit_price': '100.00', 'quantity': 1, 'is_digital': False}]
        addr = {'country': 'US', 'state': 'CA', 'zip': '90210', 'address': '1 Sunset Blvd', 'city': 'Beverly Hills'}
        breakdown = provider.calculate_tax(items, Decimal('100.00'), Decimal('0.00'), addr)

        # Degraded cleanly to local provider without throwing exception
        self.assertEqual(breakdown.provider, "local")
        self.assertGreater(breakdown.amount, Decimal('0.00'))


@override_settings(ROOT_URLCONF='storefront.urls')
class StorefrontTaxCheckoutIntegrationTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(email='taxshopper@test.com', password='Password123!')
        self.seller = User.objects.create_user(email='taxmerchant@test.com', password='Password123!')
        self.store = Store.objects.create(user=self.seller, name='Tax Store', status='active', verified_at=timezone.now())
        StoreAddress.objects.create(store=self.store, is_default=True, address='1 Main St', city='Tampa', state='FL', country='US', zip='33602')
        self.product = Product.objects.create(store=self.store, title='Taxable Jacket', price=Decimal('100.00'), discount=0, available=10, weight=Decimal('2.00'))
        self.address = Address.objects.create(user=self.buyer, address='123 Austin Blvd', zip='78701', country='US', state='TX', city='Austin')
        self.client = APIClient()

        # Seed Texas jurisdiction with shipping tax
        TaxJurisdiction.objects.create(
            country="US",
            state="TX",
            postal_code="",
            name="Texas State + Local",
            rate=Decimal("0.0825"),
            tax_shipping=True,
            tax_digital=True,
            is_active=True,
        )

    def test_shipping_rates_returns_itemized_tax_and_jurisdiction(self):
        self.client.force_authenticate(self.buyer)
        self.client.post('/api/v1/cart/', {'product': self.product.pk, 'quantity': 1}, format='json')
        response = self.client.get(f'/api/v1/checkout/shipping-rates/?address={self.address.pk}&carrier=USPS')
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data), 0)
        rate = response.data[0]

        # Verify tax fields are populated
        self.assertIn('tax', rate)
        self.assertIn('tax_rate', rate)
        self.assertIn('tax_jurisdiction', rate)
        self.assertEqual(Decimal(rate['tax_rate']), Decimal('0.0825'))
        self.assertEqual(rate['tax_jurisdiction'], 'Texas State + Local')

    def test_checkout_completes_with_accurate_tax_and_persists_tax_snapshot(self):
        self.client.force_authenticate(self.buyer)
        self.client.post('/api/v1/cart/', {'product': self.product.pk, 'quantity': 1}, format='json')
        rates_resp = self.client.get(f'/api/v1/checkout/shipping-rates/?address={self.address.pk}&carrier=USPS')
        rate = rates_resp.data[0]

        checkout_key = str(uuid4())
        checkout_resp = self.client.post('/api/v1/checkout/', {
            'address': self.address.pk,
            'checkout_key': checkout_key,
            'shipping_service': rate['service_id'],
            'shipping_quote': rate['quote_token'],
            'payment_type': 'cash_on_delivery',
        }, format='json')

        self.assertEqual(checkout_resp.status_code, 201)
        order_data = checkout_resp.data
        self.assertIn('tax', order_data)
        self.assertIn('tax_snapshot', order_data)

        # Verify tax calculation in created order
        order = Order.objects.get(checkout_key=checkout_key)
        self.assertGreater(order.tax, Decimal('0.00'))
        self.assertEqual(order.tax_snapshot.get('jurisdiction'), 'Texas State + Local')
        self.assertEqual(order.tax_snapshot.get('state'), 'TX')
        self.assertEqual(order.tax_snapshot.get('provider'), 'local')
        # Total = subtotal (100) + shipping + tax
        self.assertEqual(order.total, order.subtotal + Decimal(rate['amount']) + order.tax)


@override_settings(ROOT_URLCONF='storefront.urls')
class TaxJurisdictionAdminApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='taxadmin@proace.local', password='AdminPassword123!')
        self.staff = User.objects.create_staffuser(email='taxstaff@proace.local', password='StaffPassword123!')
        self.buyer = User.objects.create_user(email='regularbuyer@proace.local', password='BuyerPassword123!')
        self.client = APIClient()

    def test_anonymous_and_buyer_access_is_forbidden(self):
        # Anonymous
        self.assertEqual(self.client.get('/api/v1/admin/taxes/').status_code, 401)
        # Regular customer
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.get('/api/v1/admin/taxes/').status_code, 403)

    def test_admin_crud_operations(self):
        self.client.force_authenticate(self.admin)

        # 1. Create a new jurisdiction
        create_resp = self.client.post('/api/v1/admin/taxes/', {
            'country': 'US',
            'state': 'California',
            'postal_code': '90210',
            'name': 'Beverly Hills Special District',
            'rate': '0.09500',
            'tax_shipping': True,
            'tax_digital': False,
            'is_active': True,
        }, format='json')
        self.assertEqual(create_resp.status_code, 201)
        jur_id = create_resp.data['id']
        self.assertEqual(create_resp.data['state'], 'CA') # Normalized to CA
        self.assertEqual(create_resp.data['postal_code'], '90210')
        self.assertEqual(Decimal(create_resp.data['rate']), Decimal('0.09500'))

        # 2. List jurisdictions with search and summary
        list_resp = self.client.get('/api/v1/admin/taxes/?search=Beverly')
        self.assertEqual(list_resp.status_code, 200)
        self.assertIn('summary', list_resp.data)
        self.assertIn('provider', list_resp.data)
        self.assertEqual(len(list_resp.data['results']), 1)
        self.assertEqual(list_resp.data['results'][0]['id'], jur_id)

        # 3. Patch rate and flags
        patch_resp = self.client.patch(f'/api/v1/admin/taxes/{jur_id}/', {
            'rate': '0.09750',
            'tax_digital': True,
        }, format='json')
        self.assertEqual(patch_resp.status_code, 200)
        self.assertEqual(Decimal(patch_resp.data['rate']), Decimal('0.09750'))
        self.assertTrue(patch_resp.data['tax_digital'])

        # 4. Delete jurisdiction
        del_resp = self.client.delete(f'/api/v1/admin/taxes/{jur_id}/')
        self.assertEqual(del_resp.status_code, 204)
        self.assertEqual(TaxJurisdiction.objects.filter(pk=jur_id).count(), 0)

    def test_seed_defaults_endpoint(self):
        self.client.force_authenticate(self.staff)
        TaxJurisdiction.objects.all().delete()
        self.assertEqual(TaxJurisdiction.objects.count(), 0)

        seed_resp = self.client.post('/api/v1/admin/taxes/seed-defaults/')
        self.assertEqual(seed_resp.status_code, 200)
        self.assertIn('Baseline tax jurisdictions initialized', seed_resp.data['detail'])
        self.assertGreater(TaxJurisdiction.objects.count(), 40)
