"""Recognize legacy settlement evidence without declaring unpaid COD receipts paid."""

from decimal import Decimal

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.models import Sum


def backfill_settlement(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Order = apps.get_model("payment", "Order")
    Attempt = apps.get_model("payment", "CheckoutAttempt")
    WalletTransaction = apps.get_model("core", "UserWalletTransaction")
    Refund = apps.get_model("core", "Refund")
    database = schema_editor.connection.alias
    for order in Order.objects.using(database).filter(ordered=True).iterator():
        paid = Decimal("0")
        wallet_paid = Decimal("0")
        if order.payment_type in {"user_wallet", "wallet"}:
            debits = WalletTransaction.objects.using(database).filter(
                wallet__user_id=order.user_id,
                transaction_type="debit",
                reference=order.orderId,
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
            if debits >= order.total:
                paid = order.total
                wallet_paid = order.total
        elif order.stripe_session_id and order.payment_type in {
            "stripe_wallet",
            "card",
            "split_tender",
        }:
            # These sessions were assigned only after the legacy paid-session check.
            paid = order.total
            attempt = (
                Attempt.objects.using(database)
                .filter(session_id=order.stripe_session_id, status="completed")
                .first()
            )
            wallet_paid = min(paid, attempt.wallet_amount) if attempt else Decimal("0")
        refunded = Decimal("0")
        for refund in Refund.objects.using(database).filter(
            order_id=order.pk, status="approved"
        ):
            refunded += refund.refund_amount or paid
        refunded = min(paid, refunded)
        if order.status in {"refunded", "cancelled"}:
            refunded = paid
        wallet_refunded = (
            (refunded * wallet_paid / paid).quantize(Decimal(".01"))
            if paid
            else Decimal("0")
        )
        Order.objects.using(database).filter(pk=order.pk).update(
            paid_total=paid,
            wallet_paid=wallet_paid,
            refunded_total=refunded,
            wallet_refunded_total=wallet_refunded,
            card_refunded_total=refunded - wallet_refunded,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("payment", "0018_order_card_refunded_total_order_paid_total_and_more"),
        ("core", "0019_userwallettransaction_idempotency_key"),
    ]
    operations = [migrations.RunPython(backfill_settlement, migrations.RunPython.noop)]
