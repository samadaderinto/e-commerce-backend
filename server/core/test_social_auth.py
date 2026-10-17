from __future__ import annotations

from decimal import Decimal
import json
from unittest.mock import patch
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.cache import cache
from django.test import override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from affiliates.models import Marketer, Referral
from core.models import User, UserWallet, UserWalletTransaction
from core.social_auth import authenticate_social_user, verify_google_credential, verify_apple_credential


def test_apple_keys_are_shared_and_refresh_on_rotation() -> None:
    from core.social_auth import APPLE_JWKS_CACHE_KEY, APPLE_JWKS_URL, RedisAppleJWKClient

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    payload = {"keys": [json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))]}
    cache.delete(APPLE_JWKS_CACHE_KEY)
    try:
        with patch("jwt.PyJWKClient.fetch_data", return_value=payload) as fetch:
            RedisAppleJWKClient(APPLE_JWKS_URL).get_jwk_set()
            RedisAppleJWKClient(APPLE_JWKS_URL).get_jwk_set()
            assert fetch.call_count == 1
            RedisAppleJWKClient(APPLE_JWKS_URL).get_jwk_set(refresh=True)
            assert fetch.call_count == 2
    finally:
        cache.delete(APPLE_JWKS_CACHE_KEY)


@pytest.mark.parametrize("prefix", ["mock-", "test-", "dev-"])
@pytest.mark.parametrize("provider", ["google", "apple"])
@override_settings(GOOGLE_CLIENT_ID="configured", APPLE_CLIENT_ID="configured")
def test_production_rejects_every_synthetic_token(provider: str, prefix: str) -> None:
    verifier = verify_google_credential if provider == "google" else verify_apple_credential
    separator = ":" if prefix == "dev-" else "-"
    with patch("core.social_auth.is_development_or_test", return_value=False):
        with pytest.raises(ValidationError):
            verifier(f"{prefix}{provider}{separator}user@example.com")


@pytest.mark.django_db
def test_social_auth_new_customer_google() -> None:
    res = authenticate_social_user(
        provider='google',
        data={'credential': 'test-google-newcustomer@example.com'},
    )
    assert res['is_new_user'] is True
    assert res['provider'] == 'google'
    assert 'access' in res and 'refresh' in res
    assert res['user']['email'] == 'newcustomer@example.com'

    user = User.objects.get(email='newcustomer@example.com')
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.is_business_admin is False
    assert user.has_usable_password() is False
    assert user.role == 'customer'


@pytest.mark.django_db
def test_social_auth_existing_customer_google() -> None:
    user = User.objects.create(
        email='existing_shopper@example.com',
        first_name='Existing',
        last_name='Shopper',
        is_active=True,
    )
    user.set_password('SecretPassword123!')
    user.save()

    res = authenticate_social_user(
        provider='google',
        data={'credential': 'dev-google:existing_shopper@example.com'},
    )
    assert res['is_new_user'] is False
    assert res['user']['id'] == user.pk
    assert res['user']['email'] == 'existing_shopper@example.com'


@pytest.mark.django_db
def test_social_auth_customer_apple() -> None:
    res = authenticate_social_user(
        provider='apple',
        data={
            'credential': 'dev-apple:apple_customer@example.com',
            'user': {'name': {'firstName': 'Apple', 'lastName': 'Fan'}},
        },
    )
    assert res['is_new_user'] is True
    assert res['provider'] == 'apple'
    assert res['user']['email'] == 'apple_customer@example.com'

    user = User.objects.get(email='apple_customer@example.com')
    assert user.is_active is True
    assert user.is_staff is False
    assert user.has_usable_password() is False


@override_settings(DEBUG=False, TESTING=False, GOOGLE_CLIENT_ID='')
def test_google_social_auth_requires_configured_client_id_in_production(monkeypatch) -> None:
    monkeypatch.setattr('core.social_auth.is_development_or_test', lambda: False)

    with pytest.raises(ValidationError) as exc_info:
        verify_google_credential('dev-google:customer@example.com')

    assert 'Google sign-in is not configured' in str(exc_info.value)


