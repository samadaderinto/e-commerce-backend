from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone
from nanoid import generate

from cart.models import CartItem
from product.models import Product
from store.models import MerchantWallet, Schedule, Store, StoreEarningsLedger, StorePayout


@transaction.atomic
def publish_due_products() -> int:
    from store.views import invalidate_catalog

    count = 0
    schedules = Schedule.objects.select_for_update().select_related('store').filter(
        make_visible_at__lte=timezone.now()
    )
    for schedule in schedules:
        store = schedule.store
        if store.status != Store.STATUS_ACTIVE or store.verified_at is None:
            continue
        product = Product.objects.select_for_update().filter(pk=schedule.product_id, store_id=schedule.store_id).first()
        if product is not None:
            product.visibility = True
            product.save(update_fields=['visibility', 'updated'])
            transaction.on_commit(lambda product=product: invalidate_catalog(product))
            count += 1
        schedule.delete()
    return count


def get_or_create_merchant_wallet(user: Any) -> MerchantWallet:
    """Retrieves or creates a singleton MerchantWallet for the given user."""
    wallet, _ = MerchantWallet.objects.get_or_create(user=user)
    return wallet


@transaction.atomic
def record_order_earnings_for_merchant(order: Any) -> list[StoreEarningsLedger]:
    """
    Given a completed/confirmed order, calculates net earnings for each participating store,
    creates StoreEarningsLedger entries in pending escrow status, and increments the merchant's
    pending balance.
    """
    from payment.models import Order

    if not order or not order.ordered:
        return []

    refund_window = getattr(settings, 'REFUND_WINDOW_DAYS', 7)
    available_at = (order.created or timezone.now()) + timedelta(days=refund_window)
    default_fee_rate = getattr(settings, 'PLATFORM_FEE_PERCENT', Decimal('4.00')) / Decimal('100.0')

    # Gather items by store from cart or snapshot
    created_entries: list[StoreEarningsLedger] = []
    
    items_by_store: dict[int, Decimal] = {}
    if order.cart_id:
        items = CartItem.objects.filter(cart_id=order.cart_id).select_related('product', 'product__store')
        for item in items:
            store_id = item.product.store_id if item.product and item.product.store else None
            if not store_id:
                continue
            line_val = (
                Decimal(item.quantity)
                * Decimal(str(item.product.price))
                * (Decimal('100.0') - Decimal(str(item.product.discount)))
                / Decimal('100.0')
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            items_by_store[store_id] = items_by_store.get(store_id, Decimal('0.00')) + line_val
    elif order.items_snapshot:
        for snap in order.items_snapshot:
            store_id = snap.get('store')
            if not store_id:
                continue
            qty = Decimal(str(snap.get('quantity', 1)))
            price = Decimal(str(snap.get('unit_price') or snap.get('price', 0)))
            disc = Decimal(str(snap.get('discount', 0)))
            line_val = (qty * price * (Decimal('100.0') - disc) / Decimal('100.0')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            items_by_store[store_id] = items_by_store.get(store_id, Decimal('0.00')) + line_val

    for store_id, gross_amount in items_by_store.items():
        if gross_amount <= Decimal('0.00'):
            continue

        store = Store.objects.filter(pk=store_id).select_related('user').first()
        if not store or not store.user:
            continue

        # Prevent duplicate entries for the same order and store
        existing = StoreEarningsLedger.objects.filter(
            store=store,
            order=order,
            entry_type=StoreEarningsLedger.TYPE_SALE,
        ).first()
        if existing:
            continue

        is_official = store.is_official or bool(store.user and store.user.is_superuser)
        fee_rate = Decimal('0.00') if is_official else default_fee_rate
        fee_amount = (gross_amount * fee_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        net_amount = (gross_amount - fee_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        wallet, _ = MerchantWallet.objects.select_for_update().get_or_create(user=store.user)
        
        # Check if order is already past refund window (e.g. backdated in tests or delayed processing)
        now = timezone.now()
        is_cleared = available_at <= now
        entry_status = StoreEarningsLedger.STATUS_AVAILABLE if is_cleared else StoreEarningsLedger.STATUS_PENDING
        cleared_at = now if is_cleared else None

        ledger_entry = StoreEarningsLedger.objects.create(
            wallet=wallet,
            store=store,
            order=order,
            entry_type=StoreEarningsLedger.TYPE_SALE,
            gross_amount=gross_amount,
            fee_amount=fee_amount,
            net_amount=net_amount,
            status=entry_status,
            available_at=available_at,
            cleared_at=cleared_at,
            description=f"Order #{order.orderId} sale revenue for store '{store.name}'",
            reference=order.orderId,
        )

        if is_cleared:
            wallet.available_balance += net_amount
        else:
            wallet.pending_balance += net_amount
        wallet.save(update_fields=['available_balance', 'pending_balance', 'updated'])

        created_entries.append(ledger_entry)

    return created_entries


@transaction.atomic
def settle_pending_merchant_earnings() -> int:
    """
    Finds all StoreEarningsLedger entries currently in PENDING status whose holding period
    has elapsed (available_at <= now), moves the net amount from pending_balance to
    available_balance in each merchant's wallet, and updates the entry status to AVAILABLE.
    """
    now = timezone.now()
    pending_entries = StoreEarningsLedger.objects.select_for_update().filter(
        status=StoreEarningsLedger.STATUS_PENDING,
        available_at__lte=now,
    ).select_related('wallet')

    count = 0
    wallet_adjustments: dict[int, Decimal] = {}

    for entry in pending_entries:
        entry.status = StoreEarningsLedger.STATUS_AVAILABLE
        entry.cleared_at = now
        entry.save(update_fields=['status', 'cleared_at', 'updated'])

        wallet_adjustments[entry.wallet_id] = wallet_adjustments.get(entry.wallet_id, Decimal('0.00')) + entry.net_amount
        count += 1

    for wallet_id, amount in wallet_adjustments.items():
        wallet = MerchantWallet.objects.select_for_update().get(pk=wallet_id)
        wallet.pending_balance = max(Decimal('0.00'), wallet.pending_balance - amount)
        wallet.available_balance = wallet.available_balance + amount
        wallet.save(update_fields=['pending_balance', 'available_balance', 'updated'])

    return count


@transaction.atomic
def process_refund_deduction(order: Any, refund_amount: Decimal | None = None, store: Any = None) -> None:
    """
    Reverses or adjusts merchant earnings when a customer order is refunded.
    """
    from payment.models import Order

    entries = StoreEarningsLedger.objects.select_for_update().filter(
        order=order,
        entry_type=StoreEarningsLedger.TYPE_SALE,
    ).exclude(status=StoreEarningsLedger.STATUS_REVERSED).select_related('wallet', 'store')

    if store:
        entries = entries.filter(store=store)

    for entry in entries:
        wallet = entry.wallet
        # If entry was pending, subtract from pending; if available, subtract from available
        if entry.status == StoreEarningsLedger.STATUS_PENDING:
            wallet.pending_balance = max(Decimal('0.00'), wallet.pending_balance - entry.net_amount)
        elif entry.status == StoreEarningsLedger.STATUS_AVAILABLE:
            wallet.available_balance = max(Decimal('0.00'), wallet.available_balance - entry.net_amount)
        wallet.save(update_fields=['pending_balance', 'available_balance', 'updated'])

        entry.status = StoreEarningsLedger.STATUS_REVERSED
        entry.description += " (Refunded / Reversed)"
        entry.save(update_fields=['status', 'description', 'updated'])


@transaction.atomic
def request_merchant_payout(
    user: Any,
    amount: Decimal,
    payout_method: str,
    account_details: dict,
    store: Store | None = None,
    notes: str = "",
) -> StorePayout:
    """
    Submits a payout request from the merchant's unified available balance.
    Atomically debits the requested amount from available_balance and puts it into pending payout state.
    """
    from rest_framework.exceptions import ValidationError

    settle_pending_merchant_earnings()
    calculate_merchant_financials(user)

    wallet, _ = MerchantWallet.objects.select_for_update().get_or_create(user=user)

    if amount > wallet.available_balance:
        raise ValidationError({
            'detail': f'Requested payout amount (${amount}) exceeds available cleared balance (${wallet.available_balance}).'
        })

    reference = f"PO-{generate(size=10).upper()}"
    wallet.available_balance -= amount
    wallet.save(update_fields=['available_balance', 'updated'])

    payout = StorePayout.objects.create(
        store=store,
        wallet=wallet,
        amount=amount,
        payout_method=payout_method,
        account_details=account_details,
        reference=reference,
        status=StorePayout.STATUS_PENDING,
        notes=notes,
    )

    if store:
        StoreEarningsLedger.objects.create(
            wallet=wallet,
            store=store,
            entry_type=StoreEarningsLedger.TYPE_PAYOUT,
            gross_amount=amount,
            fee_amount=Decimal('0.00'),
            net_amount=-amount,
            status=StoreEarningsLedger.STATUS_PENDING,
            description=f"Payout withdrawal request ({reference}) for store '{store.name}'",
            reference=reference,
        )

    return payout


@transaction.atomic
def process_payout_status_change(
    payout: StorePayout,
    action: str,
    processed_by: Any,
    notes: str = "",
) -> StorePayout:
    """
    Staff approval or rejection of a merchant payout request.
    """
    wallet = payout.wallet or (payout.store and get_or_create_merchant_wallet(payout.store.user))

    if action == "approve":
        payout.status = StorePayout.STATUS_COMPLETED
        payout.processed_at = timezone.now()
        payout.processed_by = processed_by
        if notes:
            payout.notes = notes
        payout.save(update_fields=['status', 'processed_at', 'processed_by', 'notes', 'updated'])

        if wallet:
            wallet_obj = MerchantWallet.objects.select_for_update().get(pk=wallet.pk)
            wallet_obj.total_withdrawn += payout.amount
            wallet_obj.save(update_fields=['total_withdrawn', 'updated'])

        StoreEarningsLedger.objects.filter(
            reference=payout.reference,
            entry_type=StoreEarningsLedger.TYPE_PAYOUT,
        ).update(status=StoreEarningsLedger.STATUS_COMPLETED, cleared_at=timezone.now())

    else:
        payout.status = StorePayout.STATUS_REJECTED
        payout.notes = notes or "Payout declined by compliance."
        payout.processed_at = timezone.now()
        payout.processed_by = processed_by
        payout.save(update_fields=['status', 'notes', 'processed_at', 'processed_by', 'updated'])

        if wallet:
            wallet_obj = MerchantWallet.objects.select_for_update().get(pk=wallet.pk)
            wallet_obj.available_balance += payout.amount
            wallet_obj.save(update_fields=['available_balance', 'updated'])

        StoreEarningsLedger.objects.filter(
            reference=payout.reference,
            entry_type=StoreEarningsLedger.TYPE_PAYOUT,
        ).update(status=StoreEarningsLedger.STATUS_REVERSED)

    return payout


def calculate_store_financials(store: Store, days: int = 30) -> dict:
    """
    Calculates sales, escrow, cleared, and payout financials for a specific store.
    """
    from payment.models import Order

    sales_orders = Order.objects.filter(
        ordered=True,
        status__in=['confirmed', 'shipped', 'delivered', 'picked up'],
    )
    items = CartItem.objects.filter(product__store=store, cart__in=sales_orders.values('cart_id'))
    line_value = ExpressionWrapper(
        F('quantity') * F('product__price') * (100 - F('product__discount')) / Decimal('100.0'),
        output_field=DecimalField(max_digits=24, decimal_places=2),
    )
    totals = items.aggregate(value=Sum(line_value), units=Sum('quantity'))

    is_official = store.is_official or bool(store.user and store.user.is_superuser)
    fee_rate = Decimal('0.00') if is_official else (getattr(settings, 'PLATFORM_FEE_PERCENT', Decimal('4.00')) / Decimal('100.0'))
    fee_percent = Decimal('0.00') if is_official else getattr(settings, 'PLATFORM_FEE_PERCENT', Decimal('4.00'))

    refund_window = getattr(settings, 'REFUND_WINDOW_DAYS', 7)
    cutoff = timezone.now() - timedelta(days=refund_window)

    in_review_orders = sales_orders.filter(created__gt=cutoff)
    in_review_items = CartItem.objects.filter(product__store=store, cart__in=in_review_orders.values('cart_id'))
    in_review_totals = in_review_items.aggregate(value=Sum(line_value))
    in_review_gross = in_review_totals['value'] or Decimal('0.00')
    in_review_net = (in_review_gross * (Decimal('1.00') - fee_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    cleared_orders = sales_orders.filter(created__lte=cutoff)
    cleared_items = CartItem.objects.filter(product__store=store, cart__in=cleared_orders.values('cart_id'))
    cleared_totals = cleared_items.aggregate(value=Sum(line_value))
    cleared_gross = cleared_totals['value'] or Decimal('0.00')
    cleared_net = (cleared_gross * (Decimal('1.00') - fee_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    gross_value = totals['value'] or Decimal('0.00')
    platform_fee = (gross_value * fee_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    net_value = (gross_value - platform_fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    payouts_completed = store.payouts.filter(status=StorePayout.STATUS_COMPLETED).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    payouts_pending = store.payouts.filter(status=StorePayout.STATUS_PENDING).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    available_balance = max(Decimal('0.00'), cleared_net - payouts_completed - payouts_pending)

    return {
        'gross_sales': format(gross_value, '.2f'),
        'platform_fee_percent': format(fee_percent, '.2f'),
        'platform_fee_deducted': format(platform_fee, '.2f'),
        'net_sales': format(net_value, '.2f'),
        'in_review': format(in_review_net, '.2f'),
        'cleared_total': format(cleared_net, '.2f'),
        'payouts_completed': format(payouts_completed, '.2f'),
        'payouts_pending': format(payouts_pending, '.2f'),
        'available_balance': format(available_balance, '.2f'),
        'refund_window_days': refund_window,
    }


def calculate_merchant_financials(user: Any) -> dict:
    """
    Consolidates financial metrics across all stores owned by a user/merchant,
    including ledger consistency and store breakdown.
    """
    wallet = get_or_create_merchant_wallet(user)
    stores = Store.objects.filter(user=user).order_by('-created', '-pk')

    stores_breakdown = []
    total_gross = Decimal('0.00')
    total_fee = Decimal('0.00')
    total_net = Decimal('0.00')
    total_in_review = Decimal('0.00')
    total_cleared = Decimal('0.00')
    total_payouts_completed = Decimal('0.00')
    total_payouts_pending = Decimal('0.00')

    for store in stores:
        fin = calculate_store_financials(store)
        stores_breakdown.append({
            'store_id': store.pk,
            'store_name': store.name,
            'store_username': store.username,
            'status': store.status,
            'is_official': store.is_official,
            **fin,
        })
        total_gross += Decimal(fin['gross_sales'])
        total_fee += Decimal(fin['platform_fee_deducted'])
        total_net += Decimal(fin['net_sales'])
        total_in_review += Decimal(fin['in_review'])
        total_cleared += Decimal(fin['cleared_total'])
        total_payouts_completed += Decimal(fin['payouts_completed'])
        total_payouts_pending += Decimal(fin['payouts_pending'])

    # Synchronize wallet balance fields to match verified cleared funds
    computed_available = max(Decimal('0.00'), total_cleared - total_payouts_completed - total_payouts_pending)
    if wallet.available_balance != computed_available or wallet.pending_balance != total_in_review or wallet.total_withdrawn != total_payouts_completed:
        wallet.available_balance = computed_available
        wallet.pending_balance = total_in_review
        wallet.total_withdrawn = total_payouts_completed
        wallet.save(update_fields=['available_balance', 'pending_balance', 'total_withdrawn', 'updated'])

    refund_window = getattr(settings, 'REFUND_WINDOW_DAYS', 7)
    platform_fee_percent = getattr(settings, 'PLATFORM_FEE_PERCENT', Decimal('4.00'))

    return {
        'wallet_id': wallet.pk,
        'stripe_account_id': wallet.stripe_account_id,
        'stripe_details_submitted': wallet.stripe_details_submitted,
        'stripe_payouts_enabled': wallet.stripe_payouts_enabled,
        'available_balance': format(wallet.available_balance, '.2f'),
        'pending_balance': format(wallet.pending_balance, '.2f'),
        'total_withdrawn': format(wallet.total_withdrawn, '.2f'),
        'total_gross_sales': format(total_gross, '.2f'),
        'total_platform_fees': format(total_fee, '.2f'),
        'total_net_sales': format(total_net, '.2f'),
        'refund_window_days': refund_window,
        'platform_fee_percent': format(platform_fee_percent, '.2f'),
        'stores_count': stores.count(),
        'stores': stores_breakdown,
    }
