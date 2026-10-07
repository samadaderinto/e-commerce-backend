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
    owner = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = Comment
        fields = ['id', 'body', 'owner', 'post']        


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
            "is_staff",
            "is_superuser",
            "is_business_admin",
            "must_change_password",
            "role",
            "is_active",
            "staff_email_verified",
            "staff_blocked_at",
            "date_joined",
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

    def update(self, user):
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
    created_by = serializers.EmailField(source="created_by.email", read_only=True, default=None)
    redemptions = CouponRedemptionSerializer(many=True, read_only=True)

    class Meta(CouponSerializer.Meta):
        model = Coupon
        fields = [*CouponSerializer.Meta.fields, "created_by", "redemptions"]


class CouponUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ["valid_to", "discount", "num_available", "active"]

    def validate_num_available(self, value):
        if self.instance and value < self.instance.num_used:
            raise serializers.ValidationError("Availability cannot be lower than the number already used.")
        return value


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
    days = serializers.IntegerField(default=30, min_value=1, max_value=365)


class StoreAuditProductSerializer(serializers.ModelSerializer):
    price = serializers.CharField()
    has_digital_asset = serializers.SerializerMethodField()
    available = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "title", "category", "price", "visibility",
            "is_digital", "has_digital_asset", "available", "created",
        ]

    def get_has_digital_asset(self, obj) -> bool:
        return bool(obj.digital_file_url)

    def get_available(self, obj):
        return None if obj.is_digital else obj.available
