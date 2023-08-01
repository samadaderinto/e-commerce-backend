from rest_framework import serializers
from cart.models import Cart, CartItem
from product.serializers import ProductSerializer

from product.models import ProductImg, Product


from nanoid import generate

from store.models import Store



class CartProductInfoSerializer(serializers.ModelSerializer):
    # store_details = StoreInfoForProductCardSerializer(source="store")

    class Meta:
        model = Product
        fields = ["id", "title", "available", "discount", "price"]

class CartProductInfoSerializer(serializers.ModelSerializer):
    # store_details = StoreInfoForProductCardSerializer(source="store")

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "available",
            "discount",
            "price",
        ]


class CartItemSerializer(serializers.ModelSerializer):
    product = CartProductInfoSerializer(source="productId")
    sub_total = serializers.SerializerMethodField(method_name="total")

    class Meta:
        model = CartItem
        fields = ["cartId", "product", "quantity", "sub_total"]

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
            cart_item = CartItem.objects.get(productId=product_id, cart_id=cart_id)
            cart_item.quantity += quantity
            cart_item.save()

            self.instance = cart_item
        except:
            self.instance = CartItem.objects.create(
                productId=product_id, cart_id=cart_id, quantity=quantity
            )

        return self.instance

    class Meta:
        model = CartItem
        fields = ["id", "productId", "quantity"]


class CartSerializer(serializers.ModelSerializer):
    id = serializers.CharField(default=generate(size=15), read_only=True)

    class Meta:
        model = Cart
        fields = ["id", "userId", "created"]


class JoinCartSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source="productId")

    class Meta:
        model = CartItem
        fields = ["cartId", "productId", "quantity", "product_details"]

