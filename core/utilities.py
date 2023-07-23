from datetime import datetime
from django.conf import settings
from django.template.loader import get_template
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import get_connection, EmailMultiAlternatives,EmailMessage


import pytz
import django_filters

from rest_framework_simplejwt.tokens import RefreshToken

from store.models import Schedule, StoreAddress
from payment.models import Coupon
from core.models import Address
from cart.models import Product





class TokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return (
            str(user.pk) + str(timestamp) + str(user.is_active)
        )


generate_token = TokenGenerator()


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)

    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def send_mail(file_name, reciever_email, data=None):
    html_tpl_path = f'email-templates/{file_name}.html'
    email_html_template = get_template(html_tpl_path).render(data)
    email_msg = EmailMessage("Proace International", email_html_template, settings.APPLICATION_EMAIL, [reciever_email],
                             reply_to=[settings.APPLICATION_EMAIL])
    email_msg.content_subtype = 'html'
    email_msg.send(fail_silently=False)


def send_mass_mail(datatuple, fail_silently=False, user=None, password=None,
                   connection=None):
    """
    Given a datatuple of (subject, text_content, html_content, from_email,
    recipient_list), sends each message to each recipient list. Returns the
    number of emails sent.

    If from_email is None, the DEFAULT_FROM_EMAIL setting is used.
    If auth_user and auth_password are set, they're used to log in.
    If auth_user is None, the EMAIL_HOST_USER setting is used.
    If auth_password is None, the EMAIL_HOST_PASSWORD setting is used.

    """
    connection = connection or get_connection(
        username=user, password=password, fail_silently=fail_silently)
    messages = []
    for subject, text, html, from_email, recipient in datatuple:
        message = EmailMultiAlternatives(subject, text, from_email, recipient)
        message.attach_alternative(html, 'text/html')
        messages.append(message)
    return connection.send_messages(messages)


def deactivate_coupon():
    today = datetime.now()
    coupons = Coupon.objects.all()
    for coupon in coupons:
        exp = coupon.valid_to
        if exp < today:
            coupon.active = False
        coupon.save()


def update_product_label():
    today = datetime.now()
    products = Product.objects.all()
    for product in products:
        created = product.created

        product.label = ""
        product.save()


def usps_estimate_delivery(origin_zip, destination_zip, service=""):
    usps_api_route = f'https://secure.shippingapis.com/ShippingAPI.dll?API=FirstClassMail&XML=<FirstClassMailRequest USERID="{settings.USPS_USERNAME}"> <OriginZip>{origin_zip}</OriginZip> <DestinationZip>{destination_zip}</DestinationZip><FirstClassMailRequest>'

    return usps_api_route.text


def update_usps_delivery_date():
    products = Product.objects.all()
    destination_zip = Address.objects.get(user="", is_default=True).zip
    origin_zip = StoreAddress.objects.get(store="", is_default=True).zip

    for product in products:
        product.usps_delivery_date = usps_estimate_delivery(
            origin_zip, destination_zip)
        product.save()


def auto_set_product_visibility():
    schedules = Schedule.objects.all()
    today = datetime.now()
    for schedule in schedules:
        if schedule.make_visible_at <= today:
            schedule.productId.product_visibility = True
        schedule.save()


def calculate_order_amount(items):
    # Replace this constant with a calculation of the order's amount
    # Calculate the order total on the server to prevent
    # people from directly manipulating the amount on the client
    return 1400


methods = {
    "post": "POST",
    "get": "GET",
    "delete": "DELETE",
    "get": "GET",
    "options": "OPTIONS",
    "patch": "PATCH",
    "post": "POST",
    "put": "PUT"}


PAYMENT_STATUS_CHOICE = (
    ("pnd", "pending"),
    ("sfl", "successful"),
    ('fld', "failed")
)

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
    ("BOOK", "books")
)

ORDER_STATUS_CHOICE = (
    ("CND", "cancelled"),
    ("RFD", "refunded"),
    ("DLV", "delivered"),
    ("SHP", "shipped"),
    ("PKU", "picked up"),
    ("PND", "pending"),
    ("CFD", "confirmed")
)

LABEL_CHOICE = (

    ("NEW", "new"),
    ("", "none"),
    ("BTS", "bestseller"),
    ("SDT", "sold out")
)

USPS_SERVICE_CHOICE = (
    ("express", "none"),
    ("priority", "new"),
    ("firstclass", "bestseller")
)

DELIVERY_METHOD_CHOICE = (
    ("pckup", "pick up"),
    ("hmdlvry", "home delivery")
)
