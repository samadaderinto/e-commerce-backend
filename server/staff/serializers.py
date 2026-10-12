"""Canonical serializers module for the staff application."""
from decimal import Decimal
from utils.timezones import TimeZoneField
from django.utils import timezone
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from core.models import User
from core.serializers import UserSerializer
from payment.models import Coupon, CouponRedemption, Order
from payment.serializers import CouponSerializer, OrdersSerializer
from product.models import Product
from staff.models import Post, Content, Comment
from store.models import Store
from store.serializers import StoreSerializer
from taggit.serializers import TagListSerializerField, TaggitSerializer


class TreasuryWithdrawalSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    payout_method = serializers.ChoiceField(choices=['stripe', 'bank'], default='stripe')
    account_details = serializers.DictField(required=False, default=dict)


class PostSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField()

    class Meta:
        model = Post
        fields = [
            "id",
            "staff",
            "title",
            "tags",
            "created",
            "updated",
        ]


class ContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Content
        fields = [
            "id",
            "blog_id",
            "content",
        ]


class CommentSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.username")

    class Meta:
        model = Comment
        fields = ["id", "body", "owner", "post"]


class BackofficeStoreSerializer(StoreSerializer):
    owner_email = serializers.EmailField(source="user.email", read_only=True)
    owner_name = serializers.SerializerMethodField()

    class Meta(StoreSerializer.Meta):
        fields = StoreSerializer.Meta.fields + ["owner_email", "owner_name"]

    def get_owner_name(self, store):
        return f"{store.user.first_name} {store.user.last_name}".strip()


class StoreModerationSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=1000)

    def block(self, store, staff_user):
        if store.is_official:
            raise serializers.ValidationError({"detail": "Official company stores cannot be blocked."})
        store.status = Store.STATUS_BLOCKED
        store.blocked_reason = self.validated_data.get("reason", "")
        store.blocked_at = timezone.now()
        store.blocked_by = staff_user
        store.save(update_fields=["status", "blocked_reason", "blocked_at", "blocked_by", "updated"])
        return store

    def unblock(self, store):
        store.status = Store.STATUS_ACTIVE
        store.blocked_reason = ""
        store.blocked_at = None
        store.blocked_by = None
        store.save(update_fields=["status", "blocked_reason", "blocked_at", "blocked_by", "updated"])
        return store


class StaffUserSerializer(UserSerializer):
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
            "is_superuser",
            "is_business_admin",
            "must_change_password",
            "role",
            "is_active",
            "staff_email_verified",
            "staff_blocked_at",
            "date_joined",
            "updated",
            "last_login",
            "last_active_at",
        ]
        read_only_fields = fields


class StaffCreateSerializer(serializers.ModelSerializer):
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
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["id", "is_staff", "is_active", "date_joined"]

    def validate(self, attrs):
        if "password" in self.initial_data:
            raise serializers.ValidationError({"password": "Passwords are generated privately by the server."})
        return attrs

    def create(self, validated_data):
        from core.onboarding import invite_staff
        return invite_staff(validated_data)


class StaffPermissionSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide is_active or is_staff.")
        return attrs

    def update(self, user: User) -> User:
        previous_active, previous_staff = user.is_active, user.is_staff
        if user.is_superuser or user.is_business_admin:
            raise serializers.ValidationError("Administrator accounts cannot be changed by peers.")
        if self.validated_data.get("is_active") and user.is_staff and not user.staff_email_verified:
            raise serializers.ValidationError("Staff mailbox verification is required.")
        if "is_active" in self.validated_data:
            user.is_active = self.validated_data["is_active"]
        if "is_staff" in self.validated_data:
            user.is_staff = self.validated_data["is_staff"]
        user.credential_version += 1
        user.save(update_fields=["is_active", "is_staff", "credential_version"])
        from notification.views import account_access_notification

        account_access_notification(user, previous_active, previous_staff)
        return user


class BackofficeOrderSerializer(OrdersSerializer):
    buyer_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta(OrdersSerializer.Meta):
        fields = ["id", *OrdersSerializer.Meta.fields, "buyer_email"]


class CouponRedemptionSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    order_id = serializers.CharField(source="order.orderId", read_only=True)

    class Meta:
        model = CouponRedemption
        fields = ["id", "user_email", "order_id", "created"]


class BackofficeCouponSerializer(CouponSerializer):
    created_by = serializers.SerializerMethodField()
    redemptions = CouponRedemptionSerializer(many=True, read_only=True)

    class Meta(CouponSerializer.Meta):
        model = Coupon
        fields = [*CouponSerializer.Meta.fields, "created_by", "redemptions"]

    def get_created_by(self, obj: Coupon) -> str:
        return obj.created_by.email if obj.created_by else ""


class CouponUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ["valid_to", "discount", "num_available", "active"]

    def validate_num_available(self, value):
        if self.instance and value < self.instance.num_used:
            raise serializers.ValidationError("Availability cannot be lower than the number already used.")
        return value

    def validate(self, attrs):
        active = attrs.get("active", getattr(self.instance, "active", True))
        num_avail = attrs.get("num_available", getattr(self.instance, "num_available", 0))
        num_used = getattr(self.instance, "num_used", 0)
        if active and num_avail <= num_used:
            raise serializers.ValidationError({"active": "Cannot activate a coupon that has exhausted all available redemptions."})
        valid_to = attrs.get("valid_to")
        if valid_to and self.instance and self.instance.valid_from and valid_to <= self.instance.valid_from:
            raise serializers.ValidationError({"valid_to": "Expiration date must be after creation date."})
        return attrs


class OrderStatusOverrideSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[
        "pending", "confirmed", "shipped", "delivered", "picked up", "cancelled",
    ])
    reason = serializers.CharField(required=False, allow_blank=True, max_length=1000, default="Confirmed by backoffice operator")

    def validate_status(self, value):
        if value == "refunded":
            raise serializers.ValidationError("Use the refund workflow to refund an order.")
        return value


class DashboardQuerySerializer(serializers.Serializer):
    time_zone = TimeZoneField(default="UTC", max_length=100)
    days = serializers.IntegerField(default=30, min_value=1, max_value=365)


class StoreAuditProductSerializer(serializers.ModelSerializer):
    price = serializers.CharField()
    has_digital_asset = serializers.SerializerMethodField()
    available = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "title", "category", "price", "visibility",
            "is_digital", "has_digital_asset", "available", "created", "updated",
            "product_type", "affiliate_hoplink", "affiliate_vendor_nickname", "affiliate_button_text",
        ]

    def get_has_digital_asset(self, obj) -> bool:
        return bool(obj.digital_file_url)

    def get_available(self, obj):
        if obj.is_digital:
            return None
        return obj.available


class StaffWalletTransactionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.CharField()
    source = serializers.CharField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    description = serializers.CharField(allow_blank=True)
    created = serializers.DateTimeField()


class StaffCustomerWalletSerializer(serializers.Serializer):
    count = serializers.IntegerField()
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
    order_count = serializers.IntegerField()
    total_orders = serializers.IntegerField()
    lifetime_spent = serializers.DecimalField(max_digits=15, decimal_places=2)
    activity = StaffUserActivitySerializer(many=True)
    referral = serializers.DictField(required=False, allow_null=True)
    affiliate = serializers.DictField(required=False, allow_null=True)


class StaffUserOrderQuerySerializer(serializers.Serializer):
    order_search = serializers.CharField(required=False, allow_blank=True, default="")
    order_status = serializers.ChoiceField(choices=["", *dict(Order.ORDER_STATUS_CHOICE)], default="")
    order_carrier = serializers.ChoiceField(choices=["", "USPS", "UPS", "FEDEX", "DHL", "DIGITAL"], default="")
    order_payment = serializers.ChoiceField(choices=["", "card", "wallet", "cash_on_delivery", "stripe_wallet"], default="")
    order_ordering = serializers.ChoiceField(choices=["-created", "created", "-total", "total"], default="-created")
    order_offset = serializers.IntegerField(min_value=0, default=0)
