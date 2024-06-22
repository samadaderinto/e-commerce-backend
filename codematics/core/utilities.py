from datetime import datetime
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import get_connection, EmailMultiAlternatives, EmailMessage
from django.conf import settings
from django.template.loader import get_template
from django.db.models.signals import post_save
from rest_framework_simplejwt.tokens import RefreshToken
import stripe

import six


class TokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):

        return (six.text_type(user.pk)+six.text_type(timestamp) + six.text_type(user.is_verified))


PAYMENT_STATUS_CHOICE = (
    ("pending", "pending"),
    ("successful", "successful"),
    ("failed", "failed"),
)

CATEGORIES_CHOICE = (
    ("fishing", "fishing"),
    ("sports", "sports"),
    ("electronics", "electronics"),
    ("phones", "phones"),
    ("games", "games"),
    ("tablets", "tablets"),
    ("outwear", "outwear"),
    ("pets", "pets"),
    ("toys", "toys"),
    ("computing", "computing"),
    ("lingerie", "lingerie"),
    ("books", "books"),
    ("beverages", "beverages"),
)

ORDER_STATUS_CHOICE = (
    ("pending", "pending"),
    ("cancelled", "cancelled"),
    ("refunded", "refunded"),
    ("delivered", "delivered"),
    ("shipped", "shipped"),
    ("picked up", "picked up"),
    ("confirmed", "confirmed"),
)

LABEL_CHOICE = (
    ("new", "new"),
    ("", "none"),
    ("bestseller", "bestseller"),
    ("sold out", "sold out"),
)


GENDER_STATUS = (
    ("male", "male"),
    ("female", "female"),
)

USPS_SERVICE_CHOICE = (
    ("priority", "new"),
    ("express", "none"),
    ("firstclass", "bestseller"),
)

DELIVERY_METHOD_CHOICE = (
    ("pick up", "pick up"),
    ("home delivery", "home delivery"),
)


methods = {
    "post": "POST",
    "get": "GET",
    "delete": "DELETE",
    "get": "GET",
    "options": "OPTIONS",
    "patch": "PATCH",
    "put": "PUT",
}


def send_mail(file_name, reciever_email, data=None):
    html_tpl_path = f"email-templates/{file_name}.html"
    email_html_template = get_template(html_tpl_path).render(data)
    email_msg = EmailMessage(
        "Proace International",
        email_html_template,
        settings.APPLICATION_EMAIL,
        [reciever_email],
        reply_to=[settings.APPLICATION_EMAIL],
    )
    email_msg.content_subtype = "html"
    email_msg.send(fail_silently=False)


def auth_token(user):
    refresh = RefreshToken.for_user(user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def make_payment(items, total, coupon_discount):
    stripe.checkout.Session.create(
        payment_method_types=['card', "cashapp", 'access_debit', "paypal"],
        line_items=[
            {
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': item.product.title,
                    },
                    'unit_amount': int(item.product.sales_price),
                },
                'quantity': item.quantity,
            } for item in items
        ],
        amount_subtotal=total - coupon_discount,
        amount_total=total,
        livemode=False,
        mode='payment',
        success_url='http://localhost:3000/success/',
        cancel_url='http://localhost:3000/cancel/',
    )



# ua = urbanairship
# airship = ua.Airship(f'{settings.AIRSHIP_KEY}',
#                      f'{settings.MASTER_SECRET}', retries=5)
