from rest_framework import serializers

from notification.models import Notification


class GenericNotificationRelatedField(serializers.RelatedField):
    def to_representation(self, value):
        if value is None:
            return None
        return {
            "id": getattr(value, "pk", None),
            "type": value.__class__.__name__,
            "label": str(value),
        }


class NotificationSerializer(serializers.ModelSerializer):
    data = serializers.SerializerMethodField()
    actor = GenericNotificationRelatedField(read_only=True)
    target = GenericNotificationRelatedField(read_only=True)
    action_object = GenericNotificationRelatedField(read_only=True)
    recipient_email = serializers.EmailField(source="recipient.email", read_only=True)
    category = serializers.SerializerMethodField()
    store = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "level",
            "unread",
            "recipient_email",
            "actor",
            "verb",
            "description",
            "target",
            "action_object",
            "public",
            "deleted",
            "emailed",
            "data",
            "timestamp",
            "read_at",
            "updated_at",
            "category",
            "store",
        ]
        read_only_fields = fields

    def get_data(self, obj: Notification) -> dict[str, object]:
        from notification.policy import notification_payload

        return notification_payload(obj)

    def get_category(self, obj: Notification) -> str:
        return obj.category

    def get_store(self, obj: Notification) -> dict[str, object] | None:
        store = obj.stores.order_by("pk").first()
        if store is None:
            return None
        return {"id": store.pk, "name": store.name, "username": store.username}


class NotificationCountSerializer(serializers.Serializer):
    unread = serializers.IntegerField()
    read = serializers.IntegerField()
    archived = serializers.IntegerField()
    total = serializers.IntegerField()


class PushDeviceTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=4096, trim_whitespace=True)


class PushDeviceStatusSerializer(serializers.Serializer):
    registered = serializers.BooleanField()
    has_devices = serializers.BooleanField()
    device_count = serializers.IntegerField()
    fcm_enabled = serializers.BooleanField(default=False)
