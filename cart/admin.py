from django.contrib import admin


from cart.models import Cart, CartItem, Product, ProductImg, Specifications



# Register your models here.
admin.site.register(Product)
admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(Specifications)
admin.site.register(ProductImg)



