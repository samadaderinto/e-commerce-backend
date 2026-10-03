from __future__ import annotations

import logging
from celery import shared_task
from store.services import publish_due_products, settle_pending_merchant_earnings

logger = logging.getLogger(__name__)


@shared_task(name="store.settle_pending_merchant_earnings_task")
def settle_pending_merchant_earnings_task() -> int:
    """
    Celery task to release merchant earnings held in review escrow
    into withdrawable available balance once the refund window has elapsed.
    """
    settled_count = settle_pending_merchant_earnings()
    if settled_count > 0:
        logger.info("Settled %d merchant ledger entries into available balance.", settled_count)
    return settled_count


@shared_task(name="store.publish_due_products_task")
def publish_due_products_task() -> int:
    """
    Celery task to publish scheduled products whose visibility timestamp is reached.
    """
    count = publish_due_products()
    if count > 0:
        logger.info("Published %d scheduled products.", count)
    return count
