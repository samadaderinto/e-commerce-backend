# Create your views here.

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework import status

from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema

from affiliates.models import Marketer, Url
from affiliates.serializers import MarketerSerializer, RedirectSerializer


class AffiliatesViewSet:
    
    @extend_schema(request=MarketerSerializer, responses={status.HTTP_201_CREATED: MarketerSerializer})
    @action(detail=False, methods=['post'], url_path='register')
    def create_marketer(request):
        
        data = JSONParser().parse(request)
        serializer = MarketerSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    
    @extend_schema(request=MarketerSerializer, responses={status.HTTP_201_CREATED: MarketerSerializer})
    @action(detail=False, methods=['post'], url_path='update')
    def edit_marketer_detail(request, userId):
        data = JSONParser().parse(request)
        
        marketer = get_object_or_404(Marketer, id=userId)

        serializer = MarketerSerializer(marketer, data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        

    @extend_schema(request=MarketerSerializer, responses={status.HTTP_201_CREATED: MarketerSerializer})
    @action(detail=False, methods=['post'], url_path='delete')
    def delete_marketer_account(request, userId):
        marketer = get_object_or_404(Marketer, id=userId)
        marketer.delete()
        return Response(status=status.HTTP_202_ACCEPTED)

    
    @extend_schema(request=MarketerSerializer, responses={status.HTTP_201_CREATED: MarketerSerializer})
    @action(detail=False, methods=['post'], url_path='get')
    def get_marketer(request, userId):
        marketer = get_object_or_404(Marketer, id=userId)


        serializer = MarketerSerializer(marketer)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    
    @extend_schema(request=MarketerSerializer, responses={status.HTTP_201_CREATED: MarketerSerializer})
    @action(detail=False, methods=['post'], url_path='product_id/generate')
    def get_product_link(request):
        
        data = JSONParser().parse(request)
        serializer = MarketerSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        url = Url.objects.get(
                user=serializer.validated_data["user"],
                marketer=serializer.validated_data["marketer"],
                product=serializer.validated_data["product"],
            )
        return Response(url.data["abs_url"], status=status.HTTP_201_CREATED)
        

    @extend_schema(request=MarketerSerializer, responses={status.HTTP_201_CREATED: MarketerSerializer})
    @action(detail=False, methods=['post'], url_path='get')
    def redirect_url(request, marketerId, productId, identifier):
        data = JSONParser().parse(request)
        serializer = RedirectSerializer(data=data)

        serializer.is_valid(raise_exception=True)
        url = get_object_or_404(Url, marketer=marketerId, product=productId, identifier=identifier)
    

        serializer.save()
        return redirect(
                url.product_url,
                permanent=True,
                status=status.HTTP_308_PERMANENT_REDIRECT
            )

