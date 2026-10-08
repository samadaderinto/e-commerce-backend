from rest_framework import serializers


from payment.models import Order, Coupon, DeliveryInfo, TaxJurisdiction


class OrdersSerializer(serializers.ModelSerializer):
    # delivery = DeliveryInfo()

    class Meta:
        model = Order

        fields = [
            "user",
            "cart",
            "orderId",
            "coupon_code",
            "tax",
            "status",
            "total",
            "subtotal",
            "delivery",
            "ordered_date",
            "created",
            "updated",
            "status_updated_at",
            "cancelled_at",
            "refunded_at",
            "ordered",
            "payment_type",
            "carrier",
            "tracking_number",
            "tracking_url",
            "shipped_at",
            "delivered_at",
            "tracking_events",
            "shipping_snapshot",
            "items_snapshot",
            "address_snapshot",
            "tax_snapshot",
        ]
        read_only_fields = ['created', 'updated', 'ordered_date', 'status_updated_at', 'cancelled_at', 'refunded_at', 'shipped_at', 'delivered_at']
       


class TaxJurisdictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxJurisdiction
        fields = [
            "id",
            "country",
            "state",
            "postal_code",
            "name",
            "rate",
            "tax_shipping",
            "tax_digital",
            "is_active",
            "created",
            "updated",
        ]
        read_only_fields = ["created", "updated"]

    def validate_rate(self, value):
        from decimal import Decimal
        if value < Decimal('0.00000') or value > Decimal('1.00000'):
            raise serializers.ValidationError("Tax rate must be between 0.00000 (0%) and 1.00000 (100%).")
        return value

    def validate_state(self, value):
        from payment.tax import normalize_us_state
        return normalize_us_state(value)


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            "id",
            "code",
            "valid_from",
            "valid_to",
            "discount",
            "num_available",
            "num_used",
            "active",
            "last_used_at",
        ]
        read_only_fields = ['last_used_at']

