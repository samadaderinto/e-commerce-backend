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
    actor = GenericNotificationRelatedField(read_only=True)
    target = GenericNotificationRelatedField(read_only=True)
    action_object = GenericNotificationRelatedField(read_only=True)
    recipient_email = serializers.EmailField(source="recipient.email", read_only=True)

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
        ]
        read_only_fields = fields


class NotificationCountSerializer(serializers.Serializer):
    unread = serializers.IntegerField()
    read = serializers.IntegerField()
    archived = serializers.IntegerField()
    total = serializers.IntegerField()
