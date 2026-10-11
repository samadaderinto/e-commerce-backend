import hashlib
import json

from typing import Any

from notification.policy import CATEGORIES, POLICIES, ChannelPolicy, category_for, destination_for, store_ids_for

from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.utils import timezone
from django.db import models, transaction
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.request import Request
from core.listing_filters import ListingQuerySerializer
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema

from core.models import User
from store.models import Store
from notification.models import Notification
from notification.models import PushDevice
from notification.serializers import NotificationCountSerializer, NotificationSerializer
from notification.serializers import PushDeviceTokenSerializer


class NotificationPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100


def _content_type_for(obj):
    if obj is None:
        return None
    return ContentType.objects.get_for_model(obj, for_concrete_model=False)


def _send_external_notification(notification: Notification) -> None:
    """Persist external notification deliveries in the recovery outbox."""
    recipient = notification.recipient
    data = notification.data or {}
    if (getattr(recipient, "email", None) and data.get("email") is not False
            and POLICIES.get(data.get("event", ""), ChannelPolicy()).email):
        from notification.delivery import queue_email_delivery

        event = data.get("event", "")
        template = POLICIES.get(event, ChannelPolicy()).template
        if template:
            from utils.functions import send_mail

            send_mail(
                template,
                recipient.email,
                {
                    **data,
                    "firstname": recipient.first_name,
                    "subject": f"ProAce: {notification.verb.capitalize()}",
                    "title": notification.verb.capitalize(),
                    "message": notification.description or notification.verb.capitalize(),
                },
                recipient=recipient,
                notification=notification,
            )
        else:
            queue_email_delivery(
                recipient.email,
                f"Proace: {notification.verb.capitalize()}",
                notification.description or notification.verb.capitalize(),
                notification=notification,
                recipient=recipient,
            )
    if (
        getattr(settings, "FCM_ENABLED", False)
        and data.get("push") is not False
        and POLICIES.get(data.get("event", ""), ChannelPolicy()).push
        and PushDevice.objects.filter(user=recipient).exists()
    ):
        _queue_push_notification(notification)


@transaction.atomic
def create_notification(
    recipient: User,
    verb: str,
    actor: models.Model | None = None,
    target: models.Model | None = None,
    action_object: models.Model | None = None,
    description: str = "",
    level: str = "info",
    data: dict[str, Any] | None = None,
    public: bool = True,
    event_key: str | None = None,
) -> Notification:
    actor = actor or recipient
    payload = dict(data or {})
    category = category_for(payload, verb, target._meta.model_name if target else "")
    payload["category"] = category
    supplied_url = payload.get("url")
    if not isinstance(supplied_url, str) or not supplied_url.startswith("/") or supplied_url.startswith("//"):
        payload["url"] = destination_for(recipient, category, payload)
    identity = event_key or payload.pop("event_key", None)
    if not identity and payload.get("event"):
        object_ids = {key: value for key, value in payload.items() if key.endswith("_id")}
        if target or object_ids:
            identity = json.dumps({
                "event": payload["event"], "ids": object_ids,
                "target": [target._meta.label, target.pk] if target else None,
                "revision": str(getattr(target, "updated", "")),
                "status": payload.get("status"), "verb": verb,
            }, sort_keys=True, default=str)
    key = hashlib.sha256(str(identity).encode()).hexdigest() if identity else None
    defaults = dict(
        actor_content_type=_content_type_for(actor),
        actor_object_id=str(actor.pk), verb=verb, description=description,
        target_content_type=_content_type_for(target),
        target_object_id=str(target.pk) if target else None,
        action_object_content_type=_content_type_for(action_object),
        action_object_object_id=str(action_object.pk) if action_object else None,
        level=level, data=payload, public=public, category=category,
    )
    if key:
        notification, created = Notification.objects.get_or_create(
            recipient=recipient, event_key=key, defaults=defaults,
        )
        if not created:
            return notification
    else:
        notification = Notification.objects.create(recipient=recipient, **defaults)
    ids = store_ids_for(payload, target) | store_ids_for({}, action_object)
    stores = Store.objects.filter(pk__in=ids)
    order = target if target and target._meta.model_name == "order" else getattr(target, "order", None)
    if order is not None and order.user_id != recipient.pk and not (recipient.is_superuser or recipient.is_business_admin):
        scope = models.Q(user=recipient)
        if recipient.is_staff:
            scope |= models.Q(assigned_staff=recipient) | models.Q(is_official=True)
        stores = stores.filter(scope)
    notification.stores.set(stores.distinct())
    _send_external_notification(notification)
    from notification.search import schedule_index_notification
    schedule_index_notification(notification.pk)
    return notification


