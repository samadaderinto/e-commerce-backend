import stripe
import six

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
    
    
class TokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):

        return (six.text_type(user.pk)+six.text_type(timestamp) + six.text_type(user.is_verified))

