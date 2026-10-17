from django.contrib import admin
from django.forms import ModelForm
from django.http import HttpRequest
from django.db.models import QuerySet
from core.models import Address, Recent, Review, User, Wishlist, Device, Refund
from product.models import Product


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
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'user', 'rating', 'created', 'updated')
    list_filter = ('rating', 'created')
    search_fields = ('product__title', 'user__email', 'label', 'comment')

    def save_model(
        self,
        request: HttpRequest,
        obj: Review,
        form: ModelForm,
        change: bool,
    ) -> None:
        super().save_model(request, obj, form, change)
        obj.set_avg_rating()

    def delete_model(self, request: HttpRequest, obj: Review) -> None:
        product = obj.product
        super().delete_model(request, obj)
        Review(product=product).set_avg_rating()

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[Review]) -> None:
        product_ids = set(queryset.values_list('product_id', flat=True))
        super().delete_queryset(request, queryset)
        for product in Product.objects.filter(pk__in=product_ids):
            Review(product=product).set_avg_rating()
admin.site.register(Address)
admin.site.register(Device)
admin.site.register(Refund)
