"""Safe refund failure text for persisted records and public payloads."""

from core.models import Refund

REFUND_FAILURE_MESSAGE = "Payment provider refund failed. Support will review it."


def refund_failure_reason(refund: Refund) -> str:
    # Historical failed rows may contain a serialized Python exception. Keep
    # those representations out of successful GET payloads as well as errors.
    if refund.status == Refund.STATUS_FAILED:
        return REFUND_FAILURE_MESSAGE
    return refund.failure_reason
