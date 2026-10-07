from django.contrib import admin
from core.models import Address, Recent, Review, User, Wishlist , Device, Refund


@admin.register(User)
class ProtectedUserAdmin(admin.ModelAdmin):
    exclude = ('staff_invitation_secret',)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_superuser=False, is_business_admin=False)

    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_superuser and (obj is None or not (obj.is_superuser or obj.is_business_admin)))

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    def has_add_permission(self, request):
        return False

admin.site.register(Wishlist)
admin.site.register(Recent)
admin.site.register(Review)
admin.site.register(Address)
admin.site.register(Device)
admin.site.register(Refund)
