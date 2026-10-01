import json
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from notification.models import Notification, NotificationDelivery, PushDevice


logger = logging.getLogger(__name__)


def _deliver_email(delivery):
    message = EmailMessage(
        delivery.subject,
        delivery.body,
        getattr(settings, "APPLICATION_EMAIL", settings.DEFAULT_FROM_EMAIL),
        [delivery.recipient_email],
        reply_to=[
            delivery.reply_to
            or getattr(settings, "APPLICATION_EMAIL", settings.DEFAULT_FROM_EMAIL)
        ],
    )
    if delivery.is_html:
        message.content_subtype = "html"
    message.send(fail_silently=False)


def _firebase_app():
    import firebase_admin

    try:
        return firebase_admin.get_app()
    except ValueError:
        credentials_json = getattr(settings, "FIREBASE_CREDENTIALS_JSON", "")
        if credentials_json:
            from firebase_admin import credentials

            credential = credentials.Certificate(json.loads(credentials_json))
            return firebase_admin.initialize_app(
                credential,
                options={"projectId": settings.FIREBASE_PROJECT_ID},
            )
        return firebase_admin.initialize_app(
            options={"projectId": settings.FIREBASE_PROJECT_ID},
        )


def _deliver_push(delivery):
    if not getattr(settings, "FCM_ENABLED", False):
        raise RuntimeError("FCM is disabled; the queued push delivery cannot be sent.")

    from firebase_admin import messaging

    notification = Notification.objects.get(pk=delivery.notification_id)
    app = _firebase_app()
    metadata = delivery.metadata or {}
    pending_tokens = metadata.get("pending_tokens")
    if not isinstance(pending_tokens, list):
        pending_tokens = list(
            PushDevice.objects.filter(user_id=notification.recipient_id)
            .values_list("token", flat=True)
        )
    if not pending_tokens:
        return {"sent": 0, "failed": 0}

    data = {
        "notification_id": str(notification.pk),
        "recipient_id": str(notification.recipient_id),
        "title": notification.verb.capitalize(),
        "body": notification.description or notification.verb.capitalize(),
    }
    event = (notification.data or {}).get("event")
    if isinstance(event, str):
        data["event"] = event
    url = (notification.data or {}).get("url")
    if isinstance(url, str) and url.startswith("/") and not url.startswith("//"):
        data["url"] = url

    sent = 0
    failed_tokens = []
    for start in range(0, len(pending_tokens), 500):
        batch = pending_tokens[start:start + 500]
        response = messaging.send_each_for_multicast(
            messaging.MulticastMessage(data=data, tokens=batch),
            app=app,
        )
        sent += response.success_count
        for token, result in zip(batch, response.responses):
            if result.success:
                continue
            error = result.exception
            error_code = getattr(error, "code", None)
            if error_code in {
                "messaging/registration-token-not-registered",
                "messaging/invalid-registration-token",
                "UNREGISTERED",
            }:
                PushDevice.objects.filter(
                    user_id=notification.recipient_id,
                    token=token,
                ).delete()
            else:
                failed_tokens.append(token)
            logger.warning(
                "FCM delivery failed for notification %s with code %s",
                notification.pk,
                error_code or error.__class__.__name__,
            )

    delivery.metadata = {**metadata, "pending_tokens": failed_tokens}
    delivery.save(update_fields=["metadata", "updated_at"])
    if failed_tokens:
        raise RuntimeError(
            f"FCM delivery failed for {len(failed_tokens)} device(s); will retry."
        )
    return {"sent": sent, "failed": 0}


