from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
import logging

from django.conf import settings
from django.db import models, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Q, QuerySet, Sum
from django.utils import timezone
from nanoid import generate

from cart.models import CartItem
from product.models import Product
from store.models import MerchantWallet, Schedule, Store, StoreAddress, StoreEarningsLedger, StorePayout

logger = logging.getLogger(__name__)


def has_store_address(store: Store) -> bool:
    """Require a complete default business address for every seller."""
    address = StoreAddress.objects.filter(store=store, is_default=True).first()
    return bool(address and all(str(getattr(address, field) or '').strip()
                                for field in ('address', 'city', 'state', 'country', 'zip')))


@transaction.atomic
def publish_due_products() -> int:
    from store.views import invalidate_catalog

    count = 0
    schedules = Schedule.objects.select_for_update().select_related('store').filter(
        make_visible_at__lte=timezone.now()
    )
    for schedule in schedules:
        store = schedule.store
        if store.status != Store.STATUS_ACTIVE or store.verified_at is None or not has_store_address(store):
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


def merchant_earnings_release_at(
    order: Any,
    store_id: int | None,
    original_hold: datetime | None = None,
) -> datetime | None:
    """Physical proceeds wait for recorded delivery; digital proceeds use sale time.

    A missing store link cannot establish which shipment earned an orphaned row,
    so all physical shipments on that order must pass their return windows.
    """
    if order is None:
        return original_hold
    window = timedelta(days=getattr(settings, 'REFUND_WINDOW_DAYS', 7))
    sale_hold = (order.created or timezone.now()) + window
    release_at = max(sale_hold, original_hold) if original_hold else sale_hold
    if order.items_snapshot:
        physical_stores = {
            row.get('store') or store_id for row in order.items_snapshot
            if not row.get('is_digital')
            and (
                store_id is None or not row.get('store')
                or str(row.get('store')) == str(store_id)
            )
        }
    elif order.cart_id:
        items = CartItem.objects.filter(cart_id=order.cart_id, product__is_digital=False)
        if store_id is not None:
            items = items.filter(product__store_id=store_id)
        physical_stores = set(items.values_list('product__store_id', flat=True))
        if not physical_stores and not CartItem.objects.filter(cart_id=order.cart_id).exists():
            physical_stores = {store_id}
    else:
        # Missing historical composition is not proof of digital fulfillment.
        physical_stores = {store_id}
    deliveries = {
        str(fulfillment.store_id): fulfillment.delivered_at
        for fulfillment in order.fulfillments.all()
    }
    for physical_store in physical_stores:
        delivered_at = deliveries.get(str(physical_store)) or order.delivered_at
        if delivered_at is None:
            return None
        release_at = max(release_at, delivered_at + window)
    return release_at


def merchant_sale_is_pending(sale: StoreEarningsLedger, now: datetime) -> bool:
    if sale.order_id and sale.order.payment_disputed:
        return True
    if not sale.order_id and sale.available_at is None:
        return sale.status == StoreEarningsLedger.STATUS_PENDING
    release_at = merchant_earnings_release_at(sale.order, sale.store_id, sale.available_at)
    return release_at is None or release_at > now


def pending_merchant_ledger_net(ledger: QuerySet[StoreEarningsLedger]) -> Decimal:
    """Group orphaned same-order rows so a refund is deducted only once."""
    groups: dict[tuple[int | None, int | None], Decimal] = {}
    now = timezone.now()
    sales = ledger.filter(entry_type=StoreEarningsLedger.TYPE_SALE).select_related(
        'order',
    ).prefetch_related('order__fulfillments')
    for sale in sales:
        if merchant_sale_is_pending(sale, now):
            key = (sale.order_id, sale.store_id)
            groups[key] = groups.get(key, Decimal('0.00')) + sale.net_amount
    pending = Decimal('0.00')
    for (order_id, store_id), net in groups.items():
        refunds = (
            ledger.filter(
                order_id=order_id, store_id=store_id,
                entry_type=StoreEarningsLedger.TYPE_REFUND,
            ).aggregate(net=Sum('net_amount'))['net'] or Decimal('0.00')
            if order_id is not None else Decimal('0.00')
        )
        pending += max(Decimal('0.00'), net + refunds)
    return pending