@override_settings(DEBUG=False, TESTING=False, APPLE_CLIENT_ID='')
def test_apple_social_auth_requires_configured_client_id_in_production(monkeypatch) -> None:
    monkeypatch.setattr('core.social_auth.is_development_or_test', lambda: False)

    with pytest.raises(ValidationError) as exc_info:
        verify_apple_credential('dev-apple:customer@example.com')

    assert 'Apple sign-in is not configured' in str(exc_info.value)


@pytest.mark.django_db
@pytest.mark.parametrize(
    'role_kwargs',
    [
        {'is_staff': True, 'is_superuser': False, 'is_business_admin': False},
        {'is_staff': True, 'is_superuser': True, 'is_business_admin': False},
        {'is_staff': True, 'is_superuser': False, 'is_business_admin': True},
    ],
)
def test_social_auth_blocks_administrative_and_staff_accounts(role_kwargs: dict[str, bool]) -> None:
    admin_email = f"admin_{role_kwargs['is_superuser']}_{role_kwargs['is_business_admin']}@proace.local"
    admin_user = User.objects.create(
        email=admin_email,
        first_name='Admin',
        last_name='Staff',
        is_active=True,
        **role_kwargs,
    )
    admin_user.set_password('AdminSecure2026!')
    admin_user.save()

    with pytest.raises(PermissionDenied) as exc_info:
        authenticate_social_user(
            provider='google',
            data={'credential': f'dev-google:{admin_email}'},
        )
    assert 'Administrative and staff accounts cannot sign in via social providers' in str(exc_info.value)

    with pytest.raises(PermissionDenied) as exc_info:
        authenticate_social_user(
            provider='apple',
            data={'credential': f'dev-apple:{admin_email}'},
        )
    assert 'Administrative and staff accounts cannot sign in via social providers' in str(exc_info.value)


@pytest.mark.django_db
def test_social_auth_syncs_with_affiliate_referral() -> None:
    marketer_user = User.objects.create(
        email='marketer_affiliate@proace.local',
        first_name='Top',
        last_name='Marketer',
        is_active=True,
    )
    marketer = Marketer.objects.create(
        user=marketer_user,
        marketer_id='AFFILIATE2026',
    )
    marketer_wallet, _ = UserWallet.objects.get_or_create(user=marketer_user)
    initial_balance = marketer_wallet.balance

    res = authenticate_social_user(
        provider='google',
        data={
            'credential': 'dev-google:referred_shopper@example.com',
            'referral_code': 'AFFILIATE2026',
        },
    )
    assert res['is_new_user'] is True
    referred_user = User.objects.get(email='referred_shopper@example.com')

    referral = Referral.objects.filter(referred_user=referred_user).first()
    assert referral is not None
    assert referral.marketer == marketer
    # On signup, referral is pending to prevent throwaway account abuse
    assert referral.status == Referral.PENDING
    marketer_wallet.refresh_from_db()
    assert marketer_wallet.balance == initial_balance

    # Referral reward unlocks once referred user places a successful order
    from payment.models import Order
    from affiliates.services import process_referral_reward_for_order
    order = Order.objects.create(
        user=referred_user,
        ordered=True,
        status="confirmed",
        total=Decimal("45.00"),
        paid_total=Decimal("45.00"),
    )
    process_referral_reward_for_order(order)

    referral.refresh_from_db()
    assert referral.status == Referral.REWARDED
    assert referral.order == order

    marketer_wallet.refresh_from_db()
    assert marketer_wallet.balance == initial_balance + Decimal('25.00')

    # Verify transaction row
    tx = UserWalletTransaction.objects.filter(wallet=marketer_wallet, reference=f'REF-{referral.pk}').first()
    assert tx is not None
    assert tx.amount == Decimal('25.00')
    assert tx.source == UserWalletTransaction.SOURCE_REFERRAL


