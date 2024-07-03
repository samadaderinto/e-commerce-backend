import os

from utils.permissions import EcommerceAccessPolicy
from rest_framework import status
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.decorators import api_view, parser_classes
from rest_framework.filters import SearchFilter, OrderingFilter, BaseFilterBackend
from rest_framework_word_filter import FullWordSearchFilter
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView, GenericAPIView
from rest_framework import viewsets

from kink import di
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action

from product.models import Product, Specification, ProductImg
from store.models import StoreInfo, StoreAddress, StoreImg, Schedule, Store
from utils.variables import methods

from product.serializers import ProductSerializer, SpecificationSerializer, ProductImgSerializer
from store.serializers import ScheduleSerializer, StoreSerializer



class StoreViewSet(viewsets.GenericViewSet):
    user_store: Store = di[Store]
    product_specification: Specification = di[Specification]
    store_product: Product = di[Product]
    
    
    @extend_schema(request=StoreSerializer, responses={status.HTTP_200_OK: StoreSerializer})
    @action(detail=False, methods=['post'], url_path='create')
    def create_store(self, request):
        data = JSONParser().parse(request)
        serializer = StoreSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(responses={status.HTTP_202_ACCEPTED: None})
    @action(detail=False, methods=['post'], url_path='delete')
    def delete_store(self, request, store):
        try:
            store = self.user_store.objects.get(id=store)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        store.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


    @extend_schema(request=StoreSerializer, responses={status.HTTP_202_ACCEPTED: StoreSerializer})
    @action(detail=False, methods=['post'], url_path='add')
    def edit_store_info(self, request, store):
        data = JSONParser().parse(request)

        try:
            store = self.user_store.objects.get(id=store)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)


        serializer = StoreSerializer(store, data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


    @extend_schema(request=StoreSerializer, responses={status.HTTP_202_ACCEPTED: StoreSerializer})
    @action(detail=False, methods=['post'], url_path='/get')
    def get_stores(self, request, user):
        try:
            store = self.user_store.objects.filter(user=user)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)
        

        serializer_context = {"request": request}
        serializer = StoreSerializer(store, context=serializer_context, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


    
class VisibilityScheduleViewSet(viewsets.GenericViewSet):
    product_schedule : Schedule = di[Schedule]
    
    
    @extend_schema(request=ScheduleSerializer, responses={status.HTTP_200_OK: dict})
    @action(detail=False, methods=['post'], url_path='visibilty_schedule/add')
    def schedule_product_visibility(self, request):
        data = JSONParser().parse(request)
        serializer = ScheduleSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(f"visible will be updated by {serializer.make_visible_at}", status.HTTP_200_OK)
    
    
    @extend_schema(request=ScheduleSerializer, responses={status.HTTP_200_OK: dict})
    @action(detail=False, methods=['get'], url_path='visibilty_schedule/get')
    def schedules(self, request, store, product):
        try:
            schedules = self.product_schedule.objects.filter(store=store, product=product)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        
        if request.method == methods["get"]:
            serializer = ScheduleSerializer(schedules, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        
    @extend_schema(request=ScheduleSerializer, responses={status.HTTP_200_OK: dict})
    @action(detail=False, methods=['get'], url_path='visibilty_schedule/delete')
    def delete_schedule(self, request, store, product):
        try:
            schedule = self.product_schedule.objects.get(product=product, store=store)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        schedule.delete()
        
        return Response(status=status.HTTP_202_ACCEPTED)
    
    
    def add_schedule(self, request):
            data = JSONParser().parse(request)
            serializer = ScheduleSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            store = serializer.validated_data["store"]
            product = serializer.validated_data["product"]
            
            try:
                schedule = self.product_schedule.objects.get(store=store, productId=product)
            except:
                
                serializer.save()
                return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


    def get_schedule(self, request, store, product):
        try:
            schedule = self.product_schedule.objects.get(store=store, productId=product)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        
        serializer = ScheduleSerializer(schedule)
        return Response(serializer.data, status=status.HTTP_200_OK)