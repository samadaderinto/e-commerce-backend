from core.models import User
from product.models import Product

from cart.models import Cart, CartItem
from cart.seralizers import CartSerializer

from core.permissions import EcommerceAccessPolicy
from rest_framework import status
from rest_framework.response import Response

from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny

# Create your views here.


class CartViewSet(ModelViewSet):

    serializer_class = CartSerializer
    permission_classes = (AllowAny,)

    def get_or_create_cart(self, request):

        user = User.objects.get(id=request.data["userId"])
        cart, created = Cart.objects.get_or_create(
            userId=user, ordered=False)
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def add_to_cart(self, request):
        cart = Cart.objects.get(userId=request.data["userId"], ordered=False)
        product = Product.objects.get(pk=request.data["product_id"])
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart, product=product)
        if not created:
            cart_item.quantity += 1
            cart_item.save()
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete_cart_item(self, request):
        cart_item = CartItem.objects.get(
            cart=request.data["cart_id"], product=request.data["product_id"])
        cart_item.delete()
        return Response(status=status.HTTP_202_ACCEPTED)