@shared_task(name="notification.tasks.deliver_notification_task")
def deliver_notification_task(delivery_id):
    now = timezone.now()
    with transaction.atomic():
        delivery = NotificationDelivery.objects.select_for_update().get(pk=delivery_id)
        if delivery.status in {
            NotificationDelivery.STATUS_PROCESSING,
            NotificationDelivery.STATUS_SENT,
            NotificationDelivery.STATUS_FAILED,
        }:
            return {"status": delivery.status}
        if delivery.status in {
            NotificationDelivery.STATUS_PENDING,
            NotificationDelivery.STATUS_QUEUED,
        }:
            if delivery.available_at > now:
                return {"status": delivery.status}
        delivery.status = NotificationDelivery.STATUS_PROCESSING
        delivery.attempts += 1
        delivery.last_error = ""
        delivery.save(
            update_fields=["status", "attempts", "last_error", "updated_at"]
        )

    try:
        if delivery.channel == NotificationDelivery.CHANNEL_EMAIL:
            _deliver_email(delivery)
        elif delivery.channel == NotificationDelivery.CHANNEL_PUSH:
            _deliver_push(delivery)
        else:
            raise ValueError(f"Unsupported delivery channel: {delivery.channel}")
    except Exception as error:
        logger.exception(
            "Notification delivery %s failed on attempt %s",
            delivery.pk,
            delivery.attempts,
        )
        max_attempts = settings.NOTIFICATION_DELIVERY_MAX_ATTEMPTS
        if delivery.attempts >= max_attempts:
            delivery.status = NotificationDelivery.STATUS_FAILED
            delivery.last_error = str(error)[:4000]
        else:
            delay = min(30 * (2 ** (delivery.attempts - 1)), 3600)
            delivery.status = NotificationDelivery.STATUS_PENDING
            delivery.available_at = now + timedelta(seconds=delay)
            delivery.last_error = str(error)[:4000]
        delivery.save(
            update_fields=[
                "status",
                "available_at",
                "last_error",
                "updated_at",
            ]
        )
        return {"status": delivery.status, "attempts": delivery.attempts}

    delivery.status = NotificationDelivery.STATUS_SENT
    delivery.last_error = ""
    delivery.save(update_fields=["status", "last_error", "updated_at"])
    if (
        delivery.channel == NotificationDelivery.CHANNEL_EMAIL
        and delivery.notification_id
    ):
        Notification.objects.filter(pk=delivery.notification_id).update(emailed=True)
    return {"status": delivery.status, "attempts": delivery.attempts}


@shared_task(name="notification.tasks.recover_notification_deliveries")
def recover_notification_deliveries():
    now = timezone.now()
    stale_before = now - timedelta(
        seconds=settings.NOTIFICATION_DELIVERY_STALE_SECONDS
    )
    pending = Q(
        status=NotificationDelivery.STATUS_PENDING,
        available_at__lte=now,
    )
    abandoned = Q(
        status__in=[
            NotificationDelivery.STATUS_QUEUED,
            NotificationDelivery.STATUS_PROCESSING,
        ],
        updated_at__lte=stale_before,
    )

    with transaction.atomic():
        NotificationDelivery.objects.filter(
            status=NotificationDelivery.STATUS_PROCESSING,
            attempts__gte=settings.NOTIFICATION_DELIVERY_MAX_ATTEMPTS,
            updated_at__lte=stale_before,
        ).update(
            status=NotificationDelivery.STATUS_FAILED,
            last_error="Worker stopped during the final delivery attempt.",
            updated_at=now,
        )
        delivery_ids = list(
            NotificationDelivery.objects.filter(pending | abandoned)
            .order_by("created_at")
            .values_list("pk", flat=True)[:100]
        )
        if delivery_ids:
            NotificationDelivery.objects.filter(pk__in=delivery_ids).update(
                status=NotificationDelivery.STATUS_PENDING,
                available_at=now,
                updated_at=now,
            )

    queued = 0
    for delivery_id in delivery_ids:
        try:
            from notification.delivery import _dispatch_delivery

            _dispatch_delivery(delivery_id)
        except Exception:
            logger.exception(
                "Could not enqueue notification delivery %s for recovery",
                delivery_id,
            )
            NotificationDelivery.objects.filter(
                pk=delivery_id,
                status=NotificationDelivery.STATUS_PENDING,
            ).update(
                last_error="Queue publish failed during recovery.",
                updated_at=timezone.now(),
            )
        else:
            NotificationDelivery.objects.filter(
                pk=delivery_id,
                status=NotificationDelivery.STATUS_PENDING,
            ).update(
                status=NotificationDelivery.STATUS_QUEUED,
                last_error="",
                updated_at=timezone.now(),
            )
            queued += 1

    return {"queued": queued, "examined": len(delivery_ids)}
