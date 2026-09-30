from rest_framework import serializers
from affiliates.models import (
    AffiliateWallet,
    AffiliateWalletTransaction,
    Marketer,
    Referral,
    Redirect,
    Url,
)


class MarketerSerializer(serializers.ModelSerializer):
    wallet_balance = serializers.DecimalField(
        source="user.affiliate_wallet.balance",
        max_digits=12,
        decimal_places=2,
        read_only=True,
        default="0.00",
    )

    class Meta:
        model = Marketer
        fields = [
            "id",
            "user",
            "marketer_id",
            "name",
            "wallet_balance",
            "created",
            "updated",
        ]
        read_only_fields = ["id", "user", "marketer_id", "wallet_balance", "created", "updated"]


class UrlSerializer(serializers.ModelSerializer):
    class Meta:
        model = Url
        fields = [
            "id",
            "marketer",
            "product",
            "identifier",
            "abs_url",
            "active",
            "created",
            "updated",
        ]
        read_only_fields = ["id", "abs_url", "created", "updated"]


class RedirectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Redirect
        fields = [
            "urlId",
            "product_url",
            "refferal_url",
            "click_rate",
            "created",
        ]

    def create(self, validated_data):
        redirect = Redirect.objects.create(**validated_data)
        redirect.click_rate += 1
        redirect.save(update_fields=["click_rate", "updated"])
        return redirect


class AffiliateWalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AffiliateWalletTransaction
        fields = ["id", "amount", "transaction_type", "reason", "metadata", "created"]


class AffiliateWalletSerializer(serializers.ModelSerializer):
    transactions = AffiliateWalletTransactionSerializer(many=True, read_only=True)

    class Meta:
        model = AffiliateWallet
        fields = ["id", "balance", "transactions", "created", "updated"]


class ReferralSerializer(serializers.ModelSerializer):
    referred_email = serializers.EmailField(source="referred_user.email", read_only=True)

    class Meta:
        model = Referral
        fields = [
            "id",
            "marketer",
            "referred_user",
            "referred_email",
            "reward_amount",
            "status",
            "created",
            "updated",
        ]
        read_only_fields = fields
