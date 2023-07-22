from django.contrib import admin

from cart.models import Product, Specifications, ProductImg, Cart,CartItem

# Register your models here.
admin.site.register(Product)
admin.site.register(Specifications)
admin.site.register(ProductImg)

admin.site.register(Cart)
admin.site.register(CartItem)