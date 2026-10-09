from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from core.models import Address, Review, User
from product.models import Product
from payment.models import Coupon
from product.policies import is_own_store
from store.models import Store, StoreInfo, StoreAddress
from store.services import calculate_store_tier
from store.serializers import StoreInfoSerializer
from utils.functions import normalize_media_url


class PublicStoreProfileSerializer(StoreInfoSerializer):
    pass


class PublicStoreAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreAddress
        fields = ['city', 'state', 'country']


class PublicStoreSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    seller_tier = serializers.SerializerMethodField()
    is_verified = serializers.SerializerMethodField()
    is_preview = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = [
            'id', 'username', 'name', 'status', 'is_official', 'seller_tier', 'created',
            'profile', 'address', 'product_count', 'is_verified', 'is_preview', 'updated', 'last_active_at'
        ]

    def get_profile(self, obj):
        info = StoreInfo.objects.filter(store=obj).first()
        return PublicStoreProfileSerializer(info, context=self.context).data if info else None

    def get_address(self, obj):
        addr = StoreAddress.objects.filter(store=obj, is_default=True).first()
        return PublicStoreAddressSerializer(addr).data if addr else None

    def get_product_count(self, obj):
        return Product.objects.filter(store=obj, visibility=True).count()

    def get_seller_tier(self, obj):
        return calculate_store_tier(obj)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_verified(self, obj):
        return bool(obj.status == Store.STATUS_ACTIVE and obj.verified_at)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_preview(self, obj):
        return bool(self.context.get('is_preview', not (obj.status == Store.STATUS_ACTIVE and obj.verified_at)))


def unit_price(product: Product, variant: str = '') -> Decimal:
    price = (product.price * Decimal(100 - product.discount) / 100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    if variant:
        from product.policies import selected_variant
        option = selected_variant(product, variant)
        price += Decimal(str(option.get('price_delta') or '0'))
    if price <= 0:
        raise serializers.ValidationError({'variant': 'The selected option has an invalid price.'})
    return price.quantize(Decimal('.01'))


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'phone1',
            'is_staff',
            'is_superuser',
            'is_business_admin',
            'must_change_password',
            'role',
            'date_joined',
            'updated',
            'last_login',
            'last_active_at',
        ]
        read_only_fields = [
            'id',
            'email',
            'is_staff',
            'is_superuser',
            'is_business_admin',
            'must_change_password',
            'role',
            'date_joined',
            'updated',
            'last_login',
            'last_active_at',
        ]


class RegisterSerializer(UserSerializer):
    password = serializers.CharField(write_only=True, min_length=8, max_length=128, trim_whitespace=False)
    referral_code = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ['password', 'referral_code']
        read_only_fields = [field for field in UserSerializer.Meta.read_only_fields if field != 'email']

    def validate(self, data):
        validate_password(
            data['password'],
            user=User(**{k: v for k, v in data.items() if k not in ['password', 'referral_code']}),
        )
        return data


class AddressSerializer(serializers.ModelSerializer):
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        from payment.geo import validate_military_address
        values = {field: str(attrs.get(field, getattr(self.instance, field, '')) or '')
                  for field in ('city', 'state', 'zip', 'country')}
        validate_military_address(values['city'], values['state'], values['zip'], values['country'])
        return attrs

    class Meta:
        model = Address
        fields = ['id', 'address', 'city', 'state', 'country', 'zip', 'is_default']


