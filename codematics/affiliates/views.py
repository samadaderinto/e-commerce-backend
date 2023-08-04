# Create your views here.
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework import status


from affiliates.models import Marketer, Url
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
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["patch"]])
@permission_classes((EcommerceAccessPolicy,))
def edit_marketer_detail(request, userId):
    data = JSONParser().parse(request)

    try:
        marketer = Marketer.objects.get(pk=userId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["patch"]:
        serializer = MarketerSerializer(marketer, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_marketer_account(request, userId):
    try:
        marketer = Marketer.objects.get(pk=userId)

    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["delete"]:
        marketer.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_marketer(request, userId):
    try:
        marketer = Marketer.objects.get(pk=userId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = MarketerSerializer(marketer)

    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_product_link(request):
    if request.method == methods["get"]:
        data = JSONParser().parse(request)
        serializer = MarketerSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            url = Url.objects.get(
                user=serializer.validated_data["user"],
                marketer=serializer.validated_data["marketer"],
                product=serializer.validated_data["product"],
            )
            return Response(url.data["abs_url"], status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


