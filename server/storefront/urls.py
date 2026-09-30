from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from rest_framework.permissions import AllowAny
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from .views import (
    AddressesView, AuthView, CartView, CheckoutView, MeView, OrderDetailView,
    OrdersView, ProductDetailView, ProductsView, ReviewsView, WishlistView,
)

urlpatterns = [
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
    path('api/v1/orders/', OrdersView.as_view()),
    path('api/v1/orders/<int:pk>/', OrderDetailView.as_view()),
    path('api/v1/stores/', include('store.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
