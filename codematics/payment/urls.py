from django.urls import path

from payment.views import capture_checkout_session, create_checkout_session

urlpatterns = [






    path('payment/stripe/create/order/',
         create_checkout_session, name='create_cardless_order'),
    path('payment/stripe/capture/order/',
         capture_checkout_session, name='create_cardless_order'),

#     path('payment/paypal/create/order/',
#          create_checkout_session, name='create_cardless_order'),
#     path('payment/paypal/capture/order/',
#          capture_checkout_session, name='capture_cardless_order')
]
