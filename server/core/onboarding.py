"""Mailbox verification and credentials kept out of administrative responses/logs."""
import base64
import hashlib
import secrets

from typing import Any
from cryptography.fernet import Fernet
from django.conf import settings
from django.core import signing
from django.db import transaction
from rest_framework.exceptions import ValidationError
from core.models import User
from notification.delivery import queue_email_delivery
from utils.functions import send_mail as send_html_mail


def cipher() -> Fernet:
    key = hashlib.sha256(('staff-invitation:' + settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


@transaction.atomic
def invite_staff(fields: dict[str, Any]) -> User:
    user = User.objects.create_staffuser(
        **fields, password=secrets.token_urlsafe(24), is_active=False, must_change_password=False, staff_email_verified=False,
        staff_invitation_secret='pending_verification',
    )
    user.set_unusable_password()
    user.save(update_fields=['password'])
    token = signing.dumps({'user': user.pk, 'version': user.credential_version}, salt='staff-activation')
    url = f'{settings.FRONTEND_URL}/verify-email?token=staff:{token}'
    send_html_mail(
        'onboarding-staff',
        user.email,
        {
            'firstname': user.first_name,
            'absolute_url': url,
            'subject': 'Verify your staff account',
        },
        recipient=user,
    )
    return user


@transaction.atomic
def resend_staff_verification(user: User) -> User:
    """Invalidate every previous invitation and send a fresh, one-day link."""
    user = User.objects.select_for_update().get(pk=user.pk)
    if user.staff_email_verified:
        raise ValidationError({'detail': 'This staff mailbox is already verified.'})
    user.credential_version += 1
    user.staff_invitation_secret = 'pending_verification'
    user.save(update_fields=['credential_version', 'staff_invitation_secret'])
    token = signing.dumps({'user': user.pk, 'version': user.credential_version}, salt='staff-activation')
    url = f'{settings.FRONTEND_URL}/verify-email?token=staff:{token}'
    send_html_mail(
        'onboarding-staff',
        user.email,
        {
            'firstname': user.first_name,
            'absolute_url': url,
            'subject': 'Verify your staff account',
        },
        recipient=user,
    )
    return user


@transaction.atomic
def activate_staff(token: str) -> User:
    try:
        payload = signing.loads(token, salt='staff-activation', max_age=86400)
        user = User.objects.select_for_update().get(pk=payload['user'], is_staff=True)
        if user.is_active or user.staff_email_verified or payload['version'] != user.credential_version:
            raise ValueError()
    except (signing.BadSignature, User.DoesNotExist, KeyError, TypeError, ValueError):
        raise ValidationError({'detail': 'This staff verification link is invalid, used, or expired.'})

    user.is_active = True
    user.staff_email_verified = True
    user.must_change_password = False
    user.staff_invitation_secret = ''
    user.credential_version += 1
    user.save(update_fields=['is_active', 'staff_email_verified', 'must_change_password', 'staff_invitation_secret', 'credential_version'])

    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    reset_token = default_token_generator.make_token(user)
    reset_url = f'{settings.FRONTEND_URL}/reset-password?uid={uid}&token={reset_token}'

    # Notify staff member to set their permanent password via the reset flow
    queue_email_delivery(
        user.email,
        'Set your ProAce staff password',
        f'Hello {user.first_name or "Staff"},\n\n'
        f'Your staff email address has been verified successfully.\n\n'
        f'Please set your password using the link below to get started:\n'
        f'{reset_url}\n\n'
        f'You can also use the "Forgot Password" link on the sign-in page ({settings.FRONTEND_URL}/forgot-password) at any time to set or reset your password.\n\n'
        f'Best regards,\n'
        f'ProAce International Team',
        recipient=user,
    )
    return user
