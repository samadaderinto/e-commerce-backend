import os
from django.db import transaction
from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, get_list_or_404

from store.models import Store
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import ListAPIView


from core.models import Review
from core.serializers import  ReviewsSerializer

from product.models import Product, ProductImg, Specification
from product.serializers import (
    ProductCardSerializer,
    ProductImgSerializer,
    ProductSerializer,
    SpecificationSerializer
)

from kink import di
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action

from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.decorators import api_view, parser_classes

from usps import USPSApi, Address as uspsAddress
from usps import SERVICE_PRIORITY, LABEL_ZPL

# Create your views here.


class ProductViewSet:
    user_store: Store = di[Store]
    product_specification: Specification = di[Specification]
    store_product: Product = di[Product]
    
    
    def get_images(self, request, productId):
        product_images = get_list_or_404(ProductImg, product=productId)
        serializer = ProductImgSerializer(product_images, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def get_image(self, request, id):
        product_image = get_object_or_404(ProductImg, product=id)
        serializer = ProductImgSerializer(product_image)
        return Response(serializer.data)

    def delete_image(self, request, id):
        product_image = get_object_or_404(ProductImg, product=id)
        product_image.delete()
        return Response(status=status.HTTP_202_ACCEPTED)

    # you will also need to request further permissions by emailing uspstechnicalsupport@mailps.custhelp.com about Label API access.
    # get labelzpi and change value in constants.py

    def get_product(self, request, productId):
        product = get_object_or_404(ProductImg, id=productId)

        
        serializer = ProductSerializer(product)
        related_products = Product.objects.filter(
                category=product.category, visibility=True
            ).exclude(id=id)[:5]
        if request.user.is_authenticated:
            usps = USPSApi(settings.USPS_USERNAME)
            to_address = uspsAddress(
                        name='Tobin Brown',
                        address_1='1234 Test Ave.',
                        city='Test',
                        state='NE',
                        zipcode='55555'
                    )

            from_address = uspsAddress(
                        name='Tobin Brown',
                        address_1='1234 Test Ave.',
                        city='Test',
                        state='NE',
                        zipcode='55555'
                    )
            validate_to_address = usps.validate_address(to_address)
            validate_from_address = usps.validate_address(from_address)
            weight = 10  # in ounce
            if validate_to_address.result and validate_from_address.result:
                    # this is to get estimate delivery date if user orders product in certain range of time
                    label = usps.create_label(
                        to_address, from_address, weight, SERVICE_PRIORITY, LABEL_ZPL
                    )

                    return Response(
                    serializer.data, {'label': label.result}, status=status.HTTP_200_OK
                )
        return Response(serializer.data, status=status.HTTP_200_OK)


    def delete_product(self, request, productId):
        product = get_object_or_404(Product, id=productId)
        product.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


    def get_reviews(self, request, productId):
        reviews = get_list_or_404(Review, productId=productId)

        page_number = request.GET.get('offset', 1)
        per_page = request.GET.get('limit', 15)
        paginator = Paginator(reviews, per_page=per_page)
        items = paginator.get_page(number=page_number)
        serializer = ReviewsSerializer(items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


    def landing_page_products(self, request):
        
            newest_products = Product.objects.order_by('created')[:10]
            highest_rated_products = Product.objects.order_by('average_rating')[:10]
            best_selling_products = Product.objects.order_by('sales')[:10]

            serialized_newest = ProductSerializer(newest_products, many=True)
            serialized_highest_rated = ProductSerializer(
                highest_rated_products, many=True
            )
            serialized_best_selling = ProductSerializer(
                best_selling_products, many=True
            )

            return Response(
                {
                    'newest_products': serialized_newest.data,
                    'highest_rated_products': serialized_highest_rated.data,
                    'best_selling_products': serialized_best_selling.data
                },
                status=status.HTTP_200_OK
            )
            
    @extend_schema(request=SpecificationSerializer, responses={status.HTTP_200_OK: dict})
    @action(detail=False, methods=['delete'], url_path='specifications/delete')
    def delete_specifications(self, request, product):
        try:
            specification = self.product_specification.objects.get(product=product)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        specification.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


    @extend_schema(request=SpecificationSerializer, responses={status.HTTP_200_OK: dict})
    @action(detail=False, methods=['delete'], url_path='specifications/delete')
    def get_specifications(self, request, product):
        try:
            specifications = self.product_specification.objects.filter(product=product)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        
        serializer = SpecificationSerializer(specifications)
        return Response(serializer.data, status=status.HTTP_200_OK)


    def create(self, request):

        queryset = self.store_product.objects.all()
        serializer_class = ProductSerializer
        

        def post(self, request, *args, **kwargs):
            return self.create(request, *args, **kwargs)


    @extend_schema(request=ProductSerializer, responses={status.HTTP_200_OK: dict})
    @action(detail=False, methods=['delete'], url_path='product/delete')
    def delete(self, request, store, product):
        try:
            product = self.store_product.objects.get(store=store, id=product)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        
        product.delete()
        return Response(status=status.HTTP_202_ACCEPTED)



    @extend_schema(request=ProductSerializer, responses={status.HTTP_200_OK: dict})
    @action(detail=False, methods=['delete'], url_path='product/update')
    def edit_product(self, request, storeId, productId):
        data = JSONParser().parse(request)

        try:
            product = self.store_product.objects.get(store=storeId, id=productId)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        
        serializer = ProductSerializer(product, data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        

    @extend_schema(request=ProductSerializer, responses={status.HTTP_200_OK: dict})
    @action(detail=False, methods=['delete'], url_path='product/get')
    def get_product(self, request, storeId, productId):
        try:
            product = self.store_product.objects.get(store=storeId, id=productId)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        
        serializer = ProductSerializer(product)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



    def store_product_image(self, request, storeId, product, image):
        try:
            product = ProductImg.objects.get(id=image, productId=product)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        
        serializer = ProductImgSerializer(product)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



    def store_product_images(self, request, storeId, productId):
        try:
            product = ProductImg.objects.filter(productId=productId)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        
        serializer = ProductImgSerializer(product, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



    @parser_classes([MultiPartParser])
    def store_add_product_image(self, request):
            data = request.data
            serializer = ProductImgSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
    


    def create_specifications(self, request):
            data = JSONParser().parse(request)
            serializer = SpecificationSerializer(data=data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        


    def delete_file(self, request, product, store, filename):

            ext = filename.split(".")[-1]
            filenamenoExt = filename.replace(f"{ext}", "")
            fileDir = "%s/%s.%s" % ("img", filenamenoExt, ext)
            if os.path.isfile((f"media/images/{filename}")):
                os.remove(fileDir)
                return Response(f"{filename} deleted", status=status.HTTP_202_ACCEPTED)
            return Response("file not found", status=status.HTTP_404_NOT_FOUND)



class SearchProductViewSet(ListAPIView):
    serializer_class = ProductCardSerializer

    search_field = (
        'title',
        'description',
        'category',
        'discount',
        'average_rating',
        'tags',
        'store',
        'price'
    )

    filter_backends = [SearchFilter, OrderingFilter]
    ordering_fields = ['price', 'average_rating', 'discount']

    def get_queryset(self):
        return get_list_or_404(Product, visibility=True)

    def get_serializer_context(self):
        return {'request': self.request}
    
class IsOwnerSearchProduct(ListAPIView):

        serializer_class = ProductSerializer
    

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
            return self.store_product.objects.filter(store=store)
