import os
from django.db import transaction
from django.db.models import Count, Prefetch
from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, get_list_or_404

from store.models import Store
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework import viewsets


from core.models import Review, Wishlist

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

from product.cache import (
    PRODUCT_CACHE_TIMEOUT, LANDING_PRODUCTS_CACHE_KEY, product_cache_key,
    store_product_cache_key, invalidate_product_cache, get_cached_product_data,
    get_cached_store_product_data, get_cached_landing_products,
)

class ProductViewSet(viewsets.GenericViewSet):
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
        invalidate_product_cache(product_image.product)
        product_image.delete()
        return Response(status=status.HTTP_202_ACCEPTED)

    # you will also need to request further permissions by emailing uspstechnicalsupport@mailps.custhelp.com about Label API access.
    # get labelzpi and change value in constants.py

    def get_product(self, request, productId):
        cached_product = cache.get(product_cache_key(productId))
        if cached_product is not None and not request.user.is_authenticated:
            return Response(cached_product, status=status.HTTP_200_OK)

        products = Product.objects.filter(
            visibility=True,
        ).annotate(
            likes_count=Count("wishlist", distinct=True)
        ).prefetch_related("images")
        if request.user.is_authenticated:
            products = products.prefetch_related(
                Prefetch(
                    "wishlist_set",
                    queryset=Wishlist.objects.filter(user=request.user),
                    to_attr="user_likes",
                )
            )
        product = get_object_or_404(products, id=productId)

        
        serializer = ProductSerializer(product, context={"request": request})
        related_products = Product.objects.filter(
                category=product.category,
                visibility=True,
            ).exclude(id=product.id)[:5]
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

                    data = serializer.data
                    data['label'] = label.result
                    return Response(data, status=status.HTTP_200_OK)
        data = get_cached_product_data(product.id)
        cache.set(product_cache_key(product.id), data, PRODUCT_CACHE_TIMEOUT)
        return Response(data, status=status.HTTP_200_OK)


    def delete_product(self, request, productId):
        product = get_object_or_404(Product, id=productId)
        invalidate_product_cache(product)
        product.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


    def get_reviews(self, request, productId):
        from core.serializers import ReviewsSerializer

        reviews = get_list_or_404(Review, product=productId)

        page_number = request.GET.get('offset', 1)
        per_page = request.GET.get('limit', 15)
        paginator = Paginator(reviews, per_page=per_page)
        items = paginator.get_page(number=page_number)
        serializer = ReviewsSerializer(items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


    def landing_page_products(self, request):
            cached_products = cache.get(LANDING_PRODUCTS_CACHE_KEY)
            if cached_products is not None:
                return Response(cached_products, status=status.HTTP_200_OK)

            data = get_cached_landing_products()
            cache.set(LANDING_PRODUCTS_CACHE_KEY, data, PRODUCT_CACHE_TIMEOUT)
            return Response(data, status=status.HTTP_200_OK)
            
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
    @action(detail=False, methods=['get'], url_path='specifications/get')
    def get_specifications(self, request, product):
        try:
            specifications = self.product_specification.objects.filter(product=product)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        
        serializer = SpecificationSerializer(specifications, many=True)
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

        
        invalidate_product_cache(product)
        product.delete()
        return Response(status=status.HTTP_202_ACCEPTED)



    @extend_schema(request=ProductSerializer, responses={status.HTTP_200_OK: dict})
    @action(detail=False, methods=['put', 'patch'], url_path='product/update')
    def edit_product(self, request, storeId, productId):
        data = JSONParser().parse(request)

        try:
            product = self.store_product.objects.get(store=storeId, id=productId, store__user=request.user)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        
        serializer = ProductSerializer(product, data=data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        invalidate_product_cache(product)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        

    @extend_schema(request=ProductSerializer, responses={status.HTTP_200_OK: dict})
    @action(detail=False, methods=['get'], url_path='product/get')
    def get_store_product(self, request, storeId, productId):
        cached_product = cache.get(store_product_cache_key(storeId, productId))
        if cached_product is not None:
            return Response(cached_product, status=status.HTTP_200_OK)

        try:
            product = self.store_product.objects.get(
                store=storeId,
                id=productId,
                visibility=True,
            )
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        
        data = get_cached_store_product_data(storeId, productId)
        cache.set(
            store_product_cache_key(storeId, productId),
            data,
            PRODUCT_CACHE_TIMEOUT,
        )
        return Response(data, status=status.HTTP_200_OK)



    def store_product_image(self, request, storeId, product, image):
        try:
            product = ProductImg.objects.get(id=image, product=product)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        
        serializer = ProductImgSerializer(product)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



    def store_product_images(self, request, storeId, productId):
        try:
            product = ProductImg.objects.filter(product=productId)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

        
        serializer = ProductImgSerializer(product, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



    @parser_classes([MultiPartParser])
    def store_add_product_image(self, request):
            data = request.data
            serializer = ProductImgSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            product_image = serializer.save()
            invalidate_product_cache(product_image.product)
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

    search_fields = (
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
        return Product.objects.filter(
            visibility=True,
        ).annotate(
            likes_count=Count("wishlist", distinct=True)
        )

    def get_serializer_context(self):
        return {'request': self.request}
    
class IsOwnerSearchProduct(ListAPIView):

        serializer_class = ProductSerializer
    

        filter_backends = [SearchFilter, OrderingFilter]
        search_fields = (
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
