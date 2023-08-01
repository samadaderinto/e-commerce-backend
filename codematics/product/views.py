from django.db import transaction
from django.conf import settings
from rest_framework_word_filter import FullWordSearchFilter
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.parsers import JSONParser
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.mixins import CreateModelMixin
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework import status
from rest_framework.generics import ListAPIView, GenericAPIView
from core.models import Recent, Review
from core.serializers import RecentsSerializer,ReviewsSerializer

from product.models import Product, ProductImg, Specification
from product.serializers import (
    ProductCardSerializer,
    ProductImgSerializer,
    ProductSerializer,
)


from core.utilities import methods
from core.permissions import EcommerceAccessPolicy

from usps import USPSApi, Address as uspsAddress
from usps import SERVICE_PRIORITY, LABEL_ZPL

# Create your views here.





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
def view_product(request, id):
    try:
        product = Product.objects.prefetch_related("productId").get(pk=id)
    except:
        return Response(status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = ProductSerializer(product)
        if request.data["user"]:
            usps = USPSApi(settings.USPS_USERNAME)
            to_address = uspsAddress(
                name="Tobin Brown",
                address_1="1234 Test Ave.",
                city="Test",
                state="NE",
                zipcode="55555",
            )

            from_address = uspsAddress(
                name="Tobin Brown",
                address_1="1234 Test Ave.",
                city="Test",
                state="NE",
                zipcode="55555",
            )
            validate_to_address = usps.validate_address(to_address)
            validate_from_address = usps.validate_address(from_address)
            weight = 10
            if validate_to_address.result and validate_from_address.result:
                label = usps.create_label(
                    to_address, from_address, weight, SERVICE_PRIORITY, LABEL_ZPL
                )

            return Response(serializer.data, label.result, status=status.HTTP_200_OK)
        return Response(serializer.data,status=status.HTTP_200_OK)
    
    
    elif request.method == methods["delete"]:
        product.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


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
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SearchProduct(ListAPIView):
    permission_classes = (EcommerceAccessPolicy,)

    serializer_class = ProductCardSerializer

    search_field = (
        "id",
        "title",
        "available",
        "discount",
        "price",
        "store",
        "average_rating",
    )

    filter_backends = (SearchFilter,)
    ordering_fields = ["price"]

    paginate_by = 15

    def get_queryset(self):
        return Product.objects.filter(visibility=True)

    def get_serializer_context(self):
        return {"request": self.request}
    
    
@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_product_reviews(request, productId):
    try:
        product = (
            Review.objects.filter(productId=productId).order_by("created").reverse()
        )
    except:
        return Response(status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = ReviewsSerializer(product, many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)    
