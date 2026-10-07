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
            "category",
            "store",
        ]
        read_only_fields = fields

    def get_category(self, obj):
        data = obj.data or {}
        if data.get("category"):
            return str(data["category"]).lower()
        event = str(data.get("event") or "").lower()
        verb = (obj.verb or "").lower()
        target_model = (
            obj.target_content_type.model if obj.target_content_type else ""
        ).lower()

        if (
            "referral" in event
            or "affiliate" in event
            or "referral" in verb
            or "affiliate" in verb
        ):
            return "affiliates"
        if "refund" in event or "refund" in verb or target_model == "refund":
            return "refund"
        if (
            "payout" in event
            or "payout" in verb
            or "withdrawal" in event
            or "withdrawal" in verb
            or target_model == "storepayout"
        ):
            return "payout"
        if "store" in event or "store" in verb or target_model == "store":
            return "store"
        if "order" in event or "order" in verb or target_model == "order":
            return "order"
        return "general"

    def get_store(self, obj):
        data = obj.data or {}
        # 1. Check data store_id or store
        store_id = data.get("store_id") or data.get("store")
        if store_id:
            try:
                from store.models import Store

                store = Store.objects.filter(pk=store_id).first()
                if store:
                    return {
                        "id": store.id,
                        "name": store.name,
                        "username": store.username,
                    }
            except Exception:
                pass

        # 2. Check target content type
        if obj.target_content_type and obj.target_content_type.model == "store":
            try:
                from store.models import Store

                store = Store.objects.filter(pk=obj.target_object_id).first()
                if store:
                    return {
                        "id": store.id,
                        "name": store.name,
                        "username": store.username,
                    }
            except Exception:
                pass

        # 3. Check action_object content type
        if (
            obj.action_object_content_type
            and obj.action_object_content_type.model == "store"
        ):
            try:
                from store.models import Store

                store = Store.objects.filter(
                    pk=obj.action_object_object_id
                ).first()
                if store:
                    return {
                        "id": store.id,
                        "name": store.name,
                        "username": store.username,
                    }
            except Exception:
                pass

        return None


class NotificationCountSerializer(serializers.Serializer):
    unread = serializers.IntegerField()
    read = serializers.IntegerField()
    archived = serializers.IntegerField()
    total = serializers.IntegerField()


class PushDeviceTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=4096, trim_whitespace=True)
