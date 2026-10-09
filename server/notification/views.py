from typing import Any

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
    if getattr(recipient, "email", None) and data.get("email") is not False:
        from notification.delivery import queue_email_delivery

        event = data.get("event", "")
        template = {
            "store_verified": "store-status",
            "store_blocked": "store-status",
            "store_unblocked": "store-status",
            "account_access_changed": "account-security",
            "password_changed": "account-security",
            "inventory_low": "inventory-low",
        }.get(event)
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
) -> Notification:
    actor = actor or recipient
    notification = Notification.objects.create(
        recipient=recipient,
        actor_content_type=_content_type_for(actor),
        actor_object_id=str(actor.pk),
        verb=verb,
        description=description,
        target_content_type=_content_type_for(target),
        target_object_id=str(target.pk) if target is not None else None,
        action_object_content_type=_content_type_for(action_object),
        action_object_object_id=str(action_object.pk) if action_object is not None else None,
        level=level,
        data=data or {},
        public=public,
    )
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
    create_notification(
        recipient=user,
        verb="password changed",
        description=(
            "Your ProAce password has been changed. If you did not make this change, "
            "reset your password immediately and contact support."
        ),
        data={"event": "password_changed"},
    )


def _filter_notifications_by_store(queryset, store_param):
    if not store_param or store_param == "all":
        return queryset
    store_param = str(store_param).strip()
    from store.models import Store
    store_ct = ContentType.objects.get_for_model(Store)
    store_obj = None
    if store_param.isdigit():
        target_store_id = int(store_param)
        store_obj = Store.objects.filter(pk=target_store_id).first()
    else:
        store_obj = Store.objects.filter(
            models.Q(username__iexact=store_param) | models.Q(name__iexact=store_param)
        ).first()
        target_store_id = store_obj.pk if store_obj else None

    if target_store_id is not None:
        store_q = (
            models.Q(target_content_type=store_ct, target_object_id=str(target_store_id))
            | models.Q(action_object_content_type=store_ct, action_object_object_id=str(target_store_id))
            | models.Q(data__store_id=target_store_id)
            | models.Q(data__store_id=str(target_store_id))
            | models.Q(data__store=target_store_id)
            | models.Q(data__store=str(target_store_id))
        )
        if store_obj:
            store_q |= models.Q(verb__icontains=store_obj.name) | models.Q(description__icontains=store_obj.name)
        return queryset.filter(store_q)
    else:
        return queryset.filter(
            models.Q(verb__icontains=store_param) | models.Q(description__icontains=store_param)
        )


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
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

        # Category filter: store, affiliates, order, refund, payout, general
        category = self.request.query_params.get("category")
        if category and category != "all":
            category = category.lower().strip()
            if category == "store":
                queryset = queryset.filter(
                    models.Q(data__category="store")
                    | models.Q(data__event__icontains="store")
                    | models.Q(verb__icontains="store")
                    | models.Q(target_content_type__model="store")
                    | models.Q(action_object_content_type__model="store")
                )
            elif category == "affiliates":
                queryset = queryset.filter(
                    models.Q(data__category="affiliates")
                    | models.Q(data__event__icontains="referral")
                    | models.Q(data__event__icontains="affiliate")
                    | models.Q(verb__icontains="referral")
                    | models.Q(verb__icontains="affiliate")
                )
            elif category == "order":
                queryset = queryset.filter(
                    models.Q(data__category="order")
                    | models.Q(data__event__icontains="order")
                    | models.Q(verb__icontains="order")
                    | models.Q(target_content_type__model="order")
                    | models.Q(action_object_content_type__model="order")
                )
            elif category == "refund":
                queryset = queryset.filter(
                    models.Q(data__category="refund")
                    | models.Q(data__event__icontains="refund")
                    | models.Q(verb__icontains="refund")
                    | models.Q(target_content_type__model="refund")
                    | models.Q(action_object_content_type__model="refund")
                )
            elif category == "payout":
                queryset = queryset.filter(
                    models.Q(data__category="payout")
                    | models.Q(data__event__icontains="payout")
                    | models.Q(data__event__icontains="withdrawal")
                    | models.Q(verb__icontains="payout")
                    | models.Q(verb__icontains="withdrawal")
                    | models.Q(target_content_type__model="storepayout")
                )
            elif category == "general":
                queryset = queryset.exclude(
                    models.Q(data__category__in=["store", "affiliates", "order", "refund", "payout"])
                    | models.Q(data__event__icontains="store")
                    | models.Q(data__event__icontains="referral")
                    | models.Q(data__event__icontains="affiliate")
                    | models.Q(data__event__icontains="order")
                    | models.Q(data__event__icontains="refund")
                    | models.Q(data__event__icontains="payout")
                    | models.Q(data__event__icontains="withdrawal")
                    | models.Q(verb__icontains="store")
                    | models.Q(verb__icontains="referral")
                    | models.Q(verb__icontains="affiliate")
                    | models.Q(verb__icontains="order")
                    | models.Q(verb__icontains="refund")
                    | models.Q(verb__icontains="payout")
                    | models.Q(verb__icontains="withdrawal")
                    | models.Q(target_content_type__model__in=["store", "order", "refund", "storepayout"])
                )

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
    def archived(self, request):
        queryset = Notification.objects.filter(recipient=request.user, deleted=True).order_by("-timestamp", "-pk")
        store_param = request.query_params.get("store") or request.query_params.get("store_id")
        queryset = _filter_notifications_by_store(queryset, store_param)
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
    def filters(self, request):
        user_notifications = Notification.objects.filter(recipient=request.user)
        active_notifications = user_notifications.filter(deleted=False)

        from store.models import Store
        store_ct = ContentType.objects.get_for_model(Store)

        if request.user.is_superuser or getattr(request.user, "is_business_admin", False) or request.user.is_staff:
            # Super Admin & Staff notification filtering:
            # The notification popup dropdown/list displays only app-owned stores (Proace official stores).
            # Third-party/independent stores should not appear in this specific notification list.
            official_stores = list(
                Store.objects.filter(is_official=True).order_by("name").values("id", "name", "username")
            )
            for s in official_stores:
                s["is_official"] = True
            owned_stores = official_stores
        else:
            owned_stores = list(
                Store.objects.filter(user=request.user, is_official=False).order_by("name").values("id", "name", "username")
            )
            for s in owned_stores:
                s["is_official"] = False

        categories = [
            {"id": "all", "label": "All Categories", "count": active_notifications.count()},
            {"id": "store", "label": "Store", "count": active_notifications.filter(
                models.Q(data__category="store") | models.Q(data__event__icontains="store") | models.Q(verb__icontains="store") | models.Q(target_content_type__model="store") | models.Q(action_object_content_type__model="store")
            ).count()},
            {"id": "affiliates", "label": "Affiliates & Referrals", "count": active_notifications.filter(
                models.Q(data__category="affiliates") | models.Q(data__event__icontains="referral") | models.Q(data__event__icontains="affiliate") | models.Q(verb__icontains="referral") | models.Q(verb__icontains="affiliate")
            ).count()},
            {"id": "order", "label": "Orders", "count": active_notifications.filter(
                models.Q(data__category="order") | models.Q(data__event__icontains="order") | models.Q(verb__icontains="order") | models.Q(target_content_type__model="order") | models.Q(action_object_content_type__model="order")
            ).count()},
            {"id": "refund", "label": "Refunds", "count": active_notifications.filter(
                models.Q(data__category="refund") | models.Q(data__event__icontains="refund") | models.Q(verb__icontains="refund") | models.Q(target_content_type__model="refund") | models.Q(action_object_content_type__model="refund")
            ).count()},
            {"id": "payout", "label": "Payouts & Wallet", "count": active_notifications.filter(
                models.Q(data__category="payout") | models.Q(data__event__icontains="payout") | models.Q(data__event__icontains="withdrawal") | models.Q(verb__icontains="payout") | models.Q(verb__icontains="withdrawal") | models.Q(target_content_type__model="storepayout")
            ).count()},
        ]

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

    def list(self, request, *args, **kwargs):
        search = request.query_params.get("search") or request.query_params.get("q")
        if search:
            search = search.strip()
            from notification.search import enabled as es_enabled, search_notification_ids

            if es_enabled():
                store_val = request.query_params.get("store") or request.query_params.get("store_id")
                category_val = request.query_params.get("category")
                include_archived = request.query_params.get("include_archived") == "true"
                state_val = request.query_params.get("state")
                level_val = request.query_params.get("level")

                limit = int(request.query_params.get("limit", 20))
                offset = int(request.query_params.get("offset", 0))

                filters = {
                    "include_archived": include_archived,
                    "state": state_val,
                    "category": category_val,
                    "level": level_val,
                }
                if store_val and str(store_val).isdigit():
                    filters["store_id"] = int(store_val)

                es_results = search_notification_ids(
                    query=search,
                    recipient_id=request.user.id,
                    filters=filters,
                    offset=offset,
                    limit=limit,
                )
                if es_results is not None:
                    ids = es_results["ids"]
                    count = es_results["count"]
                    notifs = Notification.objects.filter(pk__in=ids).select_related(
                        "recipient",
                        "actor_content_type",
                        "target_content_type",
                        "action_object_content_type",
                    ).in_bulk(ids)
                    ordered = [notifs[pk] for pk in ids if pk in notifs]
                    serializer = self.get_serializer(ordered, many=True)
                    return Response({
                        "count": count,
                        "results": serializer.data,
                        "next": None,
                        "previous": None,
                    })
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
