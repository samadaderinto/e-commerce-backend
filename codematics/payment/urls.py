from django.urls import path

from payment.views import capture_checkout_session, create_checkout_session, redeem_coupon

urlpatterns = [
    path("coupons/reedeem/", redeem_coupon, name="products"),


    path('refunds/', redeem_coupon),
    path('refunds/<int:orderId>/', redeem_coupon),
    path('refund/request/', redeem_coupon),
    path('refund/request/response/', redeem_coupon),




    path('payment/stripe/create/order/',
         create_checkout_session, name='create_cardless_order'),
    path('payment/stripe/capture/order/',
         capture_checkout_session, name='create_cardless_order'),

#     path('payment/paypal/create/order/',
#          create_checkout_session, name='create_cardless_order'),
#     path('payment/paypal/capture/order/',
#          capture_checkout_session, name='capture_cardless_order')
]