def _queue_push_notification(notification):
    from notification.delivery import queue_push_delivery

    queue_push_delivery(notification)


def notify_users(recipients, verb, actor=None, target=None, action_object=None,
                 description="", level="info", data=None, public=True):
    notifications = []
    with transaction.atomic():
        for recipient in recipients:
            notifications.append(create_notification(
                recipient=recipient,
                verb=verb,
                actor=actor,
                target=target,
                action_object=action_object,
                description=description,
                level=level,
                data=data,
                public=public,
            ))
    return notifications


def notify_staff(verb, actor=None, target=None, action_object=None,
                 description="", level="info", data=None):
    staff = User.objects.filter(models.Q(is_staff=True) | models.Q(is_superuser=True) | models.Q(is_business_admin=True), is_active=True)
    return notify_users(
        staff,
        verb=verb,
        actor=actor,
        target=target,
        action_object=action_object,
        description=description,
        level=level,
        data=data,
    )


def refund_requested_nofication(actor=None, refund=None, order=None):
    return notify_staff(
        "refund requested",
        actor=actor,
        target=refund or order,
        action_object=order,
        description="A customer requested a refund.",
        level="warning",
        data={"event": "refund_requested"},
    )


def staff_created_nofication(staff_user, actor=None):
    return notify_staff(
        "staff account created",
        actor=actor,
        target=staff_user,
        description=f"{staff_user.email} was added as staff.",
        level="info",
        data={"event": "staff_created", "staff_id": staff_user.pk},
    )


def store_withdrawed_cash_nofication(store, amount=None, actor=None):
    staff_notifications = notify_staff(
        "store withdrawal requested",
        actor=actor or store.user,
        target=store,
        description=f"{store.name} requested a withdrawal.",
        level="info",
        data={"event": "store_withdrawal_requested", "amount": str(amount) if amount is not None else None},
    )
    owner_notification = create_notification(
        recipient=store.user,
        actor=actor or store.user,
        target=store,
        verb="store withdrawal submitted",
        description=f"Your withdrawal request for {amount} is being reviewed." if amount is not None else "Your store withdrawal request is being reviewed.",
        level="info",
        data={"event": "store_withdrawal_requested", "amount": str(amount) if amount is not None else None},
    )
    return [*staff_notifications, owner_notification]


def store_moderation_notification(
    store: Store,
    actor: User | None = None,
    blocked: bool = True,
) -> Notification:
    verb = "store blocked" if blocked else "store unblocked"
    level = "warning" if blocked else "success"
    description = (
        f"{store.name} has been blocked. Reason: {store.blocked_reason or 'Contact support for details.'}"
        if blocked else f"{store.name} has been unblocked."
    )
    return create_notification(
        recipient=store.user,
        actor=actor or store.user,
        target=store,
        verb=verb,
        description=description,
        level=level,
        data={"event": "store_blocked" if blocked else "store_unblocked", "store_id": store.pk},
    )


def account_access_notification(
    user: User,
    previous_active: bool,
    previous_staff: bool,
) -> None:
    if (user.is_active, user.is_staff) == (previous_active, previous_staff):
        return
    messages: list[str] = []
    if user.is_active != previous_active:
        messages.append(
            "Your account access has been restored. You can sign in again."
            if user.is_active else
            "Your account access has been suspended. Contact support for details."
        )
    if user.is_staff != previous_staff:
        messages.append(
            "Backoffice access has been granted to your account."
            if user.is_staff else "Backoffice access has been removed from your account."
        )
    create_notification(
        recipient=user,
        verb="account access updated",
        description=" ".join(messages),
        data={"event": "account_access_changed"},
    )


