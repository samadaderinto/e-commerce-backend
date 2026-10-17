"""Authenticated account linking with verified provider identities and lockout guards."""
from typing import Any
from uuid import uuid4

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import SocialAccount, User
from storefront.serializers import UserSerializer


class IdentityRequestSerializer(serializers.Serializer):
    credential = serializers.CharField(write_only=True, max_length=20000)
    user = serializers.DictField(required=False)
    current_password = serializers.CharField(required=False, write_only=True, trim_whitespace=False, max_length=128)


class PasswordSetupSerializer(IdentityRequestSerializer):
    provider = serializers.ChoiceField(choices=['google', 'apple'])
    password = serializers.CharField(write_only=True, min_length=8, max_length=128, trim_whitespace=False)


class PasswordSetupResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    access = serializers.CharField()
    refresh = serializers.CharField()


class ConnectedIdentitySerializer(serializers.Serializer):
    provider = serializers.CharField()
    email = serializers.EmailField()
    connected = serializers.BooleanField()


class AuthenticationMethodsSerializer(serializers.Serializer):
    has_password = serializers.BooleanField()
    can_link = serializers.BooleanField()
    accounts = ConnectedIdentitySerializer(many=True)


def customer_only(user: User) -> None:
    if not user.is_active or user.is_staff or user.is_superuser or user.is_business_admin:
        raise PermissionDenied('Social accounts are available only for active customer accounts.')


def verified_identity(provider: str, data: dict[str, Any]) -> dict[str, Any]:
    from core.social_auth import verify_apple_credential, verify_google_credential
    if provider == 'google':
        verified = verify_google_credential(data['credential'])
    elif provider == 'apple':
        verified = verify_apple_credential(data['credential'], data.get('user'))
    else:
        raise ValidationError({'detail': 'Choose Google or Apple.'})
    if not str(verified.get('sub') or '').strip():
        raise ValidationError({'detail': 'Unable to identify the provider account.'})
    return verified


def attach_identity(user: User, provider: str, verified: dict[str, Any], login: bool = False) -> SocialAccount:
    """Caller locks user within a transaction; unique constraints protect cross-user races."""
    subject = str(verified.get('sub') or '').strip()
    if not subject or len(subject) > 255:
        raise ValidationError({'detail': 'Unable to identify the provider account.'})
    existing = SocialAccount.objects.filter(provider=provider, subject=subject).first()
    if existing and existing.user_id != user.pk:
        raise ValidationError({'detail': 'This provider account is already linked to another profile.'})
    own = SocialAccount.objects.filter(user=user, provider=provider, connected=True).first()
    if own and own.subject != subject:
        raise ValidationError({'detail': 'Disconnect your current account for this provider before connecting a different one.'})
    if login and existing and not existing.connected:
        raise PermissionDenied('This sign-in method was disconnected. Reconnect it in settings.')
    try:
        with transaction.atomic():
            identity, _ = SocialAccount.objects.update_or_create(
                provider=provider, subject=subject,
                defaults={'user': user, 'email': str(verified['email']), 'connected': True},
            )
    except IntegrityError:
        raise ValidationError({'detail': 'This provider account could not be linked. Please sign in again.'}) from None
    return identity


def has_password(user: User) -> bool:
    return bool(user.password) and user.has_usable_password()


def methods_for(user: User) -> dict[str, Any]:
    return {
        'has_password': has_password(user),
        'can_link': user.is_active and not (user.is_staff or user.is_superuser or user.is_business_admin),
        'accounts': list(user.social_accounts.filter(connected=True).values('provider', 'email', 'connected')),
    }


def notify_method(user: User, provider: str, action: str) -> None:
    from notification.views import create_notification
    create_notification(
        recipient=user, actor=user, target=user,
        verb=f'{provider.title()} sign-in {action}',
        description=f'Your {provider.title()} sign-in method was {action}. Contact support if you did not make this change.',
        data={'event': 'account_authentication_changed', 'category': 'account', 'url': '/account/profile'},
        event_key=f'account-auth:{user.pk}:{provider}:{action}:{uuid4().hex}',
    )


class AuthenticationMethodsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AuthenticationMethodsSerializer)
    def get(self, request: Request) -> Response:
        return Response(methods_for(request.user))


class ConnectSocialAccountView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=IdentityRequestSerializer, responses=AuthenticationMethodsSerializer)
    @transaction.atomic
    def post(self, request: Request, provider: str) -> Response:
        user = User.objects.select_for_update().get(pk=request.user.pk)
        customer_only(user)
        serializer = IdentityRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verified = verified_identity(provider, serializer.validated_data)
        if str(verified['email']).lower() != user.email.lower():
            current = serializer.validated_data.get('current_password', '')
            if not has_password(user) or not user.check_password(current):
                raise ValidationError({'detail': 'Confirm your password to connect an account with a different email. If you have no password, set one first.'})
        prior = user.social_accounts.filter(provider=provider, connected=True).exists()
        attach_identity(user, provider, verified)
        if provider == 'google':
            from core.social_avatar import import_google_avatar
            import_google_avatar(user, str(verified.get('picture') or ''))
        if not prior:
            notify_method(user, provider, 'connected')
        return Response(methods_for(user))


class DisconnectSocialAccountView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses=AuthenticationMethodsSerializer)
    @transaction.atomic
    def post(self, request: Request, provider: str) -> Response:
        user = User.objects.select_for_update().get(pk=request.user.pk)
        customer_only(user)
        if provider not in ('google', 'apple'):
            raise ValidationError({'detail': 'Choose Google or Apple.'})
        identity = user.social_accounts.filter(provider=provider, connected=True).first()
        if identity is None:
            return Response(methods_for(user))
        if not has_password(user) and not user.social_accounts.filter(connected=True).exclude(pk=identity.pk).exists():
            raise ValidationError({'detail': 'Keep at least one sign-in method. Set a password or connect another provider first.'})
        identity.connected = False
        identity.save(update_fields=['connected', 'updated_at'])
        notify_method(user, provider, 'disconnected')
        return Response(methods_for(user))


class SocialPasswordSetupView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=PasswordSetupSerializer, responses=PasswordSetupResponseSerializer)
    @transaction.atomic
    def post(self, request: Request) -> Response:
        user = User.objects.select_for_update().get(pk=request.user.pk)
        customer_only(user)
        if has_password(user):
            raise ValidationError({'detail': 'Use Change password to update your existing password.'})
        serializer = PasswordSetupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        verified = verified_identity(data['provider'], data)
        owned = SocialAccount.objects.filter(provider=data['provider'], subject=str(verified['sub'])).first()
        if owned and owned.user_id != user.pk:
            raise PermissionDenied('Confirm a provider account belonging to this profile.')
        identity = user.social_accounts.filter(provider=data['provider'], subject=str(verified['sub']), connected=True).first()
        if not identity and str(verified['email']).lower() != user.email.lower():
            raise PermissionDenied('Confirm a provider account belonging to this profile.')
        revoked = user.social_accounts.filter(provider=data['provider'], subject=str(verified['sub']), connected=False).exists()
        if revoked:
            raise PermissionDenied('Reconnect this provider in settings before using it to confirm your identity.')
        try:
            validate_password(data['password'], user)
        except DjangoValidationError as error:
            raise ValidationError({'password': error.messages}) from None
        user.set_password(data['password'])
        user.credential_version += 1
        user.save(update_fields=['password', 'credential_version', 'updated'])
        from notification.views import password_changed_notification
        from storefront.views import tokens
        password_changed_notification(user)
        return Response(tokens(user))
