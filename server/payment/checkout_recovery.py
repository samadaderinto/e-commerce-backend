"""Release expired wallet reservations and compensate paid checkouts that fail."""
import logging
from typing import Any
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from celery import shared_task
from core.services import credit_user_wallet
from core.models import User
from payment.models import CheckoutAttempt, Order

logger = logging.getLogger(__name__)


@transaction.atomic
def compensate_checkout(attempt: CheckoutAttempt, session: Any, reason: str) -> bool:
    import stripe
    stripe.api_key = settings.STRIPE_SECRET
    User.objects.select_for_update().get(pk=attempt.user_id)
    attempt = CheckoutAttempt.objects.select_for_update().get(pk=attempt.pk)
    if attempt.status in {'completed', 'released', 'refunded'}:
        return True
    if Order.objects.filter(checkout_key=attempt.checkout_key).exists():
        attempt.status = 'completed'
        attempt.save(update_fields=['status', 'updated'])
        return True
    attempt.failure_reason = reason
    if session.get('payment_status') == 'paid':
        intent = session.get('payment_intent')
        attempt.payment_intent = str(intent.get('id', '') if isinstance(intent, dict) else intent or '')
        try:
            if not attempt.payment_intent:
                raise ValueError('Paid session has no payment intent.')
            stripe.Refund.create(payment_intent=attempt.payment_intent,
                                 idempotency_key=f'failed-checkout-{attempt.checkout_key}')
        except Exception as exc:
            attempt.status = 'refund_pending'
            attempt.expires_at = timezone.now()
            attempt.failure_reason = f'{reason}; refund pending: {type(exc).__name__}'
            attempt.save(update_fields=['status', 'failure_reason', 'payment_intent', 'expires_at', 'updated'])
            return False
        attempt.status = 'refunded'
    else:
        # Never release a reservation while its hosted payment session remains open.
        if session.get('status') != 'expired':
            stripe.checkout.Session.expire(attempt.session_id)
        attempt.status = 'released'
    if attempt.wallet_amount > 0:
        credit_user_wallet(
            attempt.user,
            attempt.wallet_amount,
            'Released checkout wallet reservation',
            reference=f'release-{attempt.checkout_key}',
            idempotency_key=f'compensate-{attempt.checkout_key}-wallet',
        )
    attempt.save(update_fields=['status', 'failure_reason', 'payment_intent', 'updated'])
    return True


@shared_task(name='payment.recover_checkout_attempts')
def recover_checkout_attempts() -> int:
    import stripe
    stripe.api_key = settings.STRIPE_SECRET
    count = 0
    attempts = CheckoutAttempt.objects.filter(status__in=['reserved', 'refund_pending'], expires_at__lte=timezone.now())
    for attempt in attempts.iterator():
        try:
            session = stripe.checkout.Session.retrieve(attempt.session_id)
            if compensate_checkout(attempt, session, 'Checkout expired before order completion'):
                count += 1
        except Exception as exc:
            logger.warning("Checkout %s recovery deferred (%s)", attempt.pk, type(exc).__name__)
            # Durable rows remain eligible for the next scheduled recovery pass.
            continue
    return count