class CatalogSerializer(serializers.ModelSerializer):
    selected_variant = serializers.CharField(read_only=True, default='')
    is_own_store = serializers.SerializerMethodField()
    is_official_store = serializers.BooleanField(source='store.is_official', read_only=True, default=False)
    store_verified = serializers.SerializerMethodField()
    seller_tier = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    sale_price = serializers.SerializerMethodField()
    store_name = serializers.CharField(source='store.name', read_only=True)
    store_username = serializers.CharField(source='store.username', read_only=True)
    rating_count = serializers.IntegerField(read_only=True, default=0)
    tags = serializers.SerializerMethodField()

    specifications = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id',
            'selected_variant',
            'title',
            'description',
            'category',
            'brand',
            'price',
            'sale_price',
            'discount',
            'available',
            'sales',
            'flash_sale_end',
            'variants',
            'average_rating',
            'rating_count',
            'store',
            'store_name',
            'store_username',
            'is_official_store',
            'store_verified',
            'seller_tier',
            'image',
            'images',
            'tags',
            'created',
            'is_own_store',
            'weight',
            'length',
            'width',
            'height',
            'is_digital',
            'specifications',
            'updated',
            'product_type',
            'affiliate_hoplink',
            'affiliate_vendor_nickname',
            'affiliate_button_text',
        ]

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_specifications(self, obj):
        if getattr(obj, 'is_digital', False) or getattr(obj, 'product_type', '') == Product.PRODUCT_TYPE_AFFILIATE_CLICKBANK:
            return None
        spec = getattr(obj, 'specification', None)
        if not spec:
            from product.models import Specification
            spec = Specification.objects.filter(product=obj).first()
        if spec:
            return {
                'serial': spec.serial,
                'attributes': spec.attributes,
                'height': str(spec.height),
                'width': str(spec.width),
                'breadth': str(spec.breadth),
                'weight': str(spec.weight),
                'color': spec.color,
            }
        return None

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_store_verified(self, obj):
        return bool(obj.store.status == Store.STATUS_ACTIVE and obj.store.verified_at)

    def get_seller_tier(self, obj):
        return calculate_store_tier(obj.store)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_own_store(self, obj):
        return is_own_store(obj, getattr(self.context.get('request'), 'user', None))

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_sale_price(self, obj):
        return str(unit_price(obj))

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_images(self, obj):
        images = []
        request = self.context.get('request')
        for image in obj.images.all():
            if image.image:
                url = image.image.url
                raw = request.build_absolute_uri(url) if request else url
                images.append(normalize_media_url(raw))
        if obj.image_url:
            images.append(normalize_media_url(obj.image_url))
        return images

    @extend_schema_field(OpenApiTypes.STR)
    def get_image(self, obj):
        return next(iter(self.get_images(obj)), '')

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_tags(self, obj):
        return [tag.name for tag in obj.tags.all()]


class ReviewSerializer(serializers.ModelSerializer):
    is_edited = serializers.BooleanField(read_only=True)
    author = serializers.CharField(source='user.first_name', read_only=True)
    is_verified_buyer = serializers.SerializerMethodField()
    is_own_review = serializers.SerializerMethodField()
    can_moderate = serializers.SerializerMethodField()
    images = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    class Meta:
        model = Review
        fields = ['id', 'author', 'rating', 'label', 'comment', 'images', 'created', 'updated', 'is_edited', 'is_verified_buyer', 'is_own_review', 'can_moderate']
        read_only_fields = ['created', 'updated', 'is_edited']
        extra_kwargs = {
            'rating': {'min_value': 1, 'max_value': 5},
            'label': {'max_length': 120},
            'comment': {'max_length': 1000},
        }

    def validate_images(self, value):
        if len(value) > 3:
            raise serializers.ValidationError('You can attach up to 3 photos with your review.')
        return value

    def get_is_verified_buyer(self, obj):
        from storefront.views import check_is_verified_buyer
        return check_is_verified_buyer(obj.user, obj.product) or getattr(obj.user, 'is_staff', False) or getattr(obj.user, 'is_superuser', False)

    def get_is_own_review(self, obj):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            return obj.user_id == request.user.id
        return False

    def get_can_moderate(self, obj):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            user = request.user
            if user.is_staff or user.is_superuser or getattr(user, 'is_business_admin', False):
                return True
            if obj.product and obj.product.store and obj.product.store.user_id == user.id:
                return True
        return False


class CatalogPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    pages = serializers.IntegerField()
    results = CatalogSerializer(many=True)


class CatalogQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False)
    category = serializers.CharField(required=False)
    store = serializers.IntegerField(required=False, min_value=1)
    deals = serializers.BooleanField(required=False)
    min_price = serializers.DecimalField(required=False, max_digits=15, decimal_places=2, min_value=0)
    max_price = serializers.DecimalField(required=False, max_digits=15, decimal_places=2, min_value=0)
    ordering = serializers.ChoiceField(
        required=False,
        choices=['-created', 'price', '-price', '-average_rating', '-sales', '-discount'],
    )
    page = serializers.IntegerField(required=False, min_value=1, default=1)


class AuthRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    password = serializers.CharField(required=False, write_only=True)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    phone1 = serializers.CharField(required=False)
    referral_code = serializers.CharField(required=False)
    token = serializers.CharField(required=False)
    uid = serializers.CharField(required=False)
    refresh = serializers.CharField(required=False)


class CartLineSerializer(serializers.Serializer):
    product = CatalogSerializer()
    quantity = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=15, decimal_places=2)
    purchasable = serializers.BooleanField()


class CartSerializer(serializers.Serializer):
    updated = serializers.DateTimeField()
    id = serializers.IntegerField()
    items = CartLineSerializer(many=True)
    subtotal = serializers.DecimalField(max_digits=15, decimal_places=2)
    shipping = serializers.DecimalField(max_digits=15, decimal_places=2)
    total = serializers.DecimalField(max_digits=15, decimal_places=2)


class ShippingRateSerializer(serializers.Serializer):
    carrier = serializers.CharField()
    currency = serializers.CharField()
    source = serializers.CharField()
    quote_token = serializers.CharField()
    tax = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = serializers.DecimalField(max_digits=6, decimal_places=4, required=False)
    tax_jurisdiction = serializers.CharField(required=False, allow_blank=True)
    service_id = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_default = serializers.BooleanField()


class CheckoutRequestSerializer(serializers.Serializer):
    shipping_quote = serializers.CharField(required=False)
    address = serializers.IntegerField(min_value=1)
    checkout_key = serializers.UUIDField()
    coupon = serializers.CharField(required=False, allow_blank=True)
    shipping_service = serializers.CharField(required=False, default='usps_ground_advantage')
    payment_type = serializers.ChoiceField(
        choices=['cash_on_delivery', 'user_wallet'], required=False, default='cash_on_delivery'
    )


class WalletCheckoutSerializer(serializers.Serializer):
    shipping_quote = serializers.CharField(required=False)
    address = serializers.IntegerField(min_value=1)
    checkout_key = serializers.UUIDField()
    coupon = serializers.CharField(required=False, allow_blank=True)
    shipping_service = serializers.CharField(required=False, default='usps_ground_advantage')
    wallet_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=Decimal('0.00'))


class CouponAdminSerializer(serializers.ModelSerializer):
    last_used_at = serializers.DateTimeField(read_only=True)
    class Meta:
        model = Coupon
        fields = ['id', 'code', 'valid_from', 'valid_to', 'discount', 'num_available', 'num_used', 'active',
                  'type', 'product', 'category', 'minimum_quantity', 'last_used_at']
        read_only_fields = ['id', 'valid_from', 'num_used']

    def validate(self, attrs):
        coupon_type = attrs.get('type', getattr(self.instance, 'type', Coupon.ORDER_TOTAL))
        product = attrs.get('product', getattr(self.instance, 'product', None))
        category = attrs.get('category', getattr(self.instance, 'category', ''))
        minimum = attrs.get('minimum_quantity', getattr(self.instance, 'minimum_quantity', 1))
        if coupon_type in (Coupon.PRODUCT, Coupon.PRODUCT_QUANTITY) and not product:
            raise serializers.ValidationError({'product': 'This coupon type requires a product.'})
        if coupon_type == Coupon.CATEGORY and not category:
            raise serializers.ValidationError({'category': 'This coupon type requires a category.'})
        if coupon_type != Coupon.PRODUCT_QUANTITY and minimum != 1:
            raise serializers.ValidationError({'minimum_quantity': 'Quantity thresholds are only valid for product quantity coupons.'})
        if coupon_type == Coupon.PRODUCT_QUANTITY and minimum < 2:
            raise serializers.ValidationError({'minimum_quantity': 'Use at least 2 units for a quantity coupon.'})
        return attrs


