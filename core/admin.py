from django.contrib import admin
from core.models import Address, DeliveryEstimates, DeliveryInfo, Recent, Refund, Review, User, Wishlist 

# Register your models here.
admin.site.register(User)

admin.site.register(Wishlist)
admin.site.register(Recent)

admin.site.register(Review)
admin.site.register(Refund)
admin.site.register(DeliveryInfo)
admin.site.register(Address)
admin.site.register(DeliveryEstimates)



