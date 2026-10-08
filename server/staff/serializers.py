"""Canonical serializers module for the staff application."""
from staff.serilalizers import *  # noqa: F401, F403

from rest_framework import serializers


class StaffWalletTransactionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.CharField()
    source = serializers.CharField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    description = serializers.CharField(allow_blank=True)
    created = serializers.DateTimeField()


class StaffCustomerWalletSerializer(serializers.Serializer):
    balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    transactions = StaffWalletTransactionSerializer(many=True)


class StaffUserOrderSerializer(serializers.Serializer):
    updated = serializers.DateTimeField()
    id = serializers.IntegerField()
    reference = serializers.CharField()
    created = serializers.DateTimeField()
    status = serializers.CharField()
    total = serializers.DecimalField(max_digits=15, decimal_places=2)


class StaffUserActivitySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    verb = serializers.CharField()
    description = serializers.CharField(allow_blank=True, allow_null=True)
    created = serializers.DateTimeField()
    level = serializers.CharField()


class StaffUserDetailSerializer(serializers.Serializer):
    user = StaffUserSerializer()
    wallet = StaffCustomerWalletSerializer()
    orders = StaffUserOrderSerializer(many=True)
    activity = StaffUserActivitySerializer(many=True)
