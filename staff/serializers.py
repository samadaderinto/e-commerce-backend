from rest_framework import serializers
from django import setup
setup()
from core.models import User
from payment.models import Coupon



class UserMailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["email"]



class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ["id",
                  'code',
                  "valid_from",
                  "valid_to",
                  "discount",
                  "num_available",
                  "num_used",
                  "active"]
