from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.template.loader import get_template
import stripe
from rest_framework_simplejwt.tokens import RefreshToken

from notification.delivery import queue_email_delivery


def auth_token(user: Any) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def send_mail(file_name: str, reciever_email: str, data: Optional[dict[str, Any]] = None) -> None:
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

