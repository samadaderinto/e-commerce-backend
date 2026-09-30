from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import User
from notification.models import Notification
from notification.seralizers import NotificationCountSerializer, NotificationSerializer


class NotificationPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100


def _content_type_for(obj):
    if obj is None:
        return None
    return ContentType.objects.get_for_model(obj, for_concrete_model=False)


def create_notification(recipient, verb, actor=None, target=None, action_object=None,
                        description="", level="info", data=None, public=True):
    actor = actor or recipient
    return Notification.objects.create(
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
    staff = User.objects.filter(is_staff=True, is_active=True)
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
    return notify_staff(
        "store withdrawal requested",
        actor=actor or store.user,
        target=store,
        description=f"{store.name} requested a withdrawal.",
        level="info",
        data={"event": "store_withdrawal_requested", "amount": str(amount) if amount is not None else None},
    )


def store_moderation_notification(store, actor=None, blocked=True):
    verb = "store blocked" if blocked else "store unblocked"
    level = "warning" if blocked else "success"
    description = (
        f"{store.name} has been blocked."
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
        if not include_archived and self.action != "archived":
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
            matching_ids = [
                notification.pk
                for notification in queryset
                if (notification.data or {}).get("event") == event
            ]
            queryset = Notification.objects.filter(pk__in=matching_ids)

        return queryset.order_by("-timestamp", "-pk")

    @action(detail=False, methods=["get"])
    def unread(self, request):
        queryset = self.get_queryset().filter(unread=True, deleted=False)
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=False, methods=["get"])
    def archived(self, request):
        queryset = Notification.objects.filter(recipient=request.user, deleted=True).order_by("-timestamp", "-pk")
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=False, methods=["get"])
    def counts(self, request):
        notifications = Notification.objects.filter(recipient=request.user)
        counts = {
            "unread": notifications.filter(unread=True, deleted=False).count(),
            "read": notifications.filter(unread=False, deleted=False).count(),
            "archived": notifications.filter(deleted=True).count(),
            "total": notifications.count(),
        }
        return Response(NotificationCountSerializer(counts).data)

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_as_read()
        return Response(self.get_serializer(notification).data)

    @action(detail=True, methods=["post"], url_path="mark-unread")
    def mark_unread(self, request, pk=None):
        notification = self.get_object()
        notification.mark_as_unread()
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        updated = Notification.objects.filter(
            recipient=request.user,
            unread=True,
            deleted=False,
        ).update(unread=False)
        return Response({"updated": updated})

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        notification = self.get_object()
        notification.deleted = True
        notification.save(update_fields=["deleted"])
        return Response(self.get_serializer(notification).data)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.deleted = False
        notification.save(update_fields=["deleted"])
        return Response(self.get_serializer(notification).data)

    def destroy(self, request, *args, **kwargs):
        notification = self.get_object()
        notification.deleted = True
        notification.save(update_fields=["deleted"])
        return Response(status=status.HTTP_204_NO_CONTENT)
