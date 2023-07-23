from django.contrib import admin

from payment.models import Coupon, Order, Payment

# Register your models here.
admin.site.register(Payment)
admin.site.register(Coupon)
admin.site.register(Order)



