from django.db import transaction
from django.conf import settings
from django.core.paginator import Paginator


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
        return Response(serializer.data,status=status.HTTP_200_OK)


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

# you will also need to request further permissions by emailing uspstechnicalsupport@mailps.custhelp.com about Label API access.
# get labelzpi and change value in constants.py 

@api_view([methods["get"], methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def view_product(request, productId):
    try:
        product = Product.objects.get(id=productId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == methods["get"]:
        serializer = ProductSerializer(product)
        related_products = Product.objects.filter(category=product.category,visibility=True).exclude(id=id)[:5]
        if request.user.is_authenticated:
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
            weight = 10 # in ounce
            if validate_to_address.result and validate_from_address.result:
                # this is to get estimate delivery date if user orders product in certain range of time
                label = usps.create_label(
                    to_address, from_address, weight, SERVICE_PRIORITY, LABEL_ZPL
                )

            return Response(serializer.data, {"label": label.result}, status=status.HTTP_200_OK)
        return Response(serializer.data,status=status.HTTP_200_OK)
    
    
    elif request.method == methods["delete"]:
        product.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


@api_view([methods["get"], methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def product_image_list(request):
    
    if request.method == methods["get"]:
        productImages = ProductImg.objects.all()
        serializer = ProductImgSerializer(productImages, many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)

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
        "title",
        "description",
        "category",
        "discount",
        "average_rating",
        "tags",
        "store",
        "price",
    )

    filter_backends = [SearchFilter,OrderingFilter]
    ordering_fields = ["price","average_rating","discount"]
 

    def get_queryset(self):
        return Product.objects.filter(visibility=True)

    def get_serializer_context(self):
        return {"request": self.request}
    
    
@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_product_reviews(request, productId):
    try:
        reviews = (
            Review.objects.filter(productId=productId).order_by("created").reverse()
        )
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        page_number = request.GET.get("offset", 1)
        per_page = request.GET.get("limit", 15)
        paginator = Paginator(reviews, per_page=per_page)
        items = paginator.get_page(number=page_number)
        serializer = ReviewsSerializer(items, many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)    


