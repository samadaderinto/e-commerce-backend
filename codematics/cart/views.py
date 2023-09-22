from core.utilities import methods
from cart.models import Cart, CartItem
from cart.seralizers import (
    AddToCartSerializer,
    CartItemSerializer,
    CartSerializer
)
from core.permissions import EcommerceAccessPolicy

from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import JSONParser

from rest_framework.viewsets import ModelViewSet


# Create your views here.
@api_view([methods["get"]])
@permission_classes((IsAuthenticated,))
def CartViewSet(request, userId):
     if request.method == methods["get"]:

        try:
           cart = Cart.objects.get(userId=userId, ordered=False).prefetch_related("cart_id")
        except:
            data = {"userId": userId}
            serializer = CartSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

   
        
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CartItemViewSet(ModelViewSet):
    def get_queryset(self):
        return CartItem.objects.filter(cart_id=self.request.data["cart_id"])

    def get_serializer_class(self):
        if self.request.method == methods["post"]:
            return AddToCartSerializer
        return CartItemSerializer

    def get_serializer_context(self):
        return {"cart_id": self.request.data["cart_id"]}

    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)
