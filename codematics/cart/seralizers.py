from rest_framework import serializers
from cart.models import Cart, CartItem
from product.serializers import ProductCardSerializer


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductCardSerializer()
    total = serializers.SerializerMethodField(method_name="main_total")

    class Meta:
        model = CartItem
        fields = ('id', 'product', 'quantity', "total")

    def main_total(self, cartItem):
        return sum([item.quantity * item.product.price for item in cartItem.__class__.objects.filter(id=cartItem)])
       


class CartSerializer(serializers.ModelSerializer):
    cart_items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField(method_name="main_total")

    class Meta:
        model = Cart
        fields = ('id', "cart_items", "total", "ordered", 'created')

    def main_total(self, cart):

        return sum([item.quantity * item.product.price for item in CartItem.objects.filter(cart=cart)])

