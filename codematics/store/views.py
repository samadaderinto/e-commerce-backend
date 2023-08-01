# Create your views here
import os
from rest_framework import status
from rest_framework.response import Response
from rest_framework.parsers import JSONParser,MultiPartParser
from rest_framework.decorators import api_view, permission_classes,parser_classes

from rest_framework.filters import SearchFilter, OrderingFilter, BaseFilterBackend
from rest_framework_word_filter import FullWordSearchFilter


from product.models import Product,Specification
from store.models import StoreInfo, StoreAddress, StoreImg, Schedule, Store

from rest_framework.generics import ListAPIView, GenericAPIView
from core.permissions import EcommerceAccessPolicy
from core.utilities import methods
from product.serializers import ProductSerializer,SpecificationSerializer
from store.serializers import ScheduleSerializer, StoreSerializer


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_store(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = StoreSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def schedule_product_visibility(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = ScheduleSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(f"visible will be updated by {serializer.make_visible_at}",status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def edit_store_info(request, storeId):
    try:
        store = Store.objects.get(pk=storeId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["delete"]:
        store.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_store(request, storeId):
    try:
        store = Store.objects.get(id=storeId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["delete"]:
        store.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_store(request, userId):
    try:
        store = Store.objects.filter(user=userId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == methods["get"]:
        serializer_context = {"request": request}
        serializer = StoreSerializer(store, context=serializer_context, many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_stores(request):
    try:
        store = Store.objects.all().order_by("user").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == methods["get"]:
        serializer = StoreSerializer(store, many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def store_products(request, store):
    try:
        product = Product.objects.filter(store=store)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = ProductSerializer(product, many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)


@api_view([methods["get"], methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def schedules(request, storeId,productId):
    try:
        schedules = Schedule.objects.filter(store=storeId,productId=productId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = ScheduleSerializer(schedules)
        return Response(serializer.data,status=status.HTTP_200_OK)

    elif request.method == methods["delete"]:
        schedules.delete()
        return Response(status=status.HTTP_202_ACCEPTED)

@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_specifications(request, productId):
    try:
        specification = Specification.objects.filter(product=productId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["delete"]:
        specification.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_specifications(request, productId):
    try:
        specifications = Specification.objects.filter(product=productId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = SpecificationSerializer(specifications)
        return Response(serializer.data,status=status.HTTP_200_OK)


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["post"]])
@parser_classes([MultiPartParser])
def create_product(request):
    if request.method == methods["post"]:
        data = request.data
        serializer = ProductSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["post"]])
def create_specifications(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = ProductSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_file(request, filename):
    if request.method == methods["get"]:
        ext = filename.split(".")[-1]
        filenamenoExt = filename.replace(f"{ext}", "")
        fileDir = "%s/%s.%s" % ("img", filenamenoExt, ext)
        if os.path.isfile((f"media/images/{filename}")):
            os.remove(fileDir)
            return Response(f"{filename} deleted",status=status.HTTP_202_ACCEPTED)
        return Response("file not found",status=status.HTTP_404_NOT_FOUND)


class IsOwnerSearchProduct(ListAPIView):
    """
    Filter that only allows store to see their own products.
    """
    serializer_class = ProductSerializer
    permission_classes = (EcommerceAccessPolicy,)
   
    filter_backends = (SearchFilter,)
    search_field = (
        "title",
        "description",
        "category",
        "discount",
        "average_rating",
        "tags",
        "store",
        "price"
    )
    ordering_fields = ["price"]
    paginate_by = 15
    
    def get_queryset(self):
        
        store = self.request.data["store"]
        
        return Product.objects.filter(store=store)