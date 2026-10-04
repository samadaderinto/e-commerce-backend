from __future__ import annotations

from typing import Any, Optional

from django.conf import settings
from django.db import transaction

from notification.models import NotificationDelivery


import logging

logger = logging.getLogger(__name__)


def _schedule_delivery(delivery: NotificationDelivery) -> NotificationDelivery:
    transaction.on_commit(
        lambda: _dispatch_delivery(delivery.pk),
    )
    return delivery


def _dispatch_delivery(delivery_id: int) -> bool:
    from notification.tasks import deliver_notification_task

    updated = NotificationDelivery.objects.filter(
        pk=delivery_id,
        status=NotificationDelivery.STATUS_PENDING,
    ).update(status=NotificationDelivery.STATUS_QUEUED)
    if not updated:
        return False
    try:
        deliver_notification_task.apply_async(
            args=(delivery_id,),
            queue=settings.CELERY_TASK_DEFAULT_QUEUE,
        )
        return True
    except Exception as exc:
        NotificationDelivery.objects.filter(
            pk=delivery_id,
            status=NotificationDelivery.STATUS_QUEUED,
        ).update(
            status=NotificationDelivery.STATUS_PENDING,
            last_error=f"Queue dispatch failed: {exc}",
        )
        logger.warning(
            "Could not dispatch notification delivery %s immediately; left pending for retry: %s",
            delivery_id,
            exc,
        )
        return False


def queue_email_delivery(
    recipient_email: str,
    subject: str,
    body: str,
    *,
    notification: Optional[Any] = None,
    recipient: Optional[Any] = None,
    reply_to: str = "",
    is_html: bool = False,
) -> NotificationDelivery:
    if not recipient_email:
        raise ValueError("An email recipient is required.")

    delivery = NotificationDelivery.objects.create(
        channel=NotificationDelivery.CHANNEL_EMAIL,
        notification=notification,
        recipient=recipient,
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        reply_to=reply_to,
        is_html=is_html,
    )
    return _schedule_delivery(delivery)


def queue_push_delivery(notification: Any) -> NotificationDelivery:
    delivery = NotificationDelivery.objects.create(
        channel=NotificationDelivery.CHANNEL_PUSH,
        notification=notification,
        recipient=notification.recipient,
    )
    return _schedule_delivery(delivery)

