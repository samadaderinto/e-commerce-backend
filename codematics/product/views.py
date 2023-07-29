from django.db import transaction

from rest_framework.filters import SearchFilter
from rest_framework.parsers import JSONParser
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.mixins import CreateModelMixin
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework import status
from rest_framework.generics import ListAPIView, GenericAPIView
from core.models import Recent
from core.serializers import RecentsSerializer

from product.models import Cart, CartItem, Product, ProductImg
from product.serializers import  ProductCardSerializer, ProductImgSerializer, ProductSerializer


from core.utilities import methods
from product.serializers import (
    AddToCartSerializer,
    CartItemSerializer,
    CartSerializer,
    JoinCartSerializer,
)
from core.permissions import EcommerceAccessPolicy


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

    return Response(serializer.data, status=201)




class CartViewSet(CreateModelMixin, GenericViewSet):
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
        return Response(serializer.data, safe=False)

    elif request.method == methods["put"]:
        data = JSONParser.parse(request)
        serializer = CartSerializer(cart, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data,status=status.HTTP_202_ACCEPTED)
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
        data = JSONParser.parse(request)
        serializer = CartSerializer(cart_item, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == methods["delete"]:
        cart_item.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def cart_item_by_cart(request, cartId):
    try:
        cart_item = CartItem.objects.filter(cartId=cartId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = CartItemSerializer(cart_item, many=True)
        return Response(serializer.data, safe=False, status=status.HTTP_200_OK)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def cart_item_by_cart_id(request, cartId):
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
        return Response(serializer.data, safe=False)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def cart_item_detect_same_item(request, cartId, productId):
    try:
        cart_item = CartItem.objects.filter(cartId=cartId).filter(productId=productId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = CartItemSerializer(cart_item, many=True)
        return Response(serializer.data, safe=False,status=status.HTTP_200_OK)

@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def recent_product_by_user(request, userId):
    try:
        recent = (
            Recent.objects.filter(user=userId)
            .prefetch_related("productId")
            .order_by("created")
            .reverse()
        )
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = RecentsSerializer(recent, many=True, context={"request": request})
        return Response(serializer.data, safe=False, status=status.HTTP_200_OK)
    
    
@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def product_images_by_product_id(request, productId):
    try:
        productImg = ProductImg.objects.filter(productId=productId)
    except:
        return Response(status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = ProductImgSerializer(productImg, many=True)
        return Response(serializer.data, safe=False)


@api_view([methods["get"], methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def product_image_by_id(request, id):
    try:
        productImg = ProductImg.objects.filter(pk=id)
    except:
        return Response(status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = ProductImgSerializer(productImg)
        return Response(serializer.data)

    elif request.method == methods["delete"]:
        productImg.delete()
        return Response(status=status.HTTP_202_ACCEPTED)    
    
@api_view([methods["get"], methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def productcard_by_id(request, id):
    try:
        product = Product.objects.prefetch_related("productId").get(pk=id)
    except:
        return Response(status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = ProductCardSerializer(product)
        return Response(serializer.data)
    elif request.method == methods["delete"]:
        product.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


@api_view([methods["get"], methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def product_by_id(request, id):
    try:
        product = Product.objects.prefetch_related("productId").get(pk=id)
    except:
        return Response(status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = ProductCardSerializer(product)
        return Response(serializer.data)
    elif request.method == methods["delete"]:
        product.delete()
        return Response(status=status.HTTP_202_ACCEPTED)    
    
    
@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def product_list(request):
    if request.method == methods["get"]:
        products = Product.objects.all().order_by("created").reverse()
        serializer = ProductSerializer(
            products, context={"request": request}, many=True
        )
        return Response(serializer.data, safe=False, status=status.HTTP_200_OK)   
    
    


@api_view([methods["get"], methods["put"]])
@permission_classes((EcommerceAccessPolicy,))
def product_image_list(request):
    if request.method == methods["get"]:
        productImages = ProductImg.objects.all()
        serializer = ProductImgSerializer(productImages, many=True)
        return Response(serializer.data, safe=False)

    elif request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = ProductImgSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)     
    
    
class search_product(ListAPIView):
    permission_classes = (EcommerceAccessPolicy,)
    queryset = Product.objects.all()
    serializer = ProductSerializer()
    search_field = (
        "title",
        "description",
        "category",
        "discount",
        "average_rating",
        "tags",
        "store",
    )
    ordering_fields = ['min_price',"max_price"]
    filter_backends = SearchFilter
    paginate_by = 15    