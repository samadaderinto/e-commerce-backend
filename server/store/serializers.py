from utils.timezones import TimeZoneField
import json
import urllib.parse
from decimal import Decimal
from typing import Any

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
            'id', 'user', 'username', 'name', 'status', 'is_official', 'seller_tier', 'assigned_staff',
            'blocked_reason', 'blocked_at', 'blocked_by', 'verified_at', 'verified_by',
            'created', 'updated', 'last_active_at',
        ]
        read_only_fields = [
            'id', 'user', 'status', 'is_official', 'seller_tier', 'assigned_staff',
            'blocked_reason', 'blocked_at', 'blocked_by', 'verified_at', 'verified_by',
            'created', 'updated', 'last_active_at',
        ]
        extra_kwargs = {'username': {'required': False}}

    def get_seller_tier(self, obj):
        return calculate_store_tier(obj)


class StoreInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreInfo
        fields = ['email', 'bio', 'announcement', 'pinned_products', 'avatar_url', 'banner_url', 'website',
                  'instagram', 'twitter', 'facebook',
                  'whatsapp', 'phone1', 'phone2']
        extra_kwargs = {field: {'required': False, 'allow_blank': True}
                        for field in ['bio', 'announcement', 'avatar_url', 'banner_url', 'website',
                                      'instagram', 'twitter', 'facebook']}


class StoreAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreAddress
        fields = ['id', 'store', 'address', 'zip', 'country', 'state', 'city',
                  'is_default', 'created', 'updated']
        read_only_fields = ['id', 'store', 'created', 'updated']
        extra_kwargs = {'is_default': {'default': True}, **{field: {'required': True, 'allow_blank': False, 'allow_null': False} for field in ('address', 'city', 'state', 'country', 'zip')}}


