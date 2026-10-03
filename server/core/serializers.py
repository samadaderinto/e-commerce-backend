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
            "created",
            "updated",
        ]

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
            "is_staff",
            "password",
            "created",
            "updated",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
        }

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
            'created',
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
