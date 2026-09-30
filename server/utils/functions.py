import stripe
import six
from decimal import Decimal

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMessage
from django.conf import settings
from django.template.loader import get_template

from rest_framework_simplejwt.tokens import RefreshToken



def auth_token(user):
    refresh = RefreshToken.for_user(user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def send_mail(file_name, reciever_email, data=None):
    html_tpl_path = f"email-templates/{file_name}.html"
    email_html_template = get_template(html_tpl_path).render(data)
    if getattr(settings, "QUEUE_EMAILS", True):
        from notification.tasks import send_email_task
        send_email_task.delay(
            f"Proace: {file_name.replace('-', ' ').title()}",
            email_html_template,
            reciever_email,
            getattr(settings, "APPLICATION_EMAIL", settings.DEFAULT_FROM_EMAIL),
        )
        return
    email_msg = EmailMessage(
        "Proace International",
        email_html_template,
        settings.APPLICATION_EMAIL,
        [reciever_email],
        reply_to=[settings.APPLICATION_EMAIL],
    )
    email_msg.content_subtype = "html"
    email_msg.send(fail_silently=False)
    

def make_payment(items, total, coupon_discount):
    total = Decimal(str(total))
    coupon_discount = Decimal(str(coupon_discount))
    return stripe.checkout.Session.create(
        payment_method_types=['card', "cashapp", 'access_debit', "paypal"],
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