def calculate_store_tier(
    store: Store | None,
    gross_sales: Decimal | None = None,
) -> dict[str, Any]:
    """
    Computes the seller tier and badge color based on cumulative sales volume:
    - Official Store: 'official' (Gold badge #e5a93c)
    - Starter: $0 - $4,999 (Sapphire Blue badge #2563eb)
    - Booster: $5,000 - $24,999 (Slate Silver badge #64748b)
    - Accelerator: $25,000 - $99,999 (Vivid Purple badge #7c3aed)
    - Power Seller: $100,000 - $499,999 (Emerald Green badge #059669)
    - Mega Seller: $500,000 - $999,999 (Flame Orange badge #ea580c)
    - Legendary Seller: $1,000,000+ (Cosmic Ruby Flame badge #ff0055)
    """
    if not store:
        return {
            'tier': 'starter',
            'name': 'Starter',
            'badge_color': 'blue',
            'badge_hex': '#2563eb',
            'min_sales': 0.0,
            'current_sales': 0.0,
            'next_tier': 'Booster',
            'next_threshold': 5000.0,
        }

    if getattr(store, 'is_official', False):
        return {
            'tier': 'official',
            'name': 'Official Store',
            'badge_color': 'gold',
            'badge_hex': '#d97706',
            'min_sales': 0.0,
            'current_sales': 0.0,
            'next_tier': None,
            'next_threshold': None,
        }

    gross = gross_sales
    if gross is None:
        gross = StoreEarningsLedger.objects.filter(
            store=store,
            entry_type=StoreEarningsLedger.TYPE_SALE,
        ).exclude(
            status=StoreEarningsLedger.STATUS_REVERSED,
        ).aggregate(total=Sum('gross_amount'))['total'] or Decimal('0.00')

    sales = float(gross)

    if sales >= 1000000.0:
        return {
            'tier': 'legendary',
            'name': 'Legendary Seller',
            'badge_color': 'legendary',
            'badge_hex': '#ff0055',
            'min_sales': 1000000.0,
            'current_sales': sales,
            'next_tier': None,
            'next_threshold': None,
        }
    elif sales >= 500000.0:
        return {
            'tier': 'mega',
            'name': 'Mega Seller',
            'badge_color': 'orange',
            'badge_hex': '#ea580c',
            'min_sales': 500000.0,
            'current_sales': sales,
            'next_tier': 'Legendary Seller',
            'next_threshold': 1000000.0,
        }
    elif sales >= 100000.0:
        return {
            'tier': 'power',
            'name': 'Power Seller',
            'badge_color': 'emerald',
            'badge_hex': '#059669',
            'min_sales': 100000.0,
            'current_sales': sales,
            'next_tier': 'Mega Seller',
            'next_threshold': 500000.0,
        }
    elif sales >= 25000.0:
        return {
            'tier': 'accelerator',
            'name': 'Accelerator',
            'badge_color': 'purple',
            'badge_hex': '#7c3aed',
            'min_sales': 25000.0,
            'current_sales': sales,
            'next_tier': 'Power Seller',
            'next_threshold': 100000.0,
        }
    elif sales >= 5000.0:
        return {
            'tier': 'booster',
            'name': 'Booster',
            'badge_color': 'silver',
            'badge_hex': '#64748b',
            'min_sales': 5000.0,
            'current_sales': sales,
            'next_tier': 'Accelerator',
            'next_threshold': 25000.0,
        }
    else:
        return {
            'tier': 'starter',
            'name': 'Starter',
            'badge_color': 'blue',
            'badge_hex': '#2563eb',
            'min_sales': 0.0,
            'current_sales': sales,
            'next_tier': 'Booster',
            'next_threshold': 5000.0,
        }


