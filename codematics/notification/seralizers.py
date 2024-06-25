from core.models import User
from core.serializers import UserSerializer
from rest_framework import serializers



class GenericNotificationRelatedField(serializers.RelatedField):

    pass


class NotificationSerializer(serializers.Serializer):
    recipient = UserSerializer(User, read_only=True)
    unread = serializers.BooleanField(read_only=True)
    target = GenericNotificationRelatedField(read_only=True)