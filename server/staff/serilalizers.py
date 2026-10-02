from django.utils import timezone
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from core.models import User
from core.serializers import UserSerializer
from payment.models import Coupon, Order
from payment.serializers import CouponSerializer, OrdersSerializer
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
            "is_active",
            "date_joined",
        ]
        read_only_fields = fields


class StaffCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

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
            "password",
            "is_staff",
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["id", "is_staff", "is_active", "date_joined"]

    def create(self, validated_data):
        return User.objects.create_staffuser(**validated_data)


class StaffPermissionSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide is_active or is_staff.")
        return attrs

    def update(self, user):
        if "is_active" in self.validated_data:
            user.is_active = self.validated_data["is_active"]
        if "is_staff" in self.validated_data:
            user.is_staff = self.validated_data["is_staff"]
        user.save(update_fields=["is_active", "is_staff"])
        return user


class BackofficeOrderSerializer(OrdersSerializer):
    buyer_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta(OrdersSerializer.Meta):
        fields = OrdersSerializer.Meta.fields + ["buyer_email"]


class BackofficeCouponSerializer(CouponSerializer):
    class Meta(CouponSerializer.Meta):
        model = Coupon


class DashboardQuerySerializer(serializers.Serializer):
    days = serializers.IntegerField(default=30, min_value=1, max_value=365)
