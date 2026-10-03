from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.permissions import AllowAny
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from .views import (
    AddressesView, AuthView, CartView, CheckoutView, CouponAdminView, MeView, OrderDetailView,
    OrderRefundView, ShippingRatesView, WalletCheckoutConfirmView, WalletCheckoutSessionView,
    OrdersView, ProductDetailView, ProductsView, ReviewsView, WishlistView,
)
from store.views import StoreReviewViewSet
from staff.views import StaffViewSet

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('observability.urls')),
    path('api/schema/', SpectacularAPIView.as_view(permission_classes=[AllowAny], authentication_classes=[]), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema', permission_classes=[AllowAny], authentication_classes=[]), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema', permission_classes=[AllowAny], authentication_classes=[]), name='redoc'),
    path('api/v1/auth/<str:action>/', AuthView.as_view()),
    path('api/v1/me/', MeView.as_view()),
    path('api/v1/products/', ProductsView.as_view()),
    path('api/v1/products/<int:pk>/', ProductDetailView.as_view()),
    path('api/v1/products/<int:pk>/reviews/', ReviewsView.as_view()),
    path('api/v1/wishlist/', WishlistView.as_view()),
    path('api/v1/addresses/', AddressesView.as_view()),
    path('api/v1/cart/', CartView.as_view()),
    path('api/v1/checkout/', CheckoutView.as_view()),
    path('api/v1/checkout/shipping-rates/', ShippingRatesView.as_view()),
    path('api/v1/checkout/wallet-session/', WalletCheckoutSessionView.as_view()),
    path('api/v1/checkout/wallet-confirm/', WalletCheckoutConfirmView.as_view()),
    path('api/v1/admin/coupons/', CouponAdminView.as_view()),
    path('api/v1/admin/stores/', StoreReviewViewSet.as_view({'get': 'list'})),
    path('api/v1/admin/stores/<int:pk>/approve/', StoreReviewViewSet.as_view({'post': 'approve'})),
    path('api/v1/admin/stores/<int:pk>/block/', StoreReviewViewSet.as_view({'post': 'block'})),
    path('api/v1/admin/staff/', StaffViewSet.as_view({'get': 'staffs', 'post': 'staffs'})),
    path('api/v1/admin/staff/<int:staff_pk>/', StaffViewSet.as_view({'get': 'staff_detail'})),
    path('api/v1/admin/staff/<int:staff_pk>/block/', StaffViewSet.as_view({'post': 'block_staff'})),
    path('api/v1/admin/staff/<int:staff_pk>/unblock/', StaffViewSet.as_view({'post': 'unblock_staff'})),
    path('api/v1/notifications/', include('notification.urls')),
    path('api/v1/orders/', OrdersView.as_view()),
    path('api/v1/orders/<int:pk>/', OrderDetailView.as_view()),
    path('api/v1/orders/<int:pk>/refund/', OrderRefundView.as_view()),
    path('api/v1/stores/', include('store.urls')),
]
if settings.LOCAL_PROFILING_ENABLED:
    urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
