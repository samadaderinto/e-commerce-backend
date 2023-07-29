# Create your views here.
from django.shortcuts import redirect
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework import status
from affiliates.models import Marketer
from affiliates.serializers import MarketerSerializer

from core.permissions import EcommerceAccessPolicy
from core.utilities import methods


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_marketer(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = MarketerSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


@api_view([methods["patch"]])
@permission_classes((EcommerceAccessPolicy,))
def edit_marketer_detail(request, userId):
    data = JSONParser().parse(request)

    try:
        marketer = Marketer.objects.get(pk=userId)
    except:
        return Response(status=404)

    if request.method == methods["patch"]:
        serializer = MarketerSerializer(marketer, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_marketer_account(request, userId):
    try:
        marketer = Marketer.objects.get(pk=userId)

    except:
        return Response(status=404)

    if request.method == methods["delete"]:
        marketer.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_marketers(request):
    try:
        marketer = Marketer.objects.all().order_by("created").reverse()
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = MarketerSerializer(marketer, many=True)
        return Response(serializer.data, safe=False)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_marketer(request, userId):
    try:
        marketer = Marketer.objects.get(pk=userId)
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = MarketerSerializer(marketer)

    return Response(serializer.data, status=201)



@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_link(request):
    
    if request.method == methods["get"]:
        data = JSONParser().parse(request)
        serializer = MarketerSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data.get("abs_url"), status=201)
        return Response(serializer.errors, status=404)
    
    
    