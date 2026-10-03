from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from core.models import Address, Review, User
from product.models import Product
from payment.models import Coupon
from product.policies import is_own_store


def unit_price(product):
    return (product.price * Decimal(100 - product.discount) / 100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone1', 'is_staff', 'is_superuser']
        read_only_fields = ['id', 'email', 'is_staff', 'is_superuser']


class RegisterSerializer(UserSerializer):
    password = serializers.CharField(write_only=True, min_length=8, max_length=128, trim_whitespace=False)
    referral_code = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ['password', 'referral_code']
        read_only_fields = ['id', 'is_staff', 'is_superuser']

    def validate(self, data):
        validate_password(
            data['password'],
            user=User(**{k: v for k, v in data.items() if k not in ['password', 'referral_code']}),
        )
        return data


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'address', 'city', 'state', 'country', 'zip', 'is_default']


class CatalogSerializer(serializers.ModelSerializer):
    is_own_store = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    sale_price = serializers.SerializerMethodField()
    store_name = serializers.CharField(source='store.name', read_only=True)
    store_username = serializers.CharField(source='store.username', read_only=True)
    rating_count = serializers.IntegerField(read_only=True, default=0)
    tags = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'title', 'description', 'category', 'brand', 'price', 'sale_price',
                  'discount', 'available', 'average_rating', 'rating_count', 'store',
                  'store_name', 'store_username', 'image', 'images', 'tags', 'created',
                  'is_own_store', 'weight', 'is_digital']

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
                images.append(request.build_absolute_uri(url) if request else url)
        if obj.image_url:
            images.append(obj.image_url)
        return images

    @extend_schema_field(OpenApiTypes.STR)
    def get_image(self, obj):
        return next(iter(self.get_images(obj)), '')

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_tags(self, obj):
        return [tag.name for tag in obj.tags.all()]


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source='user.first_name', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'author', 'rating', 'label', 'comment', 'created']
        extra_kwargs = {'rating': {'min_value': 1, 'max_value': 5}}


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
    id = serializers.IntegerField()
    items = CartLineSerializer(many=True)
    subtotal = serializers.DecimalField(max_digits=15, decimal_places=2)
    shipping = serializers.DecimalField(max_digits=15, decimal_places=2)
    total = serializers.DecimalField(max_digits=15, decimal_places=2)


class ShippingRateSerializer(serializers.Serializer):
    service_id = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_default = serializers.BooleanField()


class CheckoutRequestSerializer(serializers.Serializer):
    address = serializers.IntegerField(min_value=1)
    checkout_key = serializers.UUIDField()
    coupon = serializers.CharField(required=False, allow_blank=True)
    shipping_service = serializers.CharField(required=False, default='usps_ground_advantage')
    payment_type = serializers.ChoiceField(
        choices=['cash_on_delivery', 'stripe_wallet'], required=False, default='cash_on_delivery'
    )


class WalletCheckoutSerializer(serializers.Serializer):
    address = serializers.IntegerField(min_value=1)
    checkout_key = serializers.UUIDField()
    coupon = serializers.CharField(required=False, allow_blank=True)
    shipping_service = serializers.CharField(required=False, default='usps_ground_advantage')


class CouponAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ['id', 'code', 'valid_from', 'valid_to', 'discount', 'num_available', 'num_used', 'active',
                  'type', 'product', 'category', 'minimum_quantity']
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
    product = serializers.IntegerField()
    store = serializers.IntegerField()
    title = serializers.CharField()
    image = serializers.CharField(allow_blank=True)
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=15, decimal_places=2)
    is_digital = serializers.BooleanField(required=False, default=False)
    download_url = serializers.URLField(required=False, allow_blank=True)


class OrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    reference = serializers.CharField()
    status = serializers.CharField()
    created = serializers.DateTimeField()
    total = serializers.DecimalField(max_digits=15, decimal_places=2)
    subtotal = serializers.DecimalField(max_digits=15, decimal_places=2)
    payment_type = serializers.CharField()
    items = OrderItemSnapshotSerializer(many=True)
    address = OrderAddressSnapshotSerializer()


class ProductIdRequestSerializer(serializers.Serializer):
    product = serializers.IntegerField(min_value=1)


class CartMutationRequestSerializer(ProductIdRequestSerializer):
    quantity = serializers.IntegerField(min_value=1, max_value=1000, required=False)
