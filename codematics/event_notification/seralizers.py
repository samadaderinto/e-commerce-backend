from rest_framework import serializers



class GenericNotificationRelatedField(serializers.RelatedField):

    # def to_representation(self, value):
    #     if isinstance(value, Foo):
    #         serializer = FooSerializer(value)
    #     if isinstance(value, Bar):
    #         serializer = BarSerializer(value)

        # return serializer.data
        pass


class NotificationSerializer(serializers.Serializer):
    # recipient = PublicUserSerializer(User, read_only=True)
    unread = serializers.BooleanField(read_only=True)
    target = GenericNotificationRelatedField(read_only=True)