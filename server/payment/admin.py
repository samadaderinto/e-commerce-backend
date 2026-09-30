from django.contrib import admin

# Register your models here.
from payment.models import Coupon, Order, Payment, DeliveryInfo

# Register your models here.
admin.site.register(Payment)
admin.site.register(Coupon)
admin.site.register(Order)
admin.site.register(DeliveryInfo)