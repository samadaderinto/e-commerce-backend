from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.template.loader import get_template
import stripe
from rest_framework_simplejwt.tokens import RefreshToken

from notification.delivery import queue_email_delivery

if TYPE_CHECKING:
    from notification.models import Notification


def auth_token(user: Any) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
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
    context.setdefault('support_email', getattr(settings, 'APPLICATION_EMAIL', settings.DEFAULT_FROM_EMAIL))
    context.setdefault('absolute_url', f'{frontend_url}/account/orders')
    if 'orderId' in context and 'order_url' not in context:
        context['order_url'] = f"{frontend_url}/account/orders/{context['orderId']}"

    html_tpl_path = f"email-templates/{file_name}.html"
    email_html_template = get_template(html_tpl_path).render(context)
    sender = getattr(settings, "APPLICATION_EMAIL", settings.DEFAULT_FROM_EMAIL)
    subject = str(context.get('subject') or f"Proace: {file_name.replace('-', ' ').title()}")
    queue_email_delivery(
        reciever_email,
        subject,
        email_html_template,
        recipient=recipient,
        notification=notification,
        reply_to=sender,
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