class StoreOnboardingSerializer(StoreSerializer):
    profile = StoreInfoSerializer(required=False, write_only=True)
    address = StoreAddressSerializer(required=True, write_only=True)

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
    image_url = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    tags = TagListSerializerField(required=False)
    images = MerchantImageSerializer(many=True, read_only=True)
    specifications = MerchantSpecificationSerializer(source='specification', read_only=True)
    sale_price = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'store', 'title', 'description', 'category', 'price', 'brand', 'image_url',
                  'discount', 'sale_price', 'available', 'visibility', 'label',
                  'tags', 'images', 'specifications', 'sales', 'flash_sale_end', 'variants', 'average_rating',
                  'sponsored', 'weight', 'length', 'width', 'height', 'is_digital', 'digital_file_url', 'digital_preview_watermark',
                  'product_type', 'affiliate_hoplink', 'affiliate_vendor_nickname', 'affiliate_button_text', 'created', 'updated']
        read_only_fields = ['id', 'store', 'sales', 'average_rating', 'sponsored',
                            'created', 'updated']
        extra_kwargs = {
            'price': {'min_value': Decimal('0.01')},
            'discount': {'default': 0},
            'available': {'default': 0},
            'visibility': {'default': False},
            'weight': {'min_value': Decimal('0.00'), 'default': Decimal('1.00')},
            'length': {'min_value': Decimal('0.01')}, 'width': {'min_value': Decimal('0.01')}, 'height': {'min_value': Decimal('0.01')},
        }

    def validate_variants(self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(value, list) or len(value) > 100:
            raise serializers.ValidationError('Use at most 100 variants per product.')
        if len(json.dumps(value)) > 65536:
            raise serializers.ValidationError('Variant data must be at most 64 KB.')
        names: set[str] = set()
        for row in value:
            if not isinstance(row, dict) or not isinstance(row.get('name'), str) or not row['name'].strip() or len(row['name']) > 80:
                raise serializers.ValidationError('Each variant needs a name of 1–80 characters.')
            if row['name'] in names:
                raise serializers.ValidationError('Variant names must be unique.')
            names.add(row['name'])
            if 'available' in row:
                row['available'] = serializers.IntegerField(min_value=0, max_value=1000000).run_validation(row['available'])
            row['price_delta'] = str(serializers.DecimalField(max_digits=12, decimal_places=2).run_validation(row.get('price_delta') or '0'))
        return value

    def validate_image_url(self, value: str) -> str:
        # Storage-generated URLs may use local hostnames that URLField rejects.
        if self.instance is not None and value == self.instance.image_url:
            return value
        return serializers.URLField(allow_blank=True, max_length=1000).run_validation(value)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        product_type = attrs.get('product_type', getattr(self.instance, 'product_type', Product.PRODUCT_TYPE_STANDARD))
        if product_type == Product.PRODUCT_TYPE_AFFILIATE_CLICKBANK:
            hoplink = attrs.get('affiliate_hoplink', getattr(self.instance, 'affiliate_hoplink', '') or '').strip()
            if not hoplink:
                raise serializers.ValidationError({
                    'affiliate_hoplink': 'An affiliate HopLink URL is required for ClickBank partner products.'
                })
            split_url = urllib.parse.urlsplit(hoplink)
            if split_url.scheme not in ('http', 'https') or not split_url.netloc:
                raise serializers.ValidationError({
                    'affiliate_hoplink': 'Provide a valid web address starting with http:// or https://.'
                })
            attrs['product_type'] = Product.PRODUCT_TYPE_AFFILIATE_CLICKBANK
            attrs['affiliate_hoplink'] = hoplink
            attrs['is_digital'] = False
            attrs['digital_file_url'] = ''
            attrs['variants'] = []
            attrs['weight'] = Decimal('0.00')
            attrs['length'] = None
            attrs['width'] = None
            attrs['height'] = None
            if not attrs.get('available') and not getattr(self.instance, 'available', None):
                attrs['available'] = 999
            return attrs

        is_digital = attrs.get('is_digital', getattr(self.instance, 'is_digital', False))
        file_url = attrs.get('digital_file_url', getattr(self.instance, 'digital_file_url', ''))
        if is_digital:
            attrs['weight'] = Decimal('0.00')
            attrs['available'] = 0
            attrs['variants'] = []
            if not file_url:
                raise serializers.ValidationError({
                    'digital_file_url': 'Add a download URL for a digital product.',
                })
        else:
            price = attrs.get('price', getattr(self.instance, 'price', Decimal('0')))
            discount = attrs.get('discount', getattr(self.instance, 'discount', 0))
            for option in attrs.get('variants', getattr(self.instance, 'variants', [])):
                if price * (100 - discount) / 100 + Decimal(str(option.get('price_delta') or '0')) <= 0:
                    raise serializers.ValidationError({'variants': 'Each option must have a positive price.'})
            attrs['digital_file_url'] = ''
            if 'weight' not in attrs and not getattr(self.instance, 'weight', None):
                attrs['weight'] = Decimal('1.00')
            weight = attrs.get('weight', getattr(self.instance, 'weight', None))
            if weight is not None and weight < Decimal('0.01'):
                raise serializers.ValidationError({'weight': 'Ensure this value is greater than or equal to 0.01.'})
            for field, default_val in (('length', Decimal('6.00')), ('width', Decimal('4.00')), ('height', Decimal('1.00'))):
                value = attrs.get(field, getattr(self.instance, field, None))
                if value is None:
                    attrs[field] = default_val
        return attrs


class InventorySerializer(serializers.Serializer):
    available = serializers.IntegerField(min_value=0)


class DashboardQuerySerializer(serializers.Serializer):
    time_zone = TimeZoneField(default="UTC", max_length=100)
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
    store_name = serializers.CharField(source='store.name', read_only=True, default='')

    class Meta:
        model = StorePayout
        fields = [
            'id', 'store', 'store_name', 'wallet', 'amount', 'status', 'payout_method',
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


class UppercaseCarrierField(serializers.ChoiceField):
    def to_internal_value(self, data: object) -> str:
        return super().to_internal_value(str(data).upper())


class MerchantTrackingSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['confirmed', 'shipped', 'delivered', 'picked up'], required=False)
    carrier = UppercaseCarrierField(choices=['USPS', 'UPS', 'FEDEX', 'DHL'], default='USPS')
    tracking_number = serializers.CharField(max_length=100, allow_blank=True, required=False, default='')
    event_description = serializers.CharField(max_length=1000, allow_blank=True, required=False, default='')
