from rest_framework import serializers

from product.models import ProductImg, Product, Specification

from taggit.serializers import TagListSerializerField, TaggitSerializer

from store.models import Store




class StoreInfoForProductCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["url", "name"]


class ProductImgSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImg
        fields = ["id", "product", "image",]


class SpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specification

        fields = ["product", "serial", "attributes", "height",
                  "width", "breadth", "weight", "color", "created", "updated",]


class ProductSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField()
    images = ProductImgSerializer(many=True, read_only=True)
    
    # uploaded_images = serializers.ListField(
    #     child=serializers.ImageField(max_length=1000000000,allow_empty_file=False, use_url=False),
    #     write_only=True
    # )
    # specifications = SpecificationSerializer(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "store",
            "title",
            "available",
            "discount",
            "description",
            "price",
            "sale_price",
            "visibility",
            "tags",
            "images",
            
            # "uploaded_images",
            "label",
            # "specifications"
        ]

        # def create(self, validated_data):
        #     uploaded_images = validated_data.pop("uploaded_images")
        #     product = Product.objects.create(**validated_data)
        #     for image in uploaded_images:
        #         ProductImg.objects.create(product=product, image=image)
        #     return product


class ProductCardSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product

        fields = [
            "id",
            "title",
            "available",
            "discount",
            "label",
            "price",
            "sale_price",
            "average_rating",
        ]