@transaction.atomic
def record_order_earnings_for_merchant(order: Any) -> list[StoreEarningsLedger]:
    """
    Given a completed/confirmed order, calculates net earnings for each participating store,
    creates StoreEarningsLedger entries in pending escrow status, and increments the merchant's
    pending balance.
    """
    from payment.models import Order

    if not order or not order.ordered or order.paid_total <= 0:
        return []

    default_fee_rate = getattr(
        settings, "PLATFORM_FEE_PERCENT", Decimal("4.00")
    ) / Decimal("100.0")

    # Gather items by store from cart or snapshot
    created_entries: list[StoreEarningsLedger] = []

    items_by_store: dict[int, Decimal] = {}
    if order.cart_id and not order.items_snapshot:
        items = CartItem.objects.filter(cart_id=order.cart_id).select_related(
            "product", "product__store"
        )
        for item in items:
            store_id = (
                item.product.store_id if item.product and item.product.store else None
            )
            if not store_id:
                continue
            line_val = (
                Decimal(item.quantity)
                * Decimal(str(item.product.price))
                * (Decimal("100.0") - Decimal(str(item.product.discount)))
                / Decimal("100.0")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            items_by_store[store_id] = (
                items_by_store.get(store_id, Decimal("0.00")) + line_val
            )
    elif order.items_snapshot:
        from payment.accounting import order_paid_lines

        for snap in order_paid_lines(order):
            store_id = snap.get("store")
            if not store_id:
                continue
            line_val = Decimal(snap["net_total"])
            items_by_store[store_id] = (
                items_by_store.get(store_id, Decimal("0.00")) + line_val
            )

    for store_id, gross_amount in items_by_store.items():
        if gross_amount <= Decimal("0.00"):
            continue

        store = Store.objects.filter(pk=store_id).select_related("user").first()
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
        fee_rate = Decimal("0.00") if is_official else default_fee_rate
        fee_amount = (gross_amount * fee_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        net_amount = (gross_amount - fee_amount).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        wallet, _ = MerchantWallet.objects.select_for_update().get_or_create(
            user=store.user
        )

        # Check if order is already past refund window (e.g. backdated in tests or delayed processing)
        now = timezone.now()
        available_at = merchant_earnings_release_at(order, store.pk)
        is_cleared = available_at is not None and available_at <= now
        entry_status = (
            StoreEarningsLedger.STATUS_AVAILABLE
            if is_cleared
            else StoreEarningsLedger.STATUS_PENDING
        )
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
def settle_pending_merchant_earnings(user: Any = None) -> int:
    """
    Recheck delivery evidence, including rows cleared under the old sale-only rule.
    Recalculate each affected wallet once to avoid double-crediting funds already
    exposed by a dashboard recalculation before the settlement worker ran.
    """
    now = timezone.now()
    eligible_wallets = MerchantWallet.objects.all()
    if user is not None:
        eligible_wallets = eligible_wallets.filter(user=user)
    # Financial mutations take wallet locks before ledger locks. A payout request
    # settles only its own wallet, so it cannot invert cross-merchant lock order.
    wallet_ids = list(eligible_wallets.order_by('pk').values_list('pk', flat=True))
    list(MerchantWallet.objects.select_for_update().filter(pk__in=wallet_ids).order_by('pk'))
    pending_entries = (
        StoreEarningsLedger.objects.select_for_update(of=("self",))
        .filter(
            entry_type=StoreEarningsLedger.TYPE_SALE,
            wallet_id__in=wallet_ids,
            status__in=[StoreEarningsLedger.STATUS_PENDING, StoreEarningsLedger.STATUS_AVAILABLE],
        )
        .filter(
            models.Q(order__isnull=True)
            | models.Q(order__paid_total__gt=0)
        )
        .select_related("wallet", "order")
        .prefetch_related('order__fulfillments')
    )

    count = 0
    wallets: dict[int, MerchantWallet] = {}

    for entry in pending_entries:
        pending = merchant_sale_is_pending(entry, now)
        target = StoreEarningsLedger.STATUS_PENDING if pending else StoreEarningsLedger.STATUS_AVAILABLE
        release_at = merchant_earnings_release_at(entry.order, entry.store_id, entry.available_at)
        if entry.status == StoreEarningsLedger.STATUS_PENDING and not pending:
            count += 1
        if entry.status != target or entry.available_at != release_at:
            entry.status = target
            entry.available_at = release_at
            entry.cleared_at = None if pending else now
            entry.save(update_fields=['status', 'available_at', 'cleared_at', 'updated'])
        wallets[entry.wallet_id] = entry.wallet

    for wallet in wallets.values():
        calculate_merchant_financials(wallet.user)

    return count


@transaction.atomic
def process_refund_deduction(order: Any, refund_amount: Decimal | None = None, store: Any = None) -> None:
    """
    Reverses or adjusts merchant earnings when a customer order is refunded.
    """
    from payment.models import Order

    entries = StoreEarningsLedger.objects.filter(
        order=order,
        entry_type=StoreEarningsLedger.TYPE_SALE,
    ).exclude(status=StoreEarningsLedger.STATUS_REVERSED)

    if store:
        entries = entries.filter(store=store)

    wallet_ids = list(entries.order_by().values_list('wallet_id', flat=True).distinct())
    list(MerchantWallet.objects.select_for_update().filter(pk__in=wallet_ids).order_by('pk'))
    entries = list(entries.select_for_update(of=('self',)))
    from rest_framework.exceptions import ValidationError
    if refund_amount is not None and store is None and len({entry.store_id for entry in entries}) > 1:
        raise ValidationError({'store': 'Partial refunds across multiple stores require explicit store attribution.'})
    remaining = {entry.pk: max(Decimal('0.00'), entry.gross_amount + (StoreEarningsLedger.objects.filter(order=order, store=entry.store, entry_type=StoreEarningsLedger.TYPE_REFUND).aggregate(total=Sum('gross_amount'))['total'] or Decimal('0.00'))) for entry in entries}
    total_gross = sum(remaining.values(), Decimal('0.00'))
    target = min(Decimal(str(refund_amount)), total_gross) if refund_amount is not None else total_gross
    for entry in entries:
        gross_share = (target * remaining[entry.pk] / total_gross).quantize(Decimal('0.01')) if total_gross else Decimal('0.00')
        if gross_share <= 0:
            continue
        net_share = (gross_share * entry.net_amount / entry.gross_amount).quantize(Decimal('0.01')) if entry.gross_amount else Decimal('0.00')
        fee_share = gross_share - net_share
        wallet = entry.wallet or (entry.store and entry.store.user and MerchantWallet.objects.filter(user=entry.store.user).first())
        if wallet:
            wallet = MerchantWallet.objects.select_for_update().get(pk=wallet.pk)
            # If entry was pending, subtract from pending; if available, subtract from available
            if entry.status == StoreEarningsLedger.STATUS_PENDING:
                wallet.pending_balance = max(Decimal('0.00'), wallet.pending_balance - net_share)
            elif entry.status == StoreEarningsLedger.STATUS_AVAILABLE:
                wallet.available_balance -= net_share
            wallet.save(update_fields=['pending_balance', 'available_balance', 'updated'])

        StoreEarningsLedger.objects.create(wallet=wallet, store=entry.store, order=order, entry_type=StoreEarningsLedger.TYPE_REFUND, gross_amount=-gross_share, fee_amount=-fee_share, net_amount=-net_share, status=StoreEarningsLedger.STATUS_COMPLETED, description=f"Partial refund for order #{order.orderId}", reference=f"REF-{order.orderId}-{StoreEarningsLedger.objects.filter(order=order, entry_type=StoreEarningsLedger.TYPE_REFUND).count() + 1}")
        already_refunded = abs(StoreEarningsLedger.objects.filter(order=order, store=entry.store, entry_type=StoreEarningsLedger.TYPE_REFUND).aggregate(total=Sum('gross_amount'))['total'] or Decimal('0.00'))
        if already_refunded >= entry.gross_amount:
            entry.status = StoreEarningsLedger.STATUS_REVERSED
            entry.description += " (Fully refunded / reversed)"
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

    if not amount.is_finite() or amount <= 0:
        raise ValidationError({'amount': 'Enter a positive payout amount.'})
    if store and (store.user_id != user.pk or store.is_official):
        raise ValidationError({'store': 'Choose one of your merchant stores.'})
    settle_pending_merchant_earnings(user=user)
    wallet, _ = MerchantWallet.objects.select_for_update().get_or_create(user=user)
    calculate_merchant_financials(user)
    wallet.refresh_from_db()

    allocations: list[tuple[Store, Decimal]] = []
    if store:
        store_available = Decimal(
            calculate_store_financials(store)['available_balance']
        )
        if amount > store_available:
            raise ValidationError({
                'detail': (
                    f'Requested payout amount (${amount}) exceeds the selected '
                    f'store\'s available cleared balance (${store_available}).'
                )
            })
        allocations = [(store, amount)]
    else:
        merchant_stores = list(
            Store.objects.filter(user=user)
            .exclude(is_official=True)
            .exclude(user__is_superuser=True)
            .order_by('pk')
        )
        balances = [
            (
                merchant_store,
                max(
                    Decimal('0.00'),
                    Decimal(
                        calculate_store_financials(merchant_store)[
                            'available_balance'
                        ]
                    ),
                ),
            )
            for merchant_store in merchant_stores
        ]
        merchant_available = sum(
            (balance for _, balance in balances), Decimal('0.00')
        )
        if amount > merchant_available:
            raise ValidationError({
                'detail': (
                    f'Requested payout amount (${amount}) exceeds available '
                    f'merchant-store funds (${merchant_available}).'
                )
            })
        remaining = amount
        for merchant_store, balance in balances:
            allocation = min(balance, remaining)
            if allocation > 0:
                allocations.append((merchant_store, allocation))
                remaining -= allocation
            if remaining <= 0:
                break

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

    for allocated_store, allocated_amount in allocations:
        StoreEarningsLedger.objects.create(
            wallet=wallet,
            store=allocated_store,
            entry_type=StoreEarningsLedger.TYPE_PAYOUT,
            gross_amount=allocated_amount,
            fee_amount=Decimal("0.00"),
            net_amount=-allocated_amount,
            status=StoreEarningsLedger.STATUS_PENDING,
            description=(
                f"Payout withdrawal request ({reference}) for store "
                f"'{allocated_store.name}'"
            ),
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
    from rest_framework.exceptions import ValidationError

    StorePayout.objects.select_for_update().get(pk=payout.pk)
    payout.refresh_from_db()
    if payout.status != StorePayout.STATUS_PENDING:
        raise ValidationError({"detail": f"This payout request has already been processed ({payout.status})."})

    wallet = payout.wallet or (payout.store and get_or_create_merchant_wallet(payout.store.user))
    wallet_obj = MerchantWallet.objects.select_for_update().get(pk=wallet.pk) if wallet else None

    if action == "approve":
        if wallet_obj:
            # Available funds already deduct ALL pending reservations, including
            # this payout. Zero is fully funded; negative means a refund or other
            # adjustment has invalidated the reservation pool.
            financials = calculate_merchant_financials(wallet_obj.user)
            if Decimal(financials['available_balance']) < Decimal('0.00'):
                raise ValidationError({
                    'detail': 'Payout reservations exceed cleared funds. Resolve refunds or release other pending payouts before approving this payout.'
                })
            wallet_obj.refresh_from_db()
        if (
            wallet_obj
            and StoreEarningsLedger.objects.filter(
                wallet=wallet_obj,
                order__payment_disputed=True,
            ).exists()
        ):
            raise ValidationError(
                {
                    "detail": "Resolve active payment disputes before approving this payout."
                }
            )
        if payout.payout_method == StorePayout.METHOD_STRIPE_CONNECT:
            if (
                not wallet
                or not wallet.stripe_account_id
                or not getattr(settings, 'STRIPE_SECRET', '')
            ):
                raise ValidationError({'detail': 'Connect a Stripe account and configure payouts before approving this transfer.'})
            import stripe
            stripe.api_key = settings.STRIPE_SECRET
            try:
                account = stripe.Account.retrieve(wallet.stripe_account_id)
                wallet.stripe_details_submitted = bool(
                    account.get('details_submitted', False)
                )
                wallet.stripe_payouts_enabled = bool(
                    account.get('payouts_enabled', False)
                )
                wallet.save(
                    update_fields=[
                        'stripe_details_submitted',
                        'stripe_payouts_enabled',
                        'updated',
                    ]
                )
                if not wallet.stripe_payouts_enabled:
                    raise ValidationError({
                        'detail': 'Stripe payouts are not enabled for this account yet.'
                    })
                transfer = stripe.Transfer.create(
                    amount=int((payout.amount * 100).quantize(Decimal('1'))),
                    currency=getattr(settings, 'STRIPE_CURRENCY', 'usd').lower(),
                    destination=wallet.stripe_account_id,
                    metadata={'payout_id': str(payout.pk), 'reference': payout.reference},
                    idempotency_key=f"payout-transfer-{payout.reference}",
                )
            except ValidationError:
                raise
            except Exception as exc:
                logger.exception('Stripe payout transfer failed for payout %s', payout.pk)
                raise ValidationError({'detail': 'Unable to verify or complete the Stripe transfer. Please retry.'}) from exc
            notes = f"Stripe transfer {transfer.id}" if not notes else f"{notes} · Stripe transfer {transfer.id}"
        payout.status = StorePayout.STATUS_COMPLETED
        payout.processed_at = timezone.now()
        payout.processed_by = processed_by
        if notes:
            payout.notes = notes
        payout.save(update_fields=['status', 'processed_at', 'processed_by', 'notes', 'updated'])

        if wallet_obj:
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
        payout.save(
            update_fields=["status", "notes", "processed_at", "processed_by", "updated"]
        )

        if wallet_obj:
            wallet_obj.available_balance += payout.amount
            wallet_obj.save(update_fields=["available_balance", "updated"])

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

    ledger = StoreEarningsLedger.objects.filter(
        store=store,
        entry_type__in=[StoreEarningsLedger.TYPE_SALE, StoreEarningsLedger.TYPE_REFUND],
    ).filter(models.Q(order__isnull=True) | models.Q(order__paid_total__gt=0))
    if ledger.exists():
        gross = ledger.aggregate(total=Sum("gross_amount"))["total"] or Decimal("0")
        fee = ledger.aggregate(total=Sum("fee_amount"))["total"] or Decimal("0")
        net = ledger.aggregate(total=Sum("net_amount"))["total"] or Decimal("0")
        pending = pending_merchant_ledger_net(ledger)
        cleared = net - pending
        payout_ledger = StoreEarningsLedger.objects.filter(
            wallet__user=store.user,
            store=store,
            entry_type=StoreEarningsLedger.TYPE_PAYOUT,
        )
        payout_references = payout_ledger.values('reference')
        completed = abs(
            payout_ledger.filter(status=StoreEarningsLedger.STATUS_COMPLETED)
            .aggregate(total=Sum('net_amount'))['total'] or Decimal('0')
        ) + (
            store.payouts.filter(status=StorePayout.STATUS_COMPLETED)
            .exclude(reference__in=payout_references)
            .aggregate(total=Sum('amount'))['total'] or Decimal('0')
        )
        reserved = abs(
            payout_ledger.filter(status=StoreEarningsLedger.STATUS_PENDING)
            .aggregate(total=Sum('net_amount'))['total'] or Decimal('0')
        ) + (
            store.payouts.filter(status=StorePayout.STATUS_PENDING)
            .exclude(reference__in=payout_references)
            .aggregate(total=Sum('amount'))['total'] or Decimal('0')
        )
        return {
            "gross_sales": format(gross, ".2f"),
            "platform_fee_percent": format(
                Decimal("0")
                if store.is_official
                else Decimal(str(getattr(settings, "PLATFORM_FEE_PERCENT", 4))),
                ".2f",
            ),
            "platform_fee_deducted": format(fee, ".2f"),
            "net_sales": format(net, ".2f"),
            "in_review": format(pending, ".2f"),
            "cleared_total": format(cleared, ".2f"),
            "payouts_completed": format(completed, ".2f"),
            "payouts_pending": format(reserved, ".2f"),
            "available_balance": format(cleared - completed - reserved, ".2f"),
            "refund_window_days": getattr(settings, "REFUND_WINDOW_DAYS", 7),
        }

    sales_orders = Order.objects.filter(
        ordered=True,
        paid_total__gt=0,
        status__in=["confirmed", "shipped", "delivered", "picked up"],
    )
    items = CartItem.objects.filter(
        product__store=store, cart__in=sales_orders.values("cart_id")
    )
    line_value = ExpressionWrapper(
        F("quantity")
        * F("product__price")
        * (100 - F("product__discount"))
        / Decimal("100.0"),
        output_field=DecimalField(max_digits=24, decimal_places=2),
    )
    totals = items.aggregate(value=Sum(line_value), units=Sum("quantity"))

    is_official = store.is_official or bool(store.user and store.user.is_superuser)
    fee_rate = Decimal('0.00') if is_official else (getattr(settings, 'PLATFORM_FEE_PERCENT', Decimal('4.00')) / Decimal('100.0'))
    fee_percent = Decimal('0.00') if is_official else getattr(settings, 'PLATFORM_FEE_PERCENT', Decimal('4.00'))

    refund_window = getattr(settings, 'REFUND_WINDOW_DAYS', 7)
    now = timezone.now()
    cleared_ids = [
        order.pk for order in sales_orders.prefetch_related('fulfillments')
        if (release_at := merchant_earnings_release_at(order, store.pk)) is not None
        and release_at <= now and not order.payment_disputed
    ]

    in_review_orders = sales_orders.exclude(pk__in=cleared_ids)
    in_review_items = CartItem.objects.filter(product__store=store, cart__in=in_review_orders.values('cart_id'))
    in_review_totals = in_review_items.aggregate(value=Sum(line_value))
    in_review_gross = in_review_totals['value'] or Decimal('0.00')
    in_review_net = (in_review_gross * (Decimal('1.00') - fee_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    cleared_orders = sales_orders.filter(pk__in=cleared_ids)
    cleared_items = CartItem.objects.filter(product__store=store, cart__in=cleared_orders.values('cart_id'))
    cleared_totals = cleared_items.aggregate(value=Sum(line_value))
    cleared_gross = cleared_totals['value'] or Decimal('0.00')
    cleared_net = (cleared_gross * (Decimal('1.00') - fee_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    gross_value = totals['value'] or Decimal('0.00')
    platform_fee = (gross_value * fee_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    net_value = (gross_value - platform_fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    payouts_completed = store.payouts.filter(status=StorePayout.STATUS_COMPLETED).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    payouts_pending = store.payouts.filter(status=StorePayout.STATUS_PENDING).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    available_balance = cleared_net - payouts_completed - payouts_pending

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


@transaction.atomic
def calculate_merchant_financials(user: Any) -> dict:
    """
    Consolidates financial metrics across all stores owned by a user/merchant,
    including ledger consistency and store breakdown.
    """
    wallet, _ = MerchantWallet.objects.select_for_update().get_or_create(user=user)
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

    # Historical hard deletions left wallet-owned records without a store.
    # Keep those earnings and reservations in the authoritative wallet totals.
    orphaned = StoreEarningsLedger.objects.filter(wallet=wallet, store__isnull=True)
    orphaned_earnings = orphaned.filter(
        entry_type__in=[StoreEarningsLedger.TYPE_SALE, StoreEarningsLedger.TYPE_REFUND],
    ).filter(Q(order__isnull=True) | Q(order__paid_total__gt=0))
    orphaned_totals = orphaned_earnings.aggregate(
        gross=Sum('gross_amount'), fee=Sum('fee_amount'), net=Sum('net_amount'),
    )
    orphaned_net = orphaned_totals['net'] or Decimal('0.00')
    orphaned_pending = pending_merchant_ledger_net(orphaned_earnings)
    total_gross += orphaned_totals['gross'] or Decimal('0.00')
    total_fee += orphaned_totals['fee'] or Decimal('0.00')
    total_net += orphaned_net
    total_in_review += orphaned_pending
    total_cleared += orphaned_net - orphaned_pending
    orphaned_payouts = orphaned.filter(entry_type=StoreEarningsLedger.TYPE_PAYOUT)
    total_payouts_completed += abs(orphaned_payouts.filter(
        status=StoreEarningsLedger.STATUS_COMPLETED,
    ).aggregate(net=Sum('net_amount'))['net'] or Decimal('0.00'))
    total_payouts_pending += abs(orphaned_payouts.filter(
        status=StoreEarningsLedger.STATUS_PENDING,
    ).aggregate(net=Sum('net_amount'))['net'] or Decimal('0.00'))

    payout_references = StoreEarningsLedger.objects.filter(
        wallet=wallet,
        entry_type=StoreEarningsLedger.TYPE_PAYOUT,
    ).values('reference')
    unified_payouts = StorePayout.objects.filter(
        wallet=wallet,
        store__isnull=True,
    ).exclude(reference__in=payout_references)
    total_payouts_completed += unified_payouts.filter(
        status=StorePayout.STATUS_COMPLETED
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_payouts_pending += unified_payouts.filter(
        status=StorePayout.STATUS_PENDING
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Synchronize wallet balance fields to match verified cleared funds
    computed_available = total_cleared - total_payouts_completed - total_payouts_pending
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


def get_store_user_role(store: Store, user: Any) -> str | None:
    """Returns the effective role of the user within this store.

    Roles:
      - 'owner': Primary store owner or platform admin/superuser
      - 'store_admin': Delegated store administrator (full access except ownership transfer)
      - 'catalog_manager': Can manage products, specifications, and images
      - 'fulfillment_specialist': Can view orders, print packing slips, and update tracking
      - None: User has no access to this store
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    if (
        (getattr(user, 'is_superuser', False) or getattr(user, 'is_business_admin', False))
        and store.is_official
    ):
        return 'owner'
    if store.user_id == user.id:
        return 'owner'
    from store.models import StoreTeamMember
    membership = StoreTeamMember.objects.filter(store=store, user=user, status=StoreTeamMember.STATUS_ACTIVE).first()
    if membership:
        return membership.role
    # Check if there is an unlinked pending invitation for this user's email
    user_email = getattr(user, 'email', None)
    if user_email:
        pending = StoreTeamMember.objects.filter(
            store=store,
            invited_email__iexact=user_email.strip().lower(),
            status=StoreTeamMember.STATUS_PENDING,
        ).first()
        if pending:
            with transaction.atomic():
                pending.user = user
                pending.status = StoreTeamMember.STATUS_ACTIVE
                pending.save(update_fields=['user', 'status', 'updated'])
            return pending.role
    return None


@transaction.atomic
def link_pending_store_team_invitations(user: Any) -> int:
    """
    When a user registers, verifies their email, or signs in, automatically
    link any pending store team invitations matching their canonical email.
    """
    if not user or not getattr(user, 'email', None):
        return 0
    from store.models import StoreTeamMember
    pending = StoreTeamMember.objects.select_for_update().filter(
        invited_email__iexact=user.email.strip().lower(),
        status=StoreTeamMember.STATUS_PENDING,
    ).filter(Q(user__isnull=True) | Q(user=user)).order_by('store_id', 'pk')
    count = 0
    for member in pending:
        already_linked = StoreTeamMember.objects.filter(
            store_id=member.store_id, user=user,
        ).exclude(pk=member.pk).exists()
        if already_linked:
            # Older invitation flows could leave a pending row beside an active
            # membership. Preserve the assigned role instead of crashing login
            # or letting an obsolete invitation replace it.
            member.delete()
            continue
        member.user = user
        member.status = StoreTeamMember.STATUS_ACTIVE
        member.save(update_fields=['user', 'status', 'updated'])
        count += 1
    return count


def can_manage_products(store: Store, user: Any) -> bool:
    role = get_store_user_role(store, user)
    return role in ('owner', 'store_admin', 'catalog_manager')


def can_manage_orders(store: Store, user: Any) -> bool:
    role = get_store_user_role(store, user)
    return role in ('owner', 'store_admin', 'fulfillment_specialist')


def can_manage_team(store: Store, user: Any) -> bool:
    if (getattr(user, 'is_superuser', False) or getattr(user, 'is_business_admin', False)) and store.is_official:
        return True
    role = get_store_user_role(store, user)
    return role in ('owner', 'store_admin')


def can_manage_financials(store: Store, user: Any) -> bool:
    role = get_store_user_role(store, user)
    return role == 'owner'


