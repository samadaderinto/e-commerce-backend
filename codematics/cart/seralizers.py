from rest_framework import serializers
from cart.models import Cart, CartItem

from product.models import Product


from nanoid import generate





class CartProductInfoSerializer(serializers.ModelSerializer):
    

    class Meta:
       
        model = Cart
        fields = ["id", "userId", "items","grand_total","created"]


        
        
class CartItemSerializer(serializers.ModelSerializer):
    product = CartProductInfoSerializer()
    sub_total = serializers.SerializerMethodField(method_name="total")

    class Meta:
        model = CartItem
        fields = ["cart_id", "product", "quantity", "sub_total"]

    def total(self, cartitem: CartItem):
        return cartitem.quantity * cartitem.productId.price


class AddToCartSerializer(serializers.ModelSerializer):
    def validate(self,value):
        if not Product.objects.filter(pk=value.get("productId").pk).exists():
            return serializers.ValidationError("There is no product with given id")
        return value

    def save(self, **kwargs):
        cart_id = self.validated_data.get("cart_id")
        product_id = self.validated_data["productId"]
        quantity = self.validated_data["quantity"]

        try:
            cart_item = CartItem.objects.get(productId=product_id, cart_id=cart_id)
            cart_item.quantity += 1
            cart_item.save()

            self.instance = cart_item
        except:
            self.instance = CartItem.objects.create(
                productId=product_id, cart_id=cart_id, quantity=quantity
            )

        return self.instance

    class Meta:
        model = CartItem
        fields = ["cart_id", "productId", "quantity"]


class CartSerializer(serializers.ModelSerializer):
    cart_id = serializers.CharField(default=generate(size=15), read_only=True)
    # # items = CartItemSerializer(source="id",many=True,read_only=True)
    # grand_total = serializers.SerializerMethodField(method_name="main_total")
    
    class Meta:
        model = Cart
        fields = ["cart_id", "userId", "created"]
        
    # def main_total(self, cart: Cart):
    #     items = cart.objects.all()
    #     total = sum([item.quantity * item.product.price for item in items])
    #     return total 



