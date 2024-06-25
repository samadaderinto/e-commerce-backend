import os

from utils.permissions import EcommerceAccessPolicy
from rest_framework import status
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.filters import SearchFilter, OrderingFilter, BaseFilterBackend
from rest_framework_word_filter import FullWordSearchFilter
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView, GenericAPIView

from product.models import Product, Specification, ProductImg
from store.models import StoreInfo, StoreAddress, StoreImg, Schedule, Store
from utils.variables import methods

from product.serializers import ProductSerializer, SpecificationSerializer, ProductImgSerializer
from store.serializers import ScheduleSerializer, StoreSerializer



def create_store(request):
        data = JSONParser().parse(request)
        serializer = StoreSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)



def schedule_product_visibility(request):
    data = JSONParser().parse(request)
    serializer = ScheduleSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(f"visible will be updated by {serializer.make_visible_at}", status.HTTP_200_OK)


@api_view([methods["put"]])
def edit_store_info(request, storeId):
    data = JSONParser().parse(request)

    try:
        store = Store.objects.get(id=storeId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)


    serializer = StoreSerializer(store, data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_202_ACCEPTED)



def delete_store(request, storeId):
    try:
        store = Store.objects.get(id=storeId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)


    store.delete()
    return Response(status=status.HTTP_202_ACCEPTED)



def get_stores(request, userId):
    try:
        store = Store.objects.filter(user=userId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)
    

    serializer_context = {"request": request}
    serializer = StoreSerializer(store, context=serializer_context, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view([methods["get"], methods["delete"]])
def schedules(request, storeId, productId):
    try:
        schedules = Schedule.objects.filter(store=storeId, productId=productId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    
    if request.method == methods["get"]:
        serializer = ScheduleSerializer(schedules)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == methods["delete"]:
        schedules.delete()
        return Response(status=status.HTTP_202_ACCEPTED)



def delete_specifications(request, productId):
    try:
        specification = Specification.objects.filter(product=productId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    specification.delete()
    return Response(status=status.HTTP_202_ACCEPTED)



def get_specifications(request, productId):
    try:
        specifications = Specification.objects.filter(product=productId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    
    serializer = SpecificationSerializer(specifications)
    return Response(serializer.data, status=status.HTTP_200_OK)


class ProductCreateView(ModelViewSet):

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class ProductImageViewSet(ModelViewSet):
    queryset = ProductImg.objects.all()
    serializer_class = ProductImgSerializer



def delete_product(request, storeId, productId):
    try:
        product = Product.objects.get(store=storeId, id=productId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    
    product.delete()
    return Response(status=status.HTTP_202_ACCEPTED)



def delete_schedule(request, storeId, productId):
    try:
        schedule = Schedule.objects.get(productId=productId, store=storeId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    schedule.delete()
    return Response(status=status.HTTP_202_ACCEPTED)



def add_schedule(request):
        data = JSONParser().parse(request)
        storeId = data.get("store")
        productId = data.get("productId")
        serializer = ScheduleSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        
        try:
                schedule = Schedule.objects.get(store=storeId, productId=productId)
        except:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

            # update schedule
        serializer = ScheduleSerializer(schedule, data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)



def get_schedule(request, storeId, productId):
    try:
        schedule = Schedule.objects.get(store=storeId, productId=productId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    
    serializer = ScheduleSerializer(schedule)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view([methods["put"]])
def edit_product(request, storeId, productId):
    data = JSONParser().parse(request)

    try:
        product = Product.objects.get(store=storeId, id=productId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    
    serializer = ProductSerializer(product, data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)
       


def get_store_product(request, storeId, productId):
    try:
        product = Product.objects.get(store=storeId, id=productId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    
    serializer = ProductSerializer(product)
    return Response(serializer.data, status=status.HTTP_201_CREATED)



def store_product_image(request, storeId, productId, imageId):
    try:
        product = ProductImg.objects.get(id=imageId, productId=productId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    
    serializer = ProductImgSerializer(product)
    return Response(serializer.data, status=status.HTTP_201_CREATED)



def store_product_images(request, storeId, productId):
    try:
        product = ProductImg.objects.filter(productId=productId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    
    serializer = ProductImgSerializer(product, many=True)
    return Response(serializer.data, status=status.HTTP_201_CREATED)



@parser_classes([MultiPartParser])
def store_add_product_image(request):
        data = request.data
        serializer = ProductImgSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
  


def create_specifications(request):
        data = JSONParser().parse(request)
        serializer = SpecificationSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    



def delete_file(request, productId, storeId, filename):
 

        ext = filename.split(".")[-1]
        filenamenoExt = filename.replace(f"{ext}", "")
        fileDir = "%s/%s.%s" % ("img", filenamenoExt, ext)
        if os.path.isfile((f"media/images/{filename}")):
            os.remove(fileDir)
            return Response(f"{filename} deleted", status=status.HTTP_202_ACCEPTED)
        return Response("file not found", status=status.HTTP_404_NOT_FOUND)


class IsOwnerSearchProduct(ListAPIView):

    serializer_class = ProductSerializer
    permission_classes = (EcommerceAccessPolicy,)

    filter_backends = [SearchFilter, OrderingFilter]
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

    ordering_fields = ["price", "average_rating", "discount"]

    def get_queryset(self):
        store = self.request.data["store"]
        return Product.objects.filter(store=store)
