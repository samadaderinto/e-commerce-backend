"""Mailbox verification and credentials kept out of administrative responses/logs."""
import base64
import hashlib
import secrets

from typing import Any
from cryptography.fernet import Fernet
from django.conf import settings
from django.core import signing
from django.core.mail import send_mail as send_django_mail
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
def activate_staff(token: str) -> None:
    try:
        payload = signing.loads(token, salt='staff-activation', max_age=86400)
        user = User.objects.select_for_update().get(pk=payload['user'], is_staff=True)
        if user.is_active or user.staff_email_verified or payload['version'] != user.credential_version:
            raise ValueError()
    except (signing.BadSignature, User.DoesNotExist, KeyError, TypeError, ValueError):
        raise ValidationError({'detail': 'This staff verification link is invalid, used, or expired.'})
    if settings.EMAIL_BACKEND.endswith(('console.EmailBackend', 'filebased.EmailBackend')):
        raise ValidationError({'detail': 'Configure a private email backend to issue staff credentials.'})
    
    # Generate temporary password upon successful email verification
    temp_password = secrets.token_urlsafe(16)
    user.set_password(temp_password)
    user.is_active = True
    user.staff_email_verified = True
    user.must_change_password = False
    user.staff_invitation_secret = ''
    user.credential_version += 1

    # Send temporary password with explicit advice to use "Forgot Password" flow later
    send_django_mail(
        'Your temporary staff credentials',
        f'Sign in at {settings.FRONTEND_URL}/login with {user.email}\n'
        f'Temporary password: {temp_password}\n\n'
        f'Please note: You are advised to use the "Forgot Password" flow later to set a permanent, secure password.',
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
    user.save(update_fields=['password', 'is_active', 'staff_email_verified', 'must_change_password', 'staff_invitation_secret', 'credential_version'])
