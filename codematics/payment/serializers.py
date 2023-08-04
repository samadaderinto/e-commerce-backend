from rest_framework import serializers


from core.models import DeliveryInfo
from payment.models import Order, Coupon


class OrdersSerializer(serializers.ModelSerializer):
    delivery_info = DeliveryInfo()

    class Meta:
        model = Order

        fields = [
            "id",
            "cartId",
            "orderId",
            "coupon_used",
            "tax",
            "status",
            "delivery",
            "total",
            "subtotal",
            "status",
            "delivery_info",
            "ordered_date",
            "ordered",
            "payment_type"
        ]
       
class CheckOutSerializer(serializers.Serializer):
    
   # serializer fields will be here
    
    fields = [
            "id",
            "cartId",
            "orderId",
            "coupon_used",
            "tax",
            "status",
            "delivery",
            "total",
            "subtotal",
            "status",
            "delivery_info",
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
