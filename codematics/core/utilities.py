import uuid
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import get_connection, EmailMultiAlternatives, EmailMessage
from django.conf import settings
from django.template.loader import get_template
from rest_framework_simplejwt.tokens import RefreshToken
from nanoid import generate


class TokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return str(user.pk) + str(timestamp) + str(user.is_active)


generate_token = TokenGenerator()

PAYMENT_STATUS_CHOICE = (("pnd", "pending"), ("sfl", "successful"), ("fld", "failed"))

CATEGORIES_CHOICE = (
    ("FSHN", "fishing"),
    ("SPRT", "sports"),
    ("ELCT", "electronics"),
    ("PHNS", "phones"),
    ("GMES", "games"),
    ("TBLT", "tablets"),
    ("OUWR", "outwear"),
    ("PETS", "pets"),
    ("TOYS", "toys"),
    ("CMPT", "computing"),
    ("LNGR", "lingerie"),
    ("BOOK", "books"),
)

ORDER_STATUS_CHOICE = (
    ("CND", "cancelled"),
    ("RFD", "refunded"),
    ("DLV", "delivered"),
    ("SHP", "shipped"),
    ("PKU", "picked up"),
    ("PND", "pending"),
    ("CFD", "confirmed"),
)

LABEL_CHOICE = (
    ("NEW", "new"),
    ("", "none"),
    ("BTS", "bestseller"),
    ("SDT", "sold out"),
)


GENDER_STATUS = (("male", "male"), ("female", "female"))

USPS_SERVICE_CHOICE = (
    ("express", "none"),
    ("priority", "new"),
    ("firstclass", "bestseller"),
)

DELIVERY_METHOD_CHOICE = (("pckup", "pick up"), ("hmdlvry", "home delivery"))


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


def get_auth_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def calculate_order_amount():
    pass


def generate_marketer_code():
    code = str(uuid.uuid4()).replace("-", "")[:12]
    return code