class OrderAddressSnapshotSerializer(serializers.Serializer):
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    country = serializers.CharField()
    zip = serializers.CharField()


class OrderItemSnapshotSerializer(serializers.Serializer):
    net_total = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    discount_amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    tax_amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    line_total = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    product = serializers.IntegerField()
    store = serializers.IntegerField()
    title = serializers.CharField()
    image = serializers.CharField(allow_blank=True)
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=15, decimal_places=2)
    is_digital = serializers.BooleanField(required=False, default=False)
    download_url = serializers.URLField(required=False, allow_blank=True)


class OrderSerializer(serializers.Serializer):
    paid_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    refunded_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    updated = serializers.DateTimeField()
    ordered_date = serializers.DateTimeField()
    status_updated_at = serializers.DateTimeField(allow_null=True)
    cancelled_at = serializers.DateTimeField(allow_null=True)
    refunded_at = serializers.DateTimeField(allow_null=True)
    shipping = serializers.JSONField()
    tax = serializers.DecimalField(max_digits=10, decimal_places=2)
    id = serializers.IntegerField()
    reference = serializers.CharField()
    status = serializers.CharField()
    created = serializers.DateTimeField()
    total = serializers.DecimalField(max_digits=15, decimal_places=2)
    subtotal = serializers.DecimalField(max_digits=15, decimal_places=2)
    payment_type = serializers.CharField()
    carrier = serializers.CharField(required=False, default='USPS')
    tracking_number = serializers.CharField(required=False, default='')
    tracking_url = serializers.CharField(required=False, default='')
    shipped_at = serializers.DateTimeField(required=False, allow_null=True)
    delivered_at = serializers.DateTimeField(required=False, allow_null=True)
    tracking_events = serializers.ListField(required=False, child=serializers.DictField(), default=list)
    items = OrderItemSnapshotSerializer(many=True)
    address = OrderAddressSnapshotSerializer()
    tax_snapshot = serializers.JSONField(required=False, default=dict)



class ProductIdRequestSerializer(serializers.Serializer):
    product = serializers.IntegerField(min_value=1)


class CartMutationRequestSerializer(ProductIdRequestSerializer):
    variant = serializers.CharField(max_length=80, allow_blank=True, required=False)
    quantity = serializers.IntegerField(min_value=1, max_value=1000, required=False)


class RefundRequestSerializer(serializers.Serializer):
    REASONS = ['item_damaged', 'wrong_item_received', 'item_missing', 'other']
    reason = serializers.ChoiceField(choices=REASONS)
    other_reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    product_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)
    refund_type = serializers.ChoiceField(
        choices=['store_credit', 'original_payment'],
        default='store_credit',
        required=False,
    )

    def validate(self, attrs):
        if attrs['reason'] == 'other' and not attrs.get('other_reason', '').strip():
            raise serializers.ValidationError({'other_reason': 'Describe the reason for this return.'})
        return attrs


class UserWalletPaymentSerializer(CheckoutRequestSerializer):
    pass



class PasswordChangeRequestSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    password = serializers.CharField(write_only=True, min_length=8, max_length=128, trim_whitespace=False)


class WalletTopupRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal('5.00'), max_value=Decimal('25000.00'))


class PaymentSessionRequestSerializer(serializers.Serializer):
    session_id = serializers.CharField(max_length=255, allow_blank=False)
