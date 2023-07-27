from rest_framework import serializers
from affiliates.models import Marketer, Url


class MarketerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marketer
        fields = [
            "id",
            "user",
            "marketer_id",
            "name",
            "created",
            "updated",
        ]


class UrlSerializer(serializers.ModelSerializer):
    url = ""
    class Meta:
        model = Url
        fields = [
            "user",
            "marketer",
            "product",
            "identifier",
            "abs_url",
            "active",
            "created",
            "updated",
        ]
