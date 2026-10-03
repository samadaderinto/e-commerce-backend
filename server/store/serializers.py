from decimal import Decimal

from django.db import transaction
from rest_framework import serializers
from taggit.serializers import TaggitSerializer, TagListSerializerField

from product.models import Product, ProductImg, Specification
from store.models import (
    MerchantWallet, Schedule, Store, StoreAddress, StoreEarningsLedger,
    StoreImg, StoreInfo, StorePayout,
)


from store.services import calculate_store_tier


class StoreSerializer(serializers.ModelSerializer):
    seller_tier = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = [
            'id', 'user', 'username', 'name', 'status', 'is_official', 'seller_tier',
            'blocked_reason', 'blocked_at', 'blocked_by', 'verified_at', 'verified_by',
            'created', 'updated',
        ]
        read_only_fields = [
            'id', 'user', 'status', 'is_official', 'seller_tier',
            'blocked_reason', 'blocked_at', 'blocked_by', 'verified_at', 'verified_by',
            'created', 'updated',
        ]
        extra_kwargs = {'username': {'required': False}}

    def get_seller_tier(self, obj):
        return calculate_store_tier(obj)


class StoreInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreInfo
        fields = ['email', 'bio', 'avatar_url', 'banner_url', 'website',
                  'instagram', 'twitter', 'facebook',
                  'whatsapp', 'phone1', 'phone2']
        extra_kwargs = {field: {'required': False, 'allow_blank': True}
                        for field in ['bio', 'avatar_url', 'banner_url', 'website',
                                      'instagram', 'twitter', 'facebook']}


class StoreAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreAddress
        fields = ['id', 'store', 'address', 'zip', 'country', 'state', 'city',
                  'is_default', 'created', 'updated']
        read_only_fields = ['id', 'store', 'created', 'updated']
        extra_kwargs = {'is_default': {'default': True}}


class StoreOnboardingSerializer(StoreSerializer):
    profile = StoreInfoSerializer(required=False, write_only=True)
    address = StoreAddressSerializer(required=False, write_only=True)

    class Meta(StoreSerializer.Meta):
        fields = StoreSerializer.Meta.fields + ['profile', 'address']

    @transaction.atomic
    def create(self, validated_data):
        profile = validated_data.pop('profile', None)
        address = validated_data.pop('address', None)
        store = super().create(validated_data)
        if profile is not None:
            StoreInfo.objects.create(store=store, **profile)
        if address is not None:
            StoreAddress.objects.create(store=store, **address)
        return store


class MerchantImageSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(allow_empty_file=False)

    class Meta:
        model = ProductImg
        fields = ['id', 'image']

    def validate_image(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('Images must be at most 5 MB.')
        if value.image.format not in {'JPEG', 'PNG', 'WEBP'}:
            raise serializers.ValidationError('Use a JPEG, PNG or WebP image.')
        return value


class MerchantSpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specification
        exclude = ['product']
        read_only_fields = ['id', 'created', 'updated']
        extra_kwargs = {field: {'min_value': Decimal('0.01')}
                        for field in ['height', 'width', 'breadth', 'weight']}


class MerchantProductSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField(required=False)
    images = MerchantImageSerializer(many=True, read_only=True)
    specifications = MerchantSpecificationSerializer(source='specification', read_only=True)
    sale_price = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'store', 'title', 'description', 'category', 'price', 'brand', 'image_url',
                  'discount', 'sale_price', 'available', 'visibility', 'label',
                  'tags', 'images', 'specifications', 'sales', 'average_rating',
                  'sponsored', 'weight', 'is_digital', 'digital_file_url', 'created', 'updated']
        read_only_fields = ['id', 'store', 'sales', 'average_rating', 'sponsored',
                            'created', 'updated']
        extra_kwargs = {
            'price': {'min_value': Decimal('0.01')},
            'discount': {'default': 0},
            'available': {'default': 0},
            'visibility': {'default': False},
            'weight': {'min_value': Decimal('0.00'), 'default': Decimal('1.00')},
        }

    def validate(self, attrs):
        is_digital = attrs.get('is_digital', getattr(self.instance, 'is_digital', False))
        file_url = attrs.get('digital_file_url', getattr(self.instance, 'digital_file_url', ''))
        if is_digital:
            attrs['weight'] = Decimal('0.00')
            if not file_url:
                raise serializers.ValidationError({
                    'digital_file_url': 'Add a download URL for a digital product.',
                })
        else:
            attrs['digital_file_url'] = ''
            if 'weight' not in attrs and not getattr(self.instance, 'weight', None):
                attrs['weight'] = Decimal('1.00')
        return attrs


