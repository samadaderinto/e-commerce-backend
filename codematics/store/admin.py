from django.contrib import admin

from store.models import Schedule, StoreAddress, StoreImg, StoreInfo, Store, Wallet, Budget

# Register your models here.

admin.site.register(StoreAddress)
admin.site.register(StoreImg)
admin.site.register(StoreInfo)
admin.site.register(Schedule)
admin.site.register(Store)
admin.site.register(Wallet)
admin.site.register(Budget)
