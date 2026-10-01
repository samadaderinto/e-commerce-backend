from django.conf import settings
from django.db import transaction

from notification.models import NotificationDelivery


def _schedule_delivery(delivery):
    transaction.on_commit(
        lambda: _dispatch_delivery(delivery.pk),
        robust=True,
    )
    return delivery


def _dispatch_delivery(delivery_id):
    from notification.tasks import deliver_notification_task

    updated = NotificationDelivery.objects.filter(
        pk=delivery_id,
        status=NotificationDelivery.STATUS_PENDING,
    ).update(status=NotificationDelivery.STATUS_QUEUED)
    if not updated:
        return
    try:
        deliver_notification_task.apply_async(
            args=(delivery_id,),
            queue=settings.CELERY_TASK_DEFAULT_QUEUE,
        )
    except Exception:
        NotificationDelivery.objects.filter(
            pk=delivery_id,
            status=NotificationDelivery.STATUS_QUEUED,
        ).update(status=NotificationDelivery.STATUS_PENDING)
        raise


def queue_email_delivery(
    recipient_email,
    subject,
    body,
    *,
    notification=None,
    recipient=None,
    reply_to="",
    is_html=False,
):
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


def queue_push_delivery(notification):
    delivery = NotificationDelivery.objects.create(
        channel=NotificationDelivery.CHANNEL_PUSH,
        notification=notification,
        recipient=notification.recipient,
    )
    return _schedule_delivery(delivery)