class InventorySerializer(serializers.Serializer):
    available = serializers.IntegerField(min_value=0)


class DashboardQuerySerializer(serializers.Serializer):
    days = serializers.IntegerField(default=30, min_value=1, max_value=365)
    low_stock_threshold = serializers.IntegerField(default=5, min_value=1, max_value=1000)


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = ['id', 'store', 'product', 'make_visible_at']
        read_only_fields = ['id', 'store']


class StoreInfoForProductCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ['username', 'name']


class StoreImgSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreImg
        fields = ['id', 'store', 'url']


class StorePayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = StorePayout
        fields = [
            'id', 'store', 'wallet', 'amount', 'status', 'payout_method',
            'account_details', 'reference', 'processed_at',
            'notes', 'created', 'updated',
        ]
        read_only_fields = ['id', 'store', 'wallet', 'status', 'reference', 'processed_at', 'created', 'updated']


class PayoutCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('5.00'))
    payout_method = serializers.ChoiceField(
        choices=StorePayout.METHOD_CHOICES,
        default=StorePayout.METHOD_BANK_TRANSFER,
    )
    account_details = serializers.DictField(required=False, default=dict)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class StoreEarningsLedgerSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)
    store_username = serializers.CharField(source='store.username', read_only=True)

    class Meta:
        model = StoreEarningsLedger
        fields = [
            'id', 'wallet', 'store', 'store_name', 'store_username', 'order',
            'entry_type', 'gross_amount', 'fee_amount', 'net_amount', 'status',
            'available_at', 'cleared_at', 'description', 'reference',
            'created', 'updated',
        ]
        read_only_fields = fields


class MerchantStoreFinancialSummarySerializer(serializers.Serializer):
    store_id = serializers.IntegerField()
    store_name = serializers.CharField()
    store_username = serializers.CharField()
    status = serializers.CharField()
    is_official = serializers.BooleanField()
    gross_sales = serializers.CharField()
    platform_fee_percent = serializers.CharField()
    platform_fee_deducted = serializers.CharField()
    net_sales = serializers.CharField()
    in_review = serializers.CharField()
    cleared_total = serializers.CharField()
    payouts_completed = serializers.CharField()
    payouts_pending = serializers.CharField()
    available_balance = serializers.CharField()
    refund_window_days = serializers.IntegerField()


class MerchantWalletSerializer(serializers.Serializer):
    wallet_id = serializers.IntegerField()
    stripe_account_id = serializers.CharField(allow_blank=True)
    stripe_details_submitted = serializers.BooleanField()
    stripe_payouts_enabled = serializers.BooleanField()
    available_balance = serializers.CharField()
    pending_balance = serializers.CharField()
    total_withdrawn = serializers.CharField()
    total_gross_sales = serializers.CharField()
    total_platform_fees = serializers.CharField()
    total_net_sales = serializers.CharField()
    refund_window_days = serializers.IntegerField()
    platform_fee_percent = serializers.CharField()
    stores_count = serializers.IntegerField()
    stores = MerchantStoreFinancialSummarySerializer(many=True)


class MerchantPayoutCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('5.00'))
    payout_method = serializers.ChoiceField(
        choices=StorePayout.METHOD_CHOICES,
        default=StorePayout.METHOD_BANK_TRANSFER,
    )
    account_details = serializers.DictField(required=False, default=dict)
    store_id = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


