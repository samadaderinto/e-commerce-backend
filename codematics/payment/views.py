
from django.conf import settings


from cart.models import Cart, CartItem
from cart.seralizers import CartSerializer

from payment.models import DeliveryInfo
from event_notification.views import created_order_nofication


from payment.models import Coupon
from product.models import Product
from core.models import Address,  User
from core.permissions import EcommerceAccessPolicy
from core.utilities import methods, make_payment
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
            global coupon_discount
            coupon_discount = 0
            user = User.objects.get(id=serializer.validated_data["user"])
            cart = Cart.objects.get(userId=user.id, ordered=False)
            items = CartItem.objects.filter(cart=cart.id)
            # default_address = Address.objects.get(
            #     user=user.id, is_default=True)
            address = serializer.validated_data.get("address", {})
            address_serializer = DeliveryInfo(data=address)
            cart_serializer = CartSerializer(cart)
            code = serializer.validated_data["coupon_code"]

            if code:
                try:
                    coupon = Coupon.objects.get(code=code)
                    if coupon.can_use():
                        coupon_discount = coupon.discount
                    else:
                        return Response("invalid coupon", status=status.HTTP_401_UNAUTHORIZED)
                except:
                    return Response("invalid coupon", status=status.HTTP_404_NOT_FOUND)

            if address_serializer.is_valid():
                checkout_session = make_payment(
                    items, cart_serializer.total, coupon_discount)
                if checkout_session["payment_status"] == "paid":
                    cart.ordered = True
                    coupon.used()
                    cart.save()
                    address_serializer.save()
                    serializer.save()

                created_order_nofication(user, "order sucessfully created")
                return Response({'id': checkout_session.id})

            return Response(address_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
