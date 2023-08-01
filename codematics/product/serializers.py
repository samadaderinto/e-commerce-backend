from rest_framework import serializers

from product.models import ProductImg, Product, Specification


from taggit.serializers import TagListSerializerField, TaggitSerializer

from nanoid import generate

from store.models import Store


class StoreInfoForProductCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["url", "name"]


class RelatedProductSerializer(serializers.Serializer):
    url = serializers


class ProductImgSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImg
        fields = ["id", "productId", "image"]


class ProductSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField()
    images = ProductImgSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(
            max_length=10000, allow_empty_file=False, use_url=False
        ),
        # crucial code may change later
        # unable to upload image succesfully
        read_only=True,
    )

    # related_products = RelatedProductSerializer(many=True, read_only=True)

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
            "visibility",
            "tags",
            "images",
            "uploaded_images",
            "usps_delivery_date",
            "usps_service"
            # "related_products"
        ]

        def create(self, validated_data):
            uploaded_images = validated_data.pop("uploaded_images")

            product = Product.objects.create(**validated_data)
            for image in uploaded_images:
                ProductImg.objects.create(product=product, image=image)
            return product


class ProductCardSerializer(serializers.ModelSerializer):
    # image = ProductImgSerializer(source="productId",)

    class Meta:
        model = Product

        fields = [
            "id",
            "title",
            "available",
            "discount",
            # "image",
            "price",
            "average_rating",
        ]



class SpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specification
        fields = ["__all__"]
