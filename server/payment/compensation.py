"""Verify provider settlement before marking checkout compensation complete."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import stripe


def create_settled_compensation_refund(payment_intent: str, idempotency_key: str) -> bool:
    result: Any = stripe.Refund.create(
        payment_intent=payment_intent, idempotency_key=idempotency_key,
    )
    status: Any = (
        result.get('status') if isinstance(result, Mapping)
        else getattr(result, 'status', None)
    )
    reference: Any = (
        result.get('id') if isinstance(result, Mapping)
        else getattr(result, 'id', None)
    )
    if status in ('pending', 'requires_action') and isinstance(reference, str) and reference:
        # Replaying an idempotent create may return its original pending response.
        # Retrieve the current refund rather than treating that cached reply as final.
        result = stripe.Refund.retrieve(reference)
        status = (
            result.get('status') if isinstance(result, Mapping)
            else getattr(result, 'status', None)
        )
    return status == 'succeeded'
