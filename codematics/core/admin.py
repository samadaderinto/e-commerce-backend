from django.contrib import admin
from core.models import Address, Recent, Review, User, Wishlist , Device, Refund






admin.site.register(User)
admin.site.register(Wishlist)
admin.site.register(Recent)
admin.site.register(Review)
admin.site.register(Address)
admin.site.register(Device)
admin.site.register(Refund)
