from rest_framework import serializers
from affiliates.models import Marketer, Url, Redirect


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
    class Meta:
        model = Url
        fields = [
            "user",
            "marketer",
            "product",
            "identifier",
            "active",
            "created",
            "updated",
        ]


class RedirectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Url
        fields = [
            "url",
            "product_url",
            "refferal_url",
            "click_rate",
            "created",
        ]
        
        
        def create(self,validated_data):
            redirect = Redirect.objects.create_user(**validated_data)
            redirect.click_rate += 1
            redirect.save()

            return redirect
