from typing import Any

from rest_framework import serializers

from core.models import Refund, Review, User, UserWallet, UserWalletTransaction
from product.serializers import ProductCardSerializer
from store.models import Store


class UserWalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserWalletTransaction
        fields = [
            "id",
            "transaction_type",
            "amount",
            "source",
            "description",
            "reference",
            "created",
        ]


class UserWalletSerializer(serializers.ModelSerializer):
    transactions = UserWalletTransactionSerializer(many=True, read_only=True)

    class Meta:
        model = UserWallet
        fields = [
            "id",
            "balance",
            "transactions",
            "created",
            "updated",
        ]


class UserSerializer(serializers.ModelSerializer):
    created = serializers.DateTimeField(source='date_joined', read_only=True)
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone1",
            "phone2",
            "gender",
            "avatar_url",
            "created",
            "updated",
            "last_login",
            "last_active_at",
        ]
        read_only_fields = ['created', 'updated', 'last_login', 'last_active_at', 'avatar_url']

    def to_representation(self, instance: User) -> dict[str, Any]:
        data = super().to_representation(instance)
        if getattr(instance, 'avatar_image', None):
            updated_str = instance.updated.strftime("%Y%m%d%H%M%S%f") if instance.updated else "0"
            data['avatar_url'] = f'/api/users/{instance.pk}/public/images/avatar?v={updated_str}'
        elif getattr(instance, 'avatar_url', None):
            data['avatar_url'] = instance.avatar_url
        else:
            data['avatar_url'] = None
        return data

class StaffSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone1",
            "phone2",
            "gender",
            "avatar_url",
            "is_staff",
            "password",
            "created",
            "updated",
        ]
        read_only_fields = ['avatar_url']
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def to_representation(self, instance: User) -> dict[str, Any]:
        data = super().to_representation(instance)
        if getattr(instance, 'avatar_image', None):
            updated_str = instance.updated.strftime("%Y%m%d%H%M%S%f") if instance.updated else "0"
            data['avatar_url'] = f'/api/users/{instance.pk}/public/images/avatar?v={updated_str}'
        elif getattr(instance, 'avatar_url', None):
            data['avatar_url'] = instance.avatar_url
        else:
            data['avatar_url'] = None
        return data

        def create(self, validated_data):
            user = User.objects.create_staffuser(**validated_data)
            user.set_password(self.password)
            user.save()
            return user



class AdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone1",
            "phone2",
            "gender",
            "is_staff",
            "is_superuser",
            "password",
            "created",
            "updated",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
        }

        def create(self, validated_data):
            user = User.objects.create_superuser(**validated_data)
            user.set_password(self.password)
            user.save()

            return user

        def update(self, instance, validated_data):

            password = validated_data.pop('password', None)

            for (key, value) in validated_data.items():
                setattr(instance, key, value)

            if password is not None:
                instance.set_password(password)

            instance.save()

            return instance


class RefundsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = [
            "id",
            "email",
            "order",
            "reason",
            "refund_type",
            "accepted",
            "status",
            "processed_by",
            "processed_at",
            "provider_reference",
            "failure_reason",
            "selected_items",
            "refund_amount",
            "processing_reason",
            'created',
        ]
        read_only_fields = [
            "accepted",
            "status",
            "processed_by",
            "processed_at",
            "provider_reference",
            "failure_reason",
            "refund_amount",
            "processing_reason",
            "created",
        ]


class UserMailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name"]


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["id", "user", "username", "name", "created"]


class ReviewsSerializer(serializers.ModelSerializer):
    name = UserMailSerializer(source="user", read_only=True)

    class Meta:
        model = Review
        fields = [
            "name",
            "product",
            "label",
            "comment",
            "rating",
            "created",
            "updated",
        ]

    extra_kwargs = {"user_details": {"read_only": True}}
