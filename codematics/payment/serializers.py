from rest_framework import serializers


from core.models import DeliveryInfo
from payment.models import Order, Coupon


class OrdersSerializer(serializers.ModelSerializer):
    # delivery_info = DeliveryInfo()

    class Meta:
        model = Order

        fields = [
       
            "cartId",
            "orderId",
            "coupon_used",
            "tax",
            "status",
   
            "total",
            "subtotal",
            "status",
      
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
