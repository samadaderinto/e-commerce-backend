import stripe
import six
from decimal import Decimal

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.conf import settings
from django.template.loader import get_template

from notification.delivery import queue_email_delivery
from rest_framework_simplejwt.tokens import RefreshToken



def auth_token(user):
    refresh = RefreshToken.for_user(user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def send_mail(file_name, reciever_email, data=None):
    html_tpl_path = f"email-templates/{file_name}.html"
    email_html_template = get_template(html_tpl_path).render(data or {})
    sender = getattr(settings, "APPLICATION_EMAIL", settings.DEFAULT_FROM_EMAIL)
    queue_email_delivery(
        reciever_email,
        f"Proace: {file_name.replace('-', ' ').title()}",
        email_html_template,
        reply_to=sender,
        is_html=True,
    )
    

def make_payment(items, total, coupon_discount):
    total = Decimal(str(total))
    coupon_discount = Decimal(str(coupon_discount))
    return stripe.checkout.Session.create(
        payment_method_types=['card', "cashapp", 'access_debit'],
        line_items=[
            {
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': item.product.title,
                    },
                    'unit_amount': int(Decimal(str(item.product.sale_price)) * 100),
                },
                'quantity': item.quantity,
            } for item in items
        ],
        discounts=[],
        mode='payment',
        success_url='http://localhost:3000/success/',
        cancel_url='http://localhost:3000/cancel/',
    )
    
    
class TokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):

        return (six.text_type(user.pk) + six.text_type(timestamp) + six.text_type(user.is_active))
