from rest_framework import serializers

from cart.models import CartItem,Store,Specifications,ProductImg,Product,Cart


import django_filters

from taggit.serializers import (TagListSerializerField,
                                TaggitSerializer)

from nanoid import generate
class StoreInfoForProductCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["url",
                  "name"]


class ProductImgSerializer(serializers.ModelSerializer):
    class Meta:
       
        model = ProductImg
        field = ["id",
                 "productId",
                 "image"]


class CartProductInfoSerializer(serializers.ModelSerializer):
    # store_details = StoreInfoForProductCardSerializer(source="store")

    class Meta:
        model = Product
        fields = ["id",
                  "title",
                  "available",
                  "discount",
                  "price"]

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
]

        def create(self, validated_data):
            uploaded_images = validated_data.pop("uploaded_images")
            product = Product.objects.create(**validated_data)
            for image in uploaded_images:
                ProductImg.objects.create(
                    product=product, image=image)
            return product


class ProductCardSerializer(serializers.ModelSerializer):
    # store_details = StoreInfoForProductCardSerializer(source="store")
    image = ProductImgSerializer(many=True, read_only=True)
    
    related_products = RelatedProductSerializer(many=True,read_only=True)

    class Meta:
        model = Product
        fields = ["id",
                  "title",
                  "available",
                  "discount",
                  "image",
                  "price",
                  "average_rating",
                  "related_products"
                  ]


class CartProductInfoSerializer(serializers.ModelSerializer):
    # store_details = StoreInfoForProductCardSerializer(source="store")

    class Meta:
        model = Product
        fields = ["id",
                  "title",
                  "available",
                  "discount",
                  "price",
                  ]


class ProductPriceRangeFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name="price",
                                            lookup_expr='gt', widget=django_filters.widgets.RangeWidget(attrs={'placeholder': 'min_price'}))
    max_price = django_filters.NumberFilter(field_name="price",
                                            lookup_expr='lt', widget=django_filters.widgets.RangeWidget(attrs={'placeholder': 'max_price'}))

    class Meta:
        model = Product
        fields = ['min_price', 'max_price']


class CartItemSerializer(serializers.ModelSerializer):
    product = CartProductInfoSerializer(source="productId")
    sub_total = serializers.SerializerMethodField(method_name="total")

    class Meta:
        model = CartItem
        fields = ["cartId",
                  "product",
                  'quantity',
                  "sub_total"]

    def total(self, cartitem: CartItem):
        return cartitem.quantity * cartitem.productId.price


class AddToCartSerializer(serializers.ModelSerializer):

    def validate_productId(self, value):
        if not Product.objects.filter(pk=value).exists():
            return serializers.ValidationError("There is no product with given id")
        return value

    def save(self, **kwargs):
        cart_id = self.context["cartId"]
        product_id = self.validated_data["productId"]
        quantity = self.validated_data["quantity"]

        try:
            cart_item = CartItem.objects.get(
                productId=product_id, cart_id=cart_id)
            cart_item.quantity += quantity
            cart_item.save()

            self.instance = cart_item
        except:
            self.instance = CartItem.objects.create(
                productId=product_id, cart_id=cart_id, quantity=quantity)

        return self.instance

    class Meta:
        model = CartItem
        fields = ["id",
                  "productId",
                  "quantity"]


class CartSerializer(serializers.ModelSerializer):
    id = serializers.CharField(default=generate(
        size=15), read_only=True)

    class Meta:
        model = Cart
        fields = ["id",
                  "userId",
                  "created"]


class JoinCartSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source="productId")

    class Meta:
        model = CartItem
        fields = ["cartId",
                  "productId",
                  "quantity",
                  "product_details"]
        
class SpecificationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Specifications
        fields = ["__all__"]        
