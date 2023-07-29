
from store.models import Schedule, Store, StoreImg

from rest_framework import serializers




class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["id",
                  "user",
                  "username",
                  "name",
                  "created",
                  "updated"]


class StoreInfoForProductCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["url",
                  "name"]



class StoreImgSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreImg
        field = ["id", "title", "storeId", "url"]


class ScheduleSerializer(serializers.ModelSerializer):

    class Meta:
        model = Schedule
        fields = ['__all__']
