from django.contrib import admin

# Register your models here.
from payment.models import Coupon, Order, Payment, DeliveryInfo, TaxJurisdiction

admin.site.register(Payment)
admin.site.register(Coupon)
admin.site.register(Order)
admin.site.register(DeliveryInfo)


@admin.register(TaxJurisdiction)
class TaxJurisdictionAdmin(admin.ModelAdmin):
    list_display = ('name', 'state', 'postal_code', 'rate', 'tax_shipping', 'tax_digital', 'is_active')
    list_filter = ('is_active', 'tax_shipping', 'tax_digital', 'country', 'state')
    search_fields = ('name', 'state', 'postal_code')
    list_editable = ('rate', 'is_active', 'tax_shipping', 'tax_digital')