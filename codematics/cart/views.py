from rest_framework.decorators import action

from core.models import User
from product.models import Product
from cart.models import Cart, CartItem

from cart.seralizers import CartSerializer

from kink import di

from rest_framework import status
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework import viewsets

from drf_spectacular.utils import extend_schema
# Create your views here.


class CartViewSet(viewsets.GenericViewSet):
    auth_user: User = di[User]
    cart_item: CartItem = di[CartItem]
    user_cart: Cart = di[Cart]
    merchant_product: Product = di[Product]

    serializer_class = CartSerializer
    
    
    @extend_schema(responses={status.HTTP_200_OK: CartSerializer})
    @action(detail=False, methods=['get'], url_path='get')
    def get_or_create_cart(self, request):
        data = JSONParser().parse(request)
        user = self.auth_user.objects.get(id=data["user"])
        cart, created = self.user_cart.objects.get_or_create(user=user, ordered=False)
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(responses={status.HTTP_200_OK: None})
    @action(detail=False, methods=['post'], url_path='add')
    def add_to_cart(self, request):
        data = JSONParser().parse(request)
        product = self.merchant_product.objects.get(pk=data["product"])
        cart = self.user_cart.objects.get(user=data["user"], ordered=False)
        cart_item, created = self.cart_item.objects.get_or_create(cart=cart, product=product)
        if not created:
            cart_item.quantity += 1
            cart_item.save()
        serializer = CartSerializer(cart)
        return Response(status=status.HTTP_201_CREATED)

    @extend_schema(responses={status.HTTP_202_ACCEPTED: None})
    @action(detail=False, methods=['delete'], url_path='delete')
    def delete_cart_item(self, request):
        data = JSONParser().parse(request)
        cart_item = self.cart_item.objects.get(cart=data["cart"], product=data["product"])
        cart_item.delete()
        return Response(status=status.HTTP_202_ACCEPTED)
