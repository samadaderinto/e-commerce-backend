from rest_framework import serializers
from cart.models import Cart, CartItem
from product.serializers import ProductCardSerializer



class CartItemSerializer(serializers.ModelSerializer):
    product = ProductCardSerializer()
    price = serializers.SerializerMethodField(method_name="main_total")

    class Meta:
        model = CartItem
        fields = ('id', 'product', 'quantity', "price")

    def main_total(self, cartItem):

        total = sum(
            [item.quantity * item.product.price for item in cartItem.__class__.objects.filter(id=cartItem)])
        return total


class CartSerializer(serializers.ModelSerializer):
    cart_items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField(method_name="main_total")

    class Meta:
        model = Cart
        fields = ('id', "cart_items", "total", "ordered", 'created')

    def main_total(self, cart):

        total = sum(
            [item.quantity * item.product.price for item in CartItem.objects.filter(cart=cart)])
        return total
