from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.permissions import AllowAny
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from .views import (
    PasswordChangeView, AddressesView, AuthView, CartView, CheckoutView, CouponAdminView, MeView, MeAvatarView, OrderDetailView, DigitalDownloadView,
    OrderRefundView, OrderCancelView, OrderTrackingView, ShippingRatesView, UserWalletView, WalletCheckoutConfirmView, WalletCheckoutSessionView,
    OrdersView, ProductDetailView, ProductsView, PublicStoreView, PublicStoreImageView, PublicUserImageView, ReviewsView, WishlistView, WalletTopupSessionView, WalletTopupConfirmView,
    CouponValidateView, TaxJurisdictionAdminView, TaxJurisdictionDetailAdminView, TaxJurisdictionSeedDefaultsAdminView,
    WalletCheckoutCancelView, WalletTopupCancelView, StripeWebhookView,
)
from store.views import StoreReviewViewSet
from staff.views import StaffViewSet
from affiliates.workspace import ReferralWorkspaceView, AffiliateOperatorView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('observability.urls')),
    path('api/schema/', SpectacularAPIView.as_view(permission_classes=[AllowAny], authentication_classes=[]), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema', permission_classes=[AllowAny], authentication_classes=[]), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema', permission_classes=[AllowAny], authentication_classes=[]), name='redoc'),
    path('api/v1/auth/<str:action>/', AuthView.as_view()),
    path('api/v1/password/change/', PasswordChangeView.as_view()),
    path('api/v1/me/', MeView.as_view()),
    path('api/v1/me/avatar/', MeAvatarView.as_view()),
    path('api/v1/wallet/', UserWalletView.as_view()),
    path('api/v1/wallet/topup-session/', WalletTopupSessionView.as_view()),
    path('api/v1/wallet/topup-confirm/', WalletTopupConfirmView.as_view()),
    path('api/v1/wallet/topup-cancel/', WalletTopupCancelView.as_view()),
    path('api/v1/products/', ProductsView.as_view()),
    path('api/v1/products/<int:pk>/', ProductDetailView.as_view()),
    path('api/v1/products/<int:pk>/reviews/', ReviewsView.as_view()),
    path('api/v1/stores/<int:pk>/public/', PublicStoreView.as_view()),
    path('api/v1/stores/<int:pk>/public/images/<str:kind>/', PublicStoreImageView.as_view()),
    path('api/v1/users/<int:pk>/public/images/avatar/', PublicUserImageView.as_view()),
    path('api/v1/wishlist/', WishlistView.as_view()),
    path('api/v1/addresses/', AddressesView.as_view()),
    path('api/v1/addresses/<int:pk>/', AddressesView.as_view()),
    path('api/v1/cart/', CartView.as_view()),
    path('api/v1/checkout/', CheckoutView.as_view()),
    path('api/v1/checkout/validate-coupon/', CouponValidateView.as_view()),
    path('api/v1/checkout/shipping-rates/', ShippingRatesView.as_view()),
    path('api/v1/checkout/wallet-session/', WalletCheckoutSessionView.as_view()),
    path('api/v1/checkout/wallet-confirm/', WalletCheckoutConfirmView.as_view()),
    path('api/v1/checkout/wallet-cancel/', WalletCheckoutCancelView.as_view()),
    path('api/v1/checkout/stripe-webhook/', StripeWebhookView.as_view()),
    path('api/v1/stripe/webhook/', StripeWebhookView.as_view()),
    path('api/v1/affiliates/workspace/', ReferralWorkspaceView.as_view()),
    path('api/v1/admin/affiliates/', AffiliateOperatorView.as_view()),
    path('api/v1/affiliates/', include('affiliates.urls')),
    path('api/v1/admin/coupons/', CouponAdminView.as_view()),
    path('api/v1/admin/taxes/', TaxJurisdictionAdminView.as_view()),
    path('api/v1/admin/taxes/seed-defaults/', TaxJurisdictionSeedDefaultsAdminView.as_view()),
    path('api/v1/admin/taxes/<int:pk>/', TaxJurisdictionDetailAdminView.as_view()),
    path('api/v1/admin/stores/', StoreReviewViewSet.as_view({'get': 'list'})),
    path('api/v1/admin/stores/<int:pk>/approve/', StoreReviewViewSet.as_view({'post': 'approve'})),
    path('api/v1/admin/stores/<int:pk>/block/', StoreReviewViewSet.as_view({'post': 'block'})),
    path('api/v1/admin/staff/', StaffViewSet.as_view({'get': 'staffs', 'post': 'staffs'})),
    path('api/v1/admin/staff/<int:staff_pk>/', StaffViewSet.as_view({'get': 'staff_detail'})),
    path('api/v1/admin/staff/<int:staff_pk>/block/', StaffViewSet.as_view({'post': 'block_staff'})),
    path('api/v1/admin/staff/<int:staff_pk>/unblock/', StaffViewSet.as_view({'post': 'unblock_staff'})),
    path('api/v1/admin/staff/<int:staff_pk>/resend-verification/', StaffViewSet.as_view({'post': 'resend_staff_verification'})),
    path('api/v1/admin/staff/orders/', StaffViewSet.as_view({'get': 'orders'})),
    path('api/v1/admin/staff/orders/<int:order_pk>/status/', StaffViewSet.as_view({'post': 'override_order_status'})),
    path('api/v1/admin/staff/coupons/', StaffViewSet.as_view({'get': 'coupons', 'post': 'coupons'})),
    path('api/v1/admin/staff/coupons/<int:coupon_pk>/', StaffViewSet.as_view({'patch': 'coupon_detail', 'delete': 'coupon_detail'})),
    path('api/v1/admin/staff/refunds/', StaffViewSet.as_view({'get': 'refunds'})),
    path('api/v1/admin/staff/refunds/<int:refund_pk>/process/', StaffViewSet.as_view({'post': 'process_refund'})),
    path('api/v1/admin/staff/payouts/', StaffViewSet.as_view({'get': 'payouts'})),
    path('api/v1/admin/staff/payouts/<int:payout_pk>/process/', StaffViewSet.as_view({'post': 'process_payout'})),
    path('api/v1/admin/staff/commission-wallet/', StaffViewSet.as_view({'get': 'commission_wallet'})),
    path('api/v1/admin/staff/commission-wallet/withdraw/', StaffViewSet.as_view({'post': 'withdraw_commission'})),
    path('api/v1/admin/staff/', include('staff.urls')),
    path('api/v1/notifications/', include('notification.urls')),
    path('api/v1/orders/', OrdersView.as_view()),
    path('api/v1/orders/<int:pk>/', OrderDetailView.as_view()),
    path('api/v1/orders/<int:pk>/downloads/<int:product_pk>/', DigitalDownloadView.as_view()),
    path('api/v1/orders/<int:pk>/tracking/', OrderTrackingView.as_view()),
    path('api/v1/orders/<int:pk>/refund/', OrderRefundView.as_view()),
    path('api/v1/orders/<int:pk>/cancel/', OrderCancelView.as_view()),
    path('api/v1/stores/', include('store.urls')),
]

if settings.LOCAL_PROFILING_ENABLED:
    urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
