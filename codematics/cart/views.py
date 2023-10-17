from product.models import Product
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
            cart = Cart.objects.get(userId=userId, ordered=False)
        except:
            data = {"userId": userId}
            serializer = CartSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view([methods["get"], methods["post"], methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def CartItemViewSet(request):
    data = JSONParser().parse(request)
    context ={"cart_id": data.get(
                    "cart_id")}

    if request.method == methods["get"]:
        try:
            cart_items = (
                CartItem.objects.filter(cart_id=context.get("cart_Id")).order_by("created").reverse()
            )
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = CartItemSerializer(cart_items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == methods["post"]:
        
        serializer = AddToCartSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if request.method == methods["delete"]:
        try:
            cart_item = CartItem.objects.get(cart_id=context.get("cart_Id"))
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        cart_item.delete()
        return Response(status=status.HTTP_202_ACCEPTED)