@pytest.mark.django_db
def test_social_auth_api_endpoint() -> None:
    client = APIClient()

    # Successful customer Google signup/signin
    resp = client.post(
        '/api/v1/auth/google/',
        {'credential': 'dev-google:api_customer@example.com'},
        format='json',
    )
    assert resp.status_code == 200
    assert resp.data['user']['email'] == 'api_customer@example.com'
    assert 'access' in resp.data

    # Successful customer Apple signup/signin
    resp_apple = client.post(
        '/api/v1/auth/apple/',
        {'credential': 'dev-apple:api_apple@example.com'},
        format='json',
    )
    assert resp_apple.status_code == 200
    assert resp_apple.data['user']['email'] == 'api_apple@example.com'

    # Staff account attempt returns 403 Forbidden
    staff = User.objects.create(
        email='staff_api@proace.local',
        first_name='Staff',
        is_staff=True,
        is_active=True,
    )
    staff.set_password('StaffPassword123!')
    staff.save()

    resp_staff = client.post(
        '/api/v1/auth/google/',
        {'credential': 'dev-google:staff_api@proace.local'},
        format='json',
    )
    assert resp_staff.status_code == 403
    assert 'Administrative and staff accounts cannot sign in via social providers' in str(resp_staff.data)


@override_settings(GOOGLE_CLIENT_ID='profile-client')
def test_verified_google_token_preserves_picture_when_tokeninfo_omits_it() -> None:
    from unittest.mock import Mock
    picture = 'https://lh3.googleusercontent.com/profile-photo'
    credential = jwt.encode({'picture': picture}, 'test-only-secret-at-least-32-characters', algorithm='HS256')
    response = Mock(status_code=200)
    response.json.return_value = {
        'email': 'photo@example.com', 'email_verified': 'true',
        'aud': 'profile-client', 'sub': 'verified-subject',
    }
    with patch('core.social_auth.requests.get', return_value=response):
        verified = verify_google_credential(credential)
    assert verified['picture'] == picture


@pytest.mark.django_db
def test_google_signup_imports_avatar_and_existing_login_does_not_repeat_referral(tmp_path) -> None:
    from io import BytesIO
    from unittest.mock import Mock
    from PIL import Image
    from core.social_avatar import import_google_avatar

    image = BytesIO()
    Image.new('RGB', (40, 40), color='red').save(image, format='PNG')
    response = Mock(status_code=200)
    response.iter_content.return_value = [image.getvalue()]
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    verified = {
        'email': 'photo-signup@example.com', 'first_name': 'Photo',
        'last_name': 'Customer', 'sub': 'photo-subject',
        'picture': 'https://lh3.googleusercontent.com/photo',
    }
    with override_settings(
        MEDIA_ROOT=str(tmp_path),
        STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}},
    ), patch('core.social_auth.verify_google_credential', return_value=verified), patch(
        'core.social_avatar.requests.get', return_value=response
    ), patch('core.social_auth.record_referral') as reward:
        first = authenticate_social_user('google', {'credential': 'verified', 'referral_code': 'INVITE'})
        account = User.objects.get(email=verified['email'])
        assert account.avatar_image.name.startswith('user-profiles/avatars/google-')
        assert account.avatar_image.storage.exists(account.avatar_image.name)
        assert first['user']['avatar_url'].startswith('/api/users/')
        authenticate_social_user('google', {'credential': 'verified', 'referral_code': 'OTHER'})
        reward.assert_called_once_with('INVITE', account)
        with patch('core.social_avatar.requests.get') as download:
            import_google_avatar(account, verified['picture'])
            download.assert_not_called()


@pytest.mark.django_db
def test_social_customer_can_complete_phone_with_validation() -> None:
    account = User.objects.create(email='phone-completion@example.com', is_active=True)
    client = APIClient()
    client.force_authenticate(account)
    invalid = client.patch('/api/v1/me/', {'phone1': 'not-a-phone'}, format='json')
    assert invalid.status_code == 400
    response = client.patch('/api/v1/me/', {'phone1': '+12025550101'}, format='json')
    assert response.status_code == 200
    account.refresh_from_db()
    assert str(account.phone1) == '+12025550101'
