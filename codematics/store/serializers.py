
from store.models import Schedule, Store, StoreImg, StoreAddress

from rest_framework import serializers


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["id",
                  "user",
                  "username",
                  "name",
                  "created",
                  "updated",]


class StoreInfoForProductCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["url",
                  "name"]


class StoreImgSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreImg
        field = ["id", "title", "storeId", "url",]


class ScheduleSerializer(serializers.ModelSerializer):

    class Meta:
        model = Schedule
        fields = ["id", "store", "productId", "make_visible_at",]


class StoreAddressSerializer(serializers.ModelSerializer):

    class Meta:
        model = StoreAddress
        fields = ["id",
                  "store",
                  "address",
                  "zip",
                  "country",
                  "state",
                  "city",
                  "is_default",
                  "created",
                  "updated",]
