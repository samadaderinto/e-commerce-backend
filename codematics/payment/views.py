from decimal import Decimal
from django.conf import settings


from cart.models import Cart, CartItem
from event_notification.views import created_order_nofication
from core.serializers import AddressSerializer


from payment.models import Coupon, Order, Payment
from product.models import Product
from core.models import Address,  User
from core.permissions import EcommerceAccessPolicy
from core.utilities import methods
from payment.serializers import OrdersSerializer

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import JSONParser


import stripe


stripe.api_key = settings.STRIPE_SECRET


# Create your views here.


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_checkout_session(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)

        cart = Cart.objects.get(userId=request.data["userId"], ordered=False)
        items = CartItem.objects.filter(cart=cart.id)

        for item in items:
            product = Product.objects.get(pk=item.productId)

            if not product.available:
                return Response(
                    data={"message": "One of your products is sold out"},
                    status=status.HTTP_409_CONFLICT
                )

        return Response(
            "proceed to checkout",
            status=status.HTTP_200_OK
        )


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def capture_checkout_session(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = OrdersSerializer(data=data)
        if serializer.is_valid():
            userId = serializer.validated_data["userId"]
            user = User.objects.get(id=userId)
            cart = Cart.objects.get(userId=userId, ordered=False)
            default_address = Address.objects.get(user=userId, is_default=True)
            address = serializer.validated_data.get("address", default_address)
            address_serializer = AddressSerializer(address)
            code = ""
            global coupon_discount
            coupon_discount = 0
            if code != "":

                try:
                    coupon = Coupon.objects.get(code=code)
                    if coupon.can_use():
                        coupon_discount = coupon.discount
                    else:
                        return Response("invalid coupon", status=status.HTTP_401_UNAUTHORIZED)
                except:
                    return Response("invalid coupon", status=status.HTTP_404_NOT_FOUND)

            if address_serializer.is_valid():
                usps_delivery_fee = 10
                tax = 0
                sub_total = round(
                    (cart.grand_total * (100 - coupon_discount) / 100) +
                    tax + usps_delivery_fee, 2
                )

                def make_payment():
                    intent = stripe.PaymentIntent.create(
                        amount=sub_total,
                        currency="usd",
                        automatic_payment_methods={
                            "enabled": True,
                        },
                        receipt_email="test@example.com",
                    )

                    if intent:
                        coupon.used()
                        cart.ordered = True
                        cart.save()
                        address_serializer.save()
                        serializer.save()
                        return intent
                    return None
                
                if address.id is not default_address.id:

                    
                    created_order_nofication(user, "order sucessfully created")
                else:
                    
                    created_order_nofication(user, "order sucessfully created")
                
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
