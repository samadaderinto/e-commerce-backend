from django.contrib import admin


# Register your models here.


from core.models import Address, DeliveryInfo, Recent, Review, User, Wishlist 

# Register your models here.

admin.site.register(User)

# admin.site.register(CartItem)
admin.site.register(Wishlist)
admin.site.register(Recent)

admin.site.register(Review)

admin.site.register(DeliveryInfo)
admin.site.register(Address)

