from django.conf import settings

from kink import di

from cart.models import Cart, CartItem
from utils.functions import make_payment
from payment.models import Coupon, DeliveryInfo
from product.models import Product
from core.models import Address, User

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

from django.shortcuts import get_object_or_404, get_list_or_404

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
        cart = get_object_or_404(self.user_cart, user=data['user'], ordered=False)
        items = get_list_or_404(self.cart_item, cart=cart.id)

        for item in items:
            product = Product.objects.get(pk=item.productId)

            if product.available == 0:
                return Response(data={'message': 'One of your products is sold out'}, status=status.HTTP_409_CONFLICT)

        return Response('proceed to checkout', status=status.HTTP_200_OK)

    @extend_schema(responses={status.HTTP_200_OK: dict})
    @action(detail=False, methods=['post'], url_path='checkout/pay')
    def capture_checkout_session(self, request):
        data = JSONParser().parse(request)
        serializer = OrdersSerializer(data=data)

        serializer.is_valid(raise_exception=True)

        user = get_object_or_404(self.auth_user, id=serializer.validated_data['user'])
        cart = get_object_or_404(self.user_cart, user=user.id, ordered=False)
        items = get_object_or_404(self.cart_item, cart=cart.id)

        cart_serializer = CartSerializer(cart)
        coupon = get_object_or_404(Coupon, code=serializer.validated_data['coupon'])
        discount = coupon.discount if coupon.can_use() else None

        if not discount:
            return Response('invalid coupon code', status=status.HTTP_404_NOT_FOUND)

        checkout_session = make_payment(items, cart_serializer.total, discount)
        if checkout_session['payment_status'] == 'paid':
            cart.ordered = True
            coupon.used()
            cart.save()
            serializer.save()

        created_order_nofication(user, 'order sucessfully created')
        return Response({'id': checkout_session.id})
