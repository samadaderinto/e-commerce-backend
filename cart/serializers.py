from rest_framework import serializers




from taggit.serializers import (TagListSerializerField,
                                TaggitSerializer)

from nanoid import generate

from cart.models import Specifications, ProductImg, Product



class ProductImgSerializer(serializers.ModelSerializer):
    class Meta:
       
        model = ProductImg
        field = ["id",
                 "productId",
                 "image"]




class RelatedProductSerializer(serializers.Serializer):
   
    url = serializers
    
class ProductSerializer(TaggitSerializer, serializers.ModelSerializer):
    # store_info = StoreInfoForProductCardSerializer(source="store",read_only=True)
    tags = TagListSerializerField()
    images = ProductImgSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(
            max_length=7, allow_empty_file=False, use_url=False),
        write_only=True)

    related_products = RelatedProductSerializer(many=True,read_only=True)
    class Meta:
        fields = ["id",  
                  "store",
                  "title",
                  "available",
                  "discount",
                  "description",
                  "price",
                  
                  "average_rating",
                  #   'store_info',
                  "product_visibility",
                  'tags',
                  "images",
                  "uploaded_images",
                  "related_products"]

        def create(self, validated_data):
            uploaded_images = validated_data.pop("uploaded_images")
            product = Product.objects.create(**validated_data)
            for image in uploaded_images:
                ProductImg.objects.create(
                    product=product, image=image)
            return product


class ProductCardSerializer(serializers.ModelSerializer):
    # store_details = StoreInfoForProductCardSerializer(source="store")
    image = ProductImgSerializer()

    class Meta:
        model = Product
        fields = ["id",
                  "title",
                  "available",
                  "discount",
                  "image",
                  "price",
                  "average_rating",
                  ]





# class ProductPriceRangeFilter(django_filters.FilterSet):
#     min_price = django_filters.NumberFilter(field_name="price",
#                                             lookup_expr='gt', widget=django_filters.widgets.RangeWidget(attrs={'placeholder': 'min_price'}))
#     max_price = django_filters.NumberFilter(field_name="price",
#                                             lookup_expr='lt', widget=django_filters.widgets.RangeWidget(attrs={'placeholder': 'max_price'}))

#     class Meta:
#         model = Product
#         fields = ['min_price', 'max_price']

        
class SpecificationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Specifications
        fields = ["__all__"]        
