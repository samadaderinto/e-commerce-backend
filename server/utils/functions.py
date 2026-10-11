from __future__ import annotations

from decimal import Decimal
from email.utils import parseaddr
from typing import TYPE_CHECKING, Any, Optional

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.template.loader import get_template
import stripe
from rest_framework_simplejwt.tokens import RefreshToken

from notification.delivery import queue_email_delivery

if TYPE_CHECKING:
    from notification.models import Notification


def email_contact(value: str) -> str:
    address = parseaddr(value.strip())[1]
    try:
        validate_email(address)
    except ValidationError:
        return ''
    domain = address.rsplit('@', 1)[1].lower()
    if domain.startswith('example.') or domain.endswith(('.local', '.test', '.invalid', '.example')):
        return ''
    return address


def auth_token(user: Any) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    version = getattr(user, "credential_version", 0)
    refresh["credential_version"] = version
    access = refresh.access_token
    access["credential_version"] = version

    return {
        "refresh": str(refresh),
        "access": str(access),
    }


def send_mail(
    file_name: str,
    reciever_email: str,
    data: Optional[dict[str, Any]] = None,
    recipient: Optional[Any] = None,
    notification: Notification | None = None,
) -> None:
    context = dict(data or {})
    if recipient is None:
        from core.models import User
        recipient = User.objects.filter(email=reciever_email).first()
    context.setdefault('firstname', recipient.first_name if recipient else '')
    context.setdefault('title', str(context.get('subject') or f"ProAce: {file_name.replace('-', ' ').title()}"))
    context.setdefault('message', '')
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')
    context.setdefault('frontend_url', frontend_url)
    context.setdefault('shop_url', f'{frontend_url}/shop')
    context.setdefault('dashboard_url', f'{frontend_url}/merchant')
    context['support_email'] = email_contact(settings.SUPPORT_EMAIL)
    context['order_support_email'] = email_contact(settings.ORDER_SUPPORT_EMAIL)
    context.setdefault('absolute_url', f'{frontend_url}/account/orders')
    if 'orderId' in context and 'order_url' not in context:
        from payment.models import Order
        order = Order.objects.filter(orderId=str(context['orderId'])).first()
        if order and recipient and order.user_id == recipient.pk:
            context['order_url'] = f"{frontend_url}/orders/{order.pk}"
        elif order and recipient:
            from notification.policy import destination_for
            context['order_url'] = frontend_url + destination_for(recipient, "order", {"order_id": order.pk})
        else:
            context['order_url'] = f"{frontend_url}/account/orders"

    html_tpl_path = f"email-templates/{file_name}.html"
    email_html_template = get_template(html_tpl_path).render(context)
    reply_to = context['order_support_email'] if file_name.startswith(('order-', 'refund-')) else context['support_email']
    subject = str(context.get('subject') or f"Proace: {file_name.replace('-', ' ').title()}")
    queue_email_delivery(
        reciever_email,
        subject,
        email_html_template,
        recipient=recipient,
        notification=notification,
        reply_to=reply_to,
        is_html=True,
    )


def make_payment(items: Any, total: Decimal | str | float, coupon_discount: Decimal | str | float) -> Any:
    total = Decimal(str(total))
    coupon_discount = Decimal(str(coupon_discount))
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')
    return stripe.checkout.Session.create(
        payment_method_types=['card', 'cashapp'],
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
        success_url=f'{frontend_url}/success/',
        cancel_url=f'{frontend_url}/cancel/',
    )


class TokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user: Any, timestamp: int) -> str:
        return str(user.pk) + str(timestamp) + str(user.is_active)


def normalize_media_url(url: str | None) -> str:
    """Normalize internal MinIO endpoints to browser-accessible URLs and strip query strings."""
    if not url:
        return ''
    clean = str(url).strip()
    minio_public = getattr(settings, 'MINIO_PUBLIC_URL', 'http://127.0.0.1:9000').rstrip('/')
    minio_endpoint = getattr(settings, 'MINIO_ENDPOINT_URL', 'http://minio:9000').rstrip('/')
    for internal in ('http://minio:9000', 'https://minio:9000', minio_endpoint):
        if internal and clean.startswith(internal):
            clean = f"{minio_public}{clean[len(internal):]}"
            break
    if '/media/' in clean and '?' in clean:
        clean = clean.split('?')[0]
    return clean
