
from core.utilities import methods
from cart.models import Cart, CartItem
from cart.seralizers import AddToCartSerializer, CartItemSerializer, CartSerializer, JoinCartSerializer
from core.permissions import EcommerceAccessPolicy


from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.mixins import CreateModelMixin, RetrieveModelMixin, DestroyModelMixin
from rest_framework.viewsets import ModelViewSet, GenericViewSet



# Create your views here.
@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_cart(request, userId, ordered):
    try:
        user = Cart.objects.get(pk=userId, ordered=ordered)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = JoinCartSerializer(user)

        return Response(serializer.data, status=status.HTTP_200_OK)


class CartViewSet(CreateModelMixin, RetrieveModelMixin, DestroyModelMixin, GenericViewSet):
    queryset = Cart.objects.all()
    permission_classes = (EcommerceAccessPolicy,)
    serializer_class = CartSerializer


class CartItemViewSet(ModelViewSet):
    def get_queryset(self):
        return CartItem.objects.filter(cartId=self.kwargs["cart_pk"])

    def get_serializer_class(self):
        if self.request.method == methods["post"]:
            return AddToCartSerializer
        return CartItemSerializer

    def get_serializer_context(self):
        return {"cartId": self.kwargs["cart_pk"]}

    permission_classes = (EcommerceAccessPolicy,)


@api_view([methods["get"], methods["delete"], methods["put"]])
@permission_classes((EcommerceAccessPolicy,))
def cart_by_user(request, user):
    try:
        cart = Cart.objects.filter(user=user)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = CartSerializer(cart, many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)

    elif request.method == methods["put"]:
        data = JSONParser().parse(request)
        serializer = CartSerializer(cart, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == methods["delete"]:
        cart.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


@api_view([methods["get"], methods["delete"], methods["put"]])
@permission_classes((EcommerceAccessPolicy,))
def cart_item_by_id(request, pk):
    try:
        cart_item = CartItem.objects.filter(pk=pk)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = CartItemSerializer(cart_item, many=True)
        return Response(serializer.data)

    elif request.method == methods["put"]:
        data = JSONParser().parse(request)
        serializer = CartSerializer(cart_item, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data,status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == methods["delete"]:
        cart_item.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def cart_item_by_cartId(request, cartId):
    try:
        cart_item = CartItem.objects.filter(cartId=cartId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = CartItemSerializer(cart_item, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def cart_items_by_cart_id(request, cartId):
    try:
        cart_item = (
            CartItem.objects.filter(cartId=cartId)
            .prefetch_related("productId")
            .order_by("created")
        )
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = JoinCartSerializer(cart_item, many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def cart_item_detect_same_item(request, cartId, productId):
    try:
        cart_item = CartItem.objects.filter(cartId=cartId).filter(productId=productId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = CartItemSerializer(cart_item, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
