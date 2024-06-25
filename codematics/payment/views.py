from django.conf import settings

from kink import di

from cart.models import Cart, CartItem
from utils.functions import make_payment
from payment.models import Coupon, DeliveryInfo
from product.models import Product
from core.models import Address,  User

from drf_spectacular.utils import extend_schema

from payment.serializers import OrdersSerializer
from cart.seralizers import CartSerializer

from notification.views import created_order_nofication


from rest_framework.decorators import action
from rest_framework import status
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework import viewsets

import stripe


stripe.api_key = settings.STRIPE_SECRET


# Create your views here.

class PaymentViewSet(viewsets.GenericViewSet):
    auth_user: User = di[User]
    cart_item: CartItem = di[CartItem]
    user_cart: Cart = di[Cart]
    
    
    @extend_schema(responses={status.HTTP_200_OK: dict})
    @action(detail=False, methods=['post'], url_path='checkout/create')
    def create_checkout_session(self, request):
            data = JSONParser().parse(request)
            cart = self.user_cart.objects.get(user=data["user"], ordered=False)
            items = self.cart_item.objects.filter(cart=cart.id)

            for item in items:
                product = Product.objects.get(pk=item.productId)

                if not product.available:
                    return Response( data={"message": "One of your products is sold out"}, status=status.HTTP_409_CONFLICT)

            return Response("proceed to checkout", status=status.HTTP_200_OK)


    @extend_schema(responses={status.HTTP_200_OK: dict})
    @action(detail=False, methods=['post'], url_path='checkout/pay')
    def capture_checkout_session(self, request):
            data = JSONParser().parse(request)
            serializer = OrdersSerializer(data=data)

            serializer.is_valid(raise_exception=True)
            global coupon_discount
            coupon_discount = 0
            user = self.auth_user.objects.get(id=serializer.validated_data["user"])
            cart = self.user_cart.objects.get(user=user.id, ordered=False)
            items = self.cart_item.objects.filter(cart=cart.id)
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

            address_serializer.is_valid(raise_exception=True)
            
            checkout_session = make_payment(items, cart_serializer.total, coupon_discount)
            if checkout_session["payment_status"] == "paid":
                cart.ordered = True
                coupon.used()
                cart.save()
                address_serializer.save()
                serializer.save()

            created_order_nofication(user, "order sucessfully created")
            return Response({'id': checkout_session.id})
        