from django.contrib import admin
from product.models import Product, Specification, ProductImg

# Register your models here.
admin.site.register(Product)
admin.site.register(Specification)
admin.site.register(ProductImg)
