from django.contrib import admin

from store.models import Schedule, StoreAddress, StoreImg, StoreInfo, Store

# Register your models here.

admin.site.register(StoreAddress)
admin.site.register(StoreImg)
admin.site.register(StoreInfo)
admin.site.register(Schedule)
admin.site.register(Store)