def password_changed_notification(user: User) -> None:
    PushDevice.objects.filter(user=user).delete()
    create_notification(
        recipient=user,
        verb="password changed",
        description=(
            "Your ProAce password has been changed. If you did not make this change, "
            "reset your password immediately and contact support."
        ),
        data={"event": "password_changed"},
    )


def _filter_notifications_by_store(queryset: models.QuerySet, store_param: str | None) -> models.QuerySet:
    if not store_param or store_param == "all":
        return queryset
    stores = Store.objects.filter(pk=int(store_param)) if str(store_param).isdigit() else Store.objects.filter(
        models.Q(username__iexact=store_param) | models.Q(name__iexact=store_param)
    )
    return queryset.filter(stores__in=stores).distinct()


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination

    def get_queryset(self) -> models.QuerySet[Notification]:
        queryset = Notification.objects.filter(recipient=self.request.user).select_related(
            "recipient",
            "actor_content_type",
            "target_content_type",
            "action_object_content_type",
        )
        include_archived = self.request.query_params.get("include_archived") == "true"
        if not include_archived and self.action not in {
            "archived", "archive", "archive_alias", "retrieve", "destroy",
            "restore", "mark_read", "mark_unread", "mark_all_read",
            "mark_read_alias", "mark_unread_alias", "mark_all_read_alias"
        }:
            queryset = queryset.filter(deleted=False)

        state = self.request.query_params.get("state")
        if state == "unread":
            queryset = queryset.filter(unread=True)
        elif state == "read":
            queryset = queryset.filter(unread=False)
        elif state and state != "all":
            queryset = queryset.none()

        level = self.request.query_params.get("level")
        if level:
            queryset = queryset.filter(level=level)

        event = self.request.query_params.get("event")
        if event:
            queryset = queryset.filter(data__event=event)

        # Full-text-like search across verb, description, and level keywords
        search = (
            self.request.query_params.get("search")
            or self.request.query_params.get("q")
        )
        if search:
            search = search.strip()
            search_q = (
                models.Q(verb__icontains=search)
                | models.Q(description__icontains=search)
            )
            if search.lower() in ["success", "info", "warning", "error"]:
                search_q |= models.Q(level__iexact=search.lower())
            queryset = queryset.filter(search_q)

        category = self.request.query_params.get("category")
        if category and category != "all":
            queryset = queryset.filter(category=category)

        # Store filter: by store ID, username, or store name
        store_param = (
            self.request.query_params.get("store")
            or self.request.query_params.get("store_id")
        )
        queryset = _filter_notifications_by_store(queryset, store_param)

        return queryset.order_by("-timestamp", "-pk")

    @extend_schema(
        request=PushDeviceTokenSerializer,
        responses={status.HTTP_200_OK: OpenApiTypes.OBJECT},
    )
    @action(detail=False, methods=["post", "delete"], url_path="devices")
    def devices(self, request):
        if request.method == "POST" and not getattr(settings, "FCM_ENABLED", False):
            return Response(
                {"detail": "Browser push notifications are not enabled."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = PushDeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]
        if not token:
            return Response(
                {"token": ["This field may not be blank."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.method == "POST":
            PushDevice.objects.update_or_create(
                token=token,
                defaults={"user": request.user, "last_active_at": timezone.now()},
            )
            return Response({"registered": True}, status=status.HTTP_200_OK)

        removed, _ = PushDevice.objects.filter(user=request.user, token=token).delete()
        return Response({"unregistered": removed > 0})

    @action(detail=False, methods=["get"])
    def unread(self, request):
        queryset = self.get_queryset().filter(unread=True, deleted=False)
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=False, methods=["get"])
    @extend_schema(parameters=[ListingQuerySerializer], responses=NotificationSerializer(many=True))
    def archived(self, request: Request) -> Response:
        queryset = self.get_queryset().filter(deleted=True)
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=False, methods=["get"], url_path="archive")
    def archive_alias(self, request):
        return self.archived(request)

    @action(detail=False, methods=["get"])
    def counts(self, request):
        notifications = Notification.objects.filter(recipient=request.user)
        store_param = request.query_params.get("store") or request.query_params.get("store_id")
        if store_param:
            notifications = _filter_notifications_by_store(notifications, store_param)
        counts = {
            "unread": notifications.filter(unread=True, deleted=False).count(),
            "read": notifications.filter(unread=False, deleted=False).count(),
            "archived": notifications.filter(deleted=True).count(),
            "total": notifications.count(),
        }
        return Response(NotificationCountSerializer(counts).data)

    @action(detail=False, methods=["get"], url_path="filters")
    def filters(self, request: Request) -> Response:
        user_notifications = Notification.objects.filter(recipient=request.user)
        active_notifications = user_notifications.filter(deleted=False)

        owned_stores = list(
            Store.objects.filter(inbox_notifications__recipient=request.user)
            .distinct().order_by("name").values("id", "name", "username", "is_official")
        )
        categories = [{"id": "all", "label": "All Categories", "count": active_notifications.count()}]
        categories.extend(
            {"id": key, "label": label, "count": active_notifications.filter(category=key).count()}
            for key, label in CATEGORIES.items()
        )

        return Response({
            "categories": categories,
            "stores": owned_stores,
            "counts": {
                "unread": active_notifications.filter(unread=True).count(),
                "read": active_notifications.filter(unread=False).count(),
                "archived": user_notifications.filter(deleted=True).count(),
                "total": user_notifications.count(),
            }
        })

    @extend_schema(parameters=[ListingQuerySerializer], responses=NotificationSerializer(many=True))
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # The durable inbox is authoritative, including newly committed events.
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_as_read()
        from notification.search import schedule_index_notification
        schedule_index_notification(notification.pk)
        return Response(self.get_serializer(notification).data)

    @action(detail=True, methods=["post"], url_path="mark_read")
    def mark_read_alias(self, request, pk=None):
        return self.mark_read(request, pk=pk)

    @action(detail=True, methods=["post"], url_path="mark-unread")
    def mark_unread(self, request, pk=None):
        notification = self.get_object()
        notification.mark_as_unread()
        from notification.search import schedule_index_notification
        schedule_index_notification(notification.pk)
        return Response(self.get_serializer(notification).data)

    @action(detail=True, methods=["post"], url_path="mark_unread")
    def mark_unread_alias(self, request, pk=None):
        return self.mark_unread(request, pk=pk)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        queryset = Notification.objects.filter(
            recipient=request.user,
            unread=True,
            deleted=False,
        )
        store_param = request.query_params.get("store") or request.query_params.get("store_id")
        if store_param:
            queryset = _filter_notifications_by_store(queryset, store_param)
        now = timezone.now()
        updated = queryset.update(unread=False, read_at=now, updated_at=now)
        from notification.realtime import publish
        publish(request.user.pk, {'event': 'notification.changed'})
        return Response({"updated": updated})

    @action(detail=False, methods=["post"], url_path="mark_all_read")
    def mark_all_read_alias(self, request):
        return self.mark_all_read(request)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        notification = self.get_object()
        notification.deleted = True
        notification.save(update_fields=["deleted"])
        from notification.search import schedule_index_notification
        schedule_index_notification(notification.pk)
        return Response(self.get_serializer(notification).data)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.deleted = False
        notification.save(update_fields=["deleted"])
        from notification.search import schedule_index_notification
        schedule_index_notification(notification.pk)
        return Response(self.get_serializer(notification).data)

    def destroy(self, request, *args, **kwargs):
        notification = self.get_object()
        pk = notification.pk
        notification.delete()
        from notification.search import schedule_delete_notification
        schedule_delete_notification(pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
