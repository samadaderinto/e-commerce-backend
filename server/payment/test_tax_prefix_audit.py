from decimal import Decimal

from django.test import TestCase

from payment.models import TaxJurisdiction
from payment.tax import LocalTaxProvider, TaxBreakdown


class TaxPrefixAuditTests(TestCase):
    def setUp(self) -> None:
        for postal_code, rate, active, state in (
            ('', '0.05000', True, 'CA'),
            ('9', '0.06000', True, 'CA'),
            ('902', '0.07000', True, 'CA'),
            ('9021', '0.08000', True, 'CA'),
            ('90210', '0.09000', True, 'CA'),
            ('90211', '0.99000', False, 'CA'),
            ('90212', '0.99000', True, 'NY'),
        ):
            TaxJurisdiction.objects.create(
                country='US', state=state, postal_code=postal_code,
                name=f'{state}-{postal_code}', rate=Decimal(rate), is_active=active,
            )

    def calculate(self, postal_code: str) -> TaxBreakdown:
        return LocalTaxProvider().calculate_tax(
            [{'unit_price': '100.00', 'quantity': 1, 'is_digital': False}],
            Decimal('100'), Decimal('0'),
            {'country': 'US', 'state': 'California', 'zip': postal_code},
        )

    def test_exact_zip_and_zip_plus_four_take_precedence(self) -> None:
        for postal_code in ('90210', '90210-1234'):
            with self.subTest(postal_code=postal_code):
                self.assertEqual(self.calculate(postal_code).rate, Decimal('0.09000'))

    def test_longest_active_matching_prefix_wins(self) -> None:
        for postal_code, expected in (
            ('90211', '0.08000'), ('90212', '0.08000'),
            ('90299', '0.07000'), ('95555', '0.06000'), ('80000', '0.05000'),
        ):
            with self.subTest(postal_code=postal_code):
                self.assertEqual(self.calculate(postal_code).rate, Decimal(expected))

    def test_zero_rate_prefix_keeps_its_taxability_flags(self) -> None:
        TaxJurisdiction.objects.filter(postal_code='902').update(
            rate=Decimal('0'), tax_shipping=True, tax_digital=False,
        )
        result = self.calculate('90299')
        self.assertEqual(result.rate, Decimal('0'))
        self.assertEqual(result.amount, Decimal('0'))
        self.assertEqual(result.jurisdiction, 'CA-902')
