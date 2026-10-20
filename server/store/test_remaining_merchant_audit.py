"""Merchant financial/input regressions; providers are mocked throughout."""

from datetime import timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from cart.models import Cart, CartItem
from core.models import User
from payment.models import Order, OrderFulfillment
from product.models import Product
from store.models import MerchantWallet, Store, StoreEarningsLedger, StorePayout
from store.services import (
    calculate_merchant_financials,
    calculate_store_financials,
    merchant_earnings_release_at,
    process_payout_status_change,
    process_refund_deduction,
    record_order_earnings_for_merchant,
    request_merchant_payout,
    settle_pending_merchant_earnings,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def mock_providers() -> Any:
    with (
        patch('stripe.Account.retrieve') as account,
        patch('stripe.Transfer.create') as transfer,
        patch('notification.delivery._dispatch_delivery'),
    ):
        account.return_value = {'payouts_enabled': True, 'details_submitted': True}
        transfer.return_value = MagicMock(id='tr_fixture')
        yield account, transfer


@pytest.fixture
def merchant() -> tuple[APIClient, Store]:
    owner = User.objects.create_user(email='remaining-merchant@example.test', password='fixture')
    store = Store.objects.create(
        user=owner, name='Remaining audit', status='active', verified_at=timezone.now(),
    )
    client = APIClient()
    client.force_authenticate(owner)
    return client, store


def sale(
    store: Store,
    *,
    digital: bool = False,
    delivered_days: int | None = 10,
    age_days: int = 20,
) -> tuple[Order, StoreEarningsLedger]:
    product = Product.objects.create(
        store=store, title='Fixture item', description='Fixture', price=100,
        discount=0, available=5, is_digital=digital,
    )
    order = Order.objects.create(
        user=store.user, ordered=True, status='confirmed', total=100,
        subtotal=100, paid_total=100,
        items_snapshot=[{
            'product': product.pk, 'store': store.pk, 'quantity': 1,
            'unit_price': '100.00', 'line_total': '100.00',
            'net_total': '100.00', 'is_digital': digital,
        }],
    )
    Order.objects.filter(pk=order.pk).update(created=timezone.now() - timedelta(days=age_days))
    order.refresh_from_db()
    if not digital:
        OrderFulfillment.objects.create(
            order=order, store=store,
            status='delivered' if delivered_days is not None else 'confirmed',
            delivered_at=(timezone.now() - timedelta(days=delivered_days))
            if delivered_days is not None else None,
        )
    return order, record_order_earnings_for_merchant(order)[0]


def payout(store: Store, amount: str, *, method: str = 'bank_transfer') -> StorePayout:
    return request_merchant_payout(
        store.user, Decimal(amount), method, {}, store=store,
    )


@pytest.mark.parametrize('method', ['bank_transfer', 'stripe_connect'])
def test_refund_invalidates_pending_payout_before_provider(
    merchant: tuple[APIClient, Store], mock_providers: Any, settings: Any, method: str,
) -> None:
    _, store = merchant
    order, entry = sale(store)
    withdrawal = payout(store, '96.00', method=method)
    settings.STRIPE_SECRET = 'fixture-only'
    entry.wallet.stripe_account_id = 'acct_fixture'
    entry.wallet.save(update_fields=['stripe_account_id'])
    process_refund_deduction(order)
    with pytest.raises(ValidationError, match='reservations exceed cleared funds'):
        process_payout_status_change(withdrawal, 'approve', store.user)
    withdrawal.refresh_from_db()
    assert withdrawal.status == 'pending'
    mock_providers[0].assert_not_called()
    mock_providers[1].assert_not_called()


def test_multiple_reservations_require_coverage_but_rejection_restores_eligibility(
    merchant: tuple[APIClient, Store],
) -> None:
    _, store = merchant
    order, _ = sale(store)
    sale(store)
    first, second = payout(store, '70'), payout(store, '70')
    process_refund_deduction(order)
    with pytest.raises(ValidationError):
        process_payout_status_change(first, 'approve', store.user)
    process_payout_status_change(second, 'reject', store.user)
    process_payout_status_change(first, 'approve', store.user)
    assert calculate_merchant_financials(store.user)['available_balance'] == '26.00'


def test_exactly_reserved_stripe_payout_is_legitimate_and_transferred_once(
    merchant: tuple[APIClient, Store], mock_providers: Any, settings: Any,
) -> None:
    _, store = merchant
    sale(store)
    withdrawal = payout(store, '96', method='stripe_connect')
    wallet = MerchantWallet.objects.get(user=store.user)
    wallet.stripe_account_id = 'acct_fixture'
    wallet.save(update_fields=['stripe_account_id'])
    settings.STRIPE_SECRET = 'fixture-only'
    process_payout_status_change(withdrawal, 'approve', store.user)
    with pytest.raises(ValidationError):
        process_payout_status_change(withdrawal, 'approve', store.user)
    mock_providers[1].assert_called_once()
    assert calculate_merchant_financials(store.user)['available_balance'] == '0.00'


@pytest.mark.parametrize('history', ['sale', 'pending', 'completed', 'rejected'])
def test_store_with_financial_history_cannot_be_deleted(
    merchant: tuple[APIClient, Store], history: str,
) -> None:
    client, store = merchant
    if history == 'sale':
        sale(store)
    else:
        wallet = MerchantWallet.objects.create(user=store.user)
        StorePayout.objects.create(store=store, wallet=wallet, amount=10, status=history)
    before = calculate_merchant_financials(store.user)
    result = client.delete(f'/api/v1/stores/{store.pk}/delete/')
    assert result.status_code == 400, result.data
    assert 'history' in result.data['error']['message']
    assert Store.objects.filter(pk=store.pk).exists()
    assert calculate_merchant_financials(store.user)['available_balance'] == before['available_balance']


def test_unused_store_can_still_be_deleted(merchant: tuple[APIClient, Store]) -> None:
    client, store = merchant
    assert client.delete(f'/api/v1/stores/{store.pk}/delete/').status_code == 204


@pytest.mark.parametrize('collection', ['orders', 'refunds'])
@pytest.mark.parametrize('days', ['999999999999999999999', '-1', 'not-a-number'])
def test_relative_date_windows_reject_overflow_and_invalid_values(
    merchant: tuple[APIClient, Store], collection: str, days: str,
) -> None:
    client, store = merchant
    response = client.get(f'/api/v1/stores/{store.pk}/{collection}/', {'days': days})
    assert response.status_code == 400


def test_historical_deleted_store_keeps_earnings_and_single_payout_debit(
    merchant: tuple[APIClient, Store],
) -> None:
    _, store = merchant
    _, entry = sale(store, digital=True)
    withdrawal = payout(store, '30')
    process_payout_status_change(withdrawal, 'approve', store.user)
    owner = store.user
    store.delete()  # Simulate records orphaned by the former deletion behavior.
    entry.refresh_from_db()
    assert entry.store_id is None
    financials = calculate_merchant_financials(owner)
    assert financials['total_net_sales'] == '96.00'
    assert financials['total_withdrawn'] == '30.00'
    assert financials['available_balance'] == '66.00'


@pytest.mark.parametrize('field', ['date_from', 'date_to'])
@pytest.mark.parametrize('value', ['2026-02-30', '2026-13-01T12:00:00Z', 'not-a-date'])
@pytest.mark.parametrize('endpoint', ['orders', 'refunds'])
def test_invalid_dates_return_field_errors(
    merchant: tuple[APIClient, Store], field: str, value: str, endpoint: str,
) -> None:
    client, store = merchant
    result = client.get(f'/api/v1/stores/{store.pk}/{endpoint}/', {field: value})
    assert result.status_code == 400, result.data
    assert field in result.data['error']['details']


@pytest.mark.parametrize('value', [123, True, ['https://example.test'], {'url': 'file'}, None])
def test_variant_asset_addresses_require_strings(
    merchant: tuple[APIClient, Store], value: Any,
) -> None:
    client, store = merchant
    _, entry = sale(store)
    product_id = entry.order.items_snapshot[0]['product']
    result = client.patch(
        f'/api/v1/stores/{store.pk}/products/{product_id}/',
        {'variants': [{'name': 'Option', 'digital_file_url': value}]}, format='json',
    )
    assert result.status_code == 400, result.data
    assert 'variants' in result.data['error']['details']


@pytest.mark.parametrize('value,status', [(0, 200), (2147483647, 200), (2147483648, 400), (-1, 400)])
def test_inventory_database_bounds(
    merchant: tuple[APIClient, Store], value: int, status: int,
) -> None:
    client, store = merchant
    _, entry = sale(store)
    product_id = entry.order.items_snapshot[0]['product']
    result = client.patch(
        f'/api/v1/stores/{store.pk}/products/{product_id}/inventory/',
        {'available': value}, format='json',
    )
    assert result.status_code == status, result.data
    assert Product.objects.get(pk=product_id).available == (value if status == 200 else 5)


@pytest.mark.parametrize('delivered_days,expected', [(None, '0.00'), (2, '0.00'), (8, '96.00')])
def test_physical_escrow_creation_settlement_and_recalculation(
    merchant: tuple[APIClient, Store], delivered_days: int | None, expected: str,
) -> None:
    _, store = merchant
    _, entry = sale(store, delivered_days=delivered_days)
    assert calculate_store_financials(store)['available_balance'] == expected
    assert calculate_merchant_financials(store.user)['available_balance'] == expected
    # Old workers may already have marked this sale cleared using sale+7.
    StoreEarningsLedger.objects.filter(pk=entry.pk).update(
        status='available', available_at=timezone.now() - timedelta(days=10),
    )
    settle_pending_merchant_earnings()
    entry.refresh_from_db()
    assert entry.status == ('available' if expected == '96.00' else 'pending')
    assert calculate_merchant_financials(store.user)['available_balance'] == expected


def test_digital_sale_hold_and_original_sale_minimum_remain(
    merchant: tuple[APIClient, Store],
) -> None:
    _, store = merchant
    order, _ = sale(store, digital=True, age_days=2)
    assert merchant_earnings_release_at(order, store.pk) == order.created + timedelta(days=7)
    assert calculate_store_financials(store)['available_balance'] == '0.00'
    physical, _ = sale(store, age_days=2, delivered_days=10)
    assert merchant_earnings_release_at(physical, store.pk) == physical.created + timedelta(days=7)


def test_multi_store_escrow_uses_each_store_delivery(
    merchant: tuple[APIClient, Store],
) -> None:
    _, store = merchant
    order, _ = sale(store)
    other = Store.objects.create(user=store.user, name='Other fixture')
    order.items_snapshot.append({**order.items_snapshot[0], 'store': other.pk})
    order.total = order.paid_total = 200
    order.save(update_fields=['items_snapshot', 'total', 'paid_total'])
    OrderFulfillment.objects.create(order=order, store=other, status='shipped')
    record_order_earnings_for_merchant(order)
    assert calculate_store_financials(store)['available_balance'] == '96.00'
    assert calculate_store_financials(other)['available_balance'] == '0.00'


def test_legacy_cart_and_order_delivery_fallback(merchant: tuple[APIClient, Store]) -> None:
    _, store = merchant
    order, entry = sale(store, delivered_days=None)
    cart = Cart.objects.create(user=store.user, ordered=True)
    CartItem.objects.create(cart=cart, product_id=order.items_snapshot[0]['product'], quantity=1)
    order.items_snapshot = []
    order.cart = cart
    order.delivered_at = timezone.now() - timedelta(days=8)
    order.save(update_fields=['items_snapshot', 'cart', 'delivered_at'])
    assert calculate_store_financials(store)['available_balance'] == '96.00'
    settle_pending_merchant_earnings()
    entry.refresh_from_db()
    assert entry.status == 'available'


def test_orphaned_physical_sale_stays_held_without_delivery_proof(
    merchant: tuple[APIClient, Store],
) -> None:
    _, store = merchant
    order, _ = sale(store, delivered_days=None)
    order.fulfillments.all().delete()  # Legacy hard deletions predated protected fulfillment rows.
    owner = store.user
    store.delete()
    assert calculate_merchant_financials(owner)['pending_balance'] == '96.00'
    assert calculate_merchant_financials(owner)['available_balance'] == '0.00'


def test_physical_snapshot_without_store_is_not_treated_as_digital(
    merchant: tuple[APIClient, Store],
) -> None:
    _, store = merchant
    order, _ = sale(store, delivered_days=None)
    order.items_snapshot[0].pop('store')
    order.save(update_fields=['items_snapshot'])
    assert merchant_earnings_release_at(order, store.pk) is None
    assert calculate_store_financials(store)['available_balance'] == '0.00'
    order.fulfillments.update(delivered_at=timezone.now() - timedelta(days=8))
    assert calculate_store_financials(store)['available_balance'] == '96.00'


def test_settlement_after_dashboard_release_does_not_double_credit(
    merchant: tuple[APIClient, Store],
) -> None:
    _, store = merchant
    order, entry = sale(store, delivered_days=None)
    order.fulfillments.update(delivered_at=timezone.now() - timedelta(days=8))
    assert calculate_merchant_financials(store.user)['available_balance'] == '96.00'
    assert settle_pending_merchant_earnings(user=store.user) == 1
    assert settle_pending_merchant_earnings(user=store.user) == 0
    entry.wallet.refresh_from_db()
    assert entry.wallet.available_balance == Decimal('96.00')


def test_orphaned_same_order_refund_is_deducted_once(
    merchant: tuple[APIClient, Store],
) -> None:
    _, store = merchant
    order, entry = sale(store, digital=True, age_days=2)
    other = Store.objects.create(user=store.user, name='Deleted sibling fixture')
    order.items_snapshot.append({**order.items_snapshot[0], 'store': other.pk})
    order.total = order.paid_total = 200
    order.save(update_fields=['items_snapshot', 'total', 'paid_total'])
    record_order_earnings_for_merchant(order)
    process_refund_deduction(order, Decimal('50'), store=store)
    StoreEarningsLedger.objects.filter(order=order).update(store=None)
    financials = calculate_merchant_financials(store.user)
    assert financials['pending_balance'] == '144.00'
    assert financials['available_balance'] == '0.00'
