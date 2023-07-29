# Create your views here
import os
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import JSONParser,MultiPartParser
from rest_framework.decorators import api_view, permission_classes,parser_classes


from product.models import Product
from store.models import StoreInfo, StoreAddress, StoreImg, Schedule, Store


from core.permissions import EcommerceAccessPolicy
from core.utilities import methods
from product.serializers import ProductSerializer
from store.serializers import ScheduleSerializer, StoreSerializer


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_store(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = StoreSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_schedule(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = ScheduleSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(f"visible to be updated by {serializer.make_visible_at}")
        return Response(serializer.errors, status=400)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def edit_store_info(request, storeId):
    try:
        store = Store.objects.get(pk=storeId)
    except:
        return Response(status=404)

    if request.method == methods["delete"]:
        store.delete()
        return Response(status=201)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_store(request, storeId):
    try:
        store = Store.objects.get(id=storeId)
    except:
        return Response(status=404)

    if request.method == methods["delete"]:
        store.delete()
        return Response(status=201)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_store(request, userId):
    try:
        store = Store.objects.filter(user=userId)
    except:
        return Response(status=404)
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
        return Response(status=404)
    if request.method == methods["get"]:
        serializer = StoreSerializer(store, many=True)
        return Response(serializer.data,)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def store_products(request, store):
    try:
        product = Product.objects.filter(store=store)
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = ProductSerializer(product, many=True)
        return Response(serializer.data,)


@api_view([methods["get"], methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def schedule_visiblity(request, userId):
    try:
        schedules = Schedule.objects.filter(user=userId)
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = ScheduleSerializer(schedules)
        return Response(serializer.data)

    elif request.method == methods["delete"]:
        schedules.delete()
        return Response(status=201)

@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def specifications(request, userId):
    try:
        schedules = Schedule.objects.filter(user=userId)
    except:
        return Response(status=404)

    if request.method == methods["delete"]:
        schedules.delete()
        return Response(status=201)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_specifications(request, userId):
    try:
        schedules = Schedule.objects.filter(user=userId)
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = ScheduleSerializer(schedules)
        return Response(serializer.data)


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["post"]])
@parser_classes([MultiPartParser])
def create_product(request):
    if request.method == methods["post"]:
        data = request.data
        serializer = ProductSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["post"]])
def create_specifications(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = ProductSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_file(request, filename):
    if request.method == methods["get"]:
        ext = filename.split(".")[-1]
        filenamenoExt = filename.replace(f"{ext}", "")
        fileDir = "%s/%s.%s" % ("img", filenamenoExt, ext)
        if os.path.isfile((f"media/images/{filename}")):
            os.remove(fileDir)
            return Response(f"{filename} deleted")
        return Response("file not found")
