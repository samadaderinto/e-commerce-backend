from rest_framework import serializers


from payment.models import Order, Coupon, DeliveryInfo


class OrdersSerializer(serializers.ModelSerializer):
    delivery = DeliveryInfo()

    class Meta:
        model = Order

        fields = [
            "user",
            "cartId",
            "orderId",
            "coupon_code",
            "tax",
            "status",
            "total",
            "subtotal",
            "status",
            "delivery",
            "ordered_date",
            "ordered",
            "payment_type"
        ]
       


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
        ]
