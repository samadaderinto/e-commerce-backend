from rest_framework import serializers
from cart.models import Cart, CartItem
from product.serializers import ProductCardSerializer


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductCardSerializer()
    total = serializers.SerializerMethodField(method_name="main_total")

    class Meta:
        model = CartItem
        fields = ('id', 'product', 'variant', 'quantity', "total")

    def main_total(self, cartItem):
        from storefront.serializers import unit_price
        return cartItem.quantity * unit_price(cartItem.product, cartItem.variant)
       


class CartSerializer(serializers.ModelSerializer):
    cart_items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField(method_name="main_total")

    class Meta:
        model = Cart
        fields = ('id', "cart_items", "total", "ordered", 'created')

    def main_total(self, cart):

        from storefront.serializers import unit_price
        return sum(item.quantity * unit_price(item.product, item.variant) for item in CartItem.objects.filter(cart=cart))
