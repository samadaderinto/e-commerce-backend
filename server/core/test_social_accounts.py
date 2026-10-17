from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from core.models import SocialAccount, User
from core.social_auth import authenticate_social_user

pytestmark = pytest.mark.django_db


def profile(email: str = 'owner@example.com', subject: str = 'google-owner') -> dict[str, str]:
    return {'email': email, 'sub': subject, 'first_name': 'Owner', 'last_name': 'Customer'}


def customer(password: bool = True) -> User:
    user = User(email='owner@example.com', is_active=True)
    if password:
        user.set_password('OwnerPrivatePassword2026!')
    else:
        user.set_unusable_password()
    user.save()
    return user


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_email_match_links_once_and_stable_subject_survives_email_change() -> None:
    user = customer()
    with patch('core.social_auth.verify_google_credential', return_value=profile()):
        first = authenticate_social_user('google', {'credential': 'verified'})
    assert first['user']['id'] == user.pk
    assert first['is_new_user'] is False
    with patch('core.social_auth.verify_google_credential', return_value=profile('changed@example.com')):
        second = authenticate_social_user('google', {'credential': 'verified'})
    assert second['user']['id'] == user.pk
    assert second['user']['email'] == 'owner@example.com'
    assert User.objects.count() == 1
    assert SocialAccount.objects.get(user=user).email == 'changed@example.com'


def test_link_different_email_requires_password_and_keeps_session_profile() -> None:
    user = customer()
    client = client_for(user)
    with patch('core.social_auth.verify_google_credential', return_value=profile('different@example.com')):
        assert client.post('/api/v1/auth/connect/google/', {'credential': 'verified'}, format='json').status_code == 400
        response = client.post('/api/v1/auth/connect/google/', {
            'credential': 'verified', 'current_password': 'OwnerPrivatePassword2026!',
        }, format='json')
    assert response.status_code == 200
    assert response.data['has_password'] is True
    assert response.data['accounts'][0]['email'] == 'different@example.com'
    assert client.get('/api/v1/me/').data['id'] == user.pk
    assert User.objects.count() == 1


def test_provider_owned_by_another_profile_cannot_be_taken_over() -> None:
    user = customer()
    other = User.objects.create(email='other@example.com', is_active=True)
    SocialAccount.objects.create(user=other, provider='google', subject='google-owner', email=user.email)
    with patch('core.social_auth.verify_google_credential', return_value=profile()):
        response = client_for(user).post('/api/v1/auth/connect/google/', {'credential': 'verified'}, format='json')
    assert response.status_code == 400
    assert SocialAccount.objects.get(subject='google-owner').user_id == other.pk


def test_disconnect_last_method_is_blocked_then_other_provider_allows_it() -> None:
    user = customer(False)
    SocialAccount.objects.create(user=user, provider='google', subject='google-owner', email=user.email)
    client = client_for(user)
    assert client.post('/api/v1/auth/disconnect/google/', {}, format='json').status_code == 400
    SocialAccount.objects.create(user=user, provider='apple', subject='apple-owner', email=user.email)
    assert client.post('/api/v1/auth/disconnect/google/', {}, format='json').status_code == 200
    assert not SocialAccount.objects.get(provider='google').connected
    assert SocialAccount.objects.get(provider='apple').connected


def test_disconnected_provider_login_stays_disabled_until_explicit_reconnect() -> None:
    user = customer()
    SocialAccount.objects.create(user=user, provider='google', subject='google-owner', email=user.email)
    client = client_for(user)
    client.post('/api/v1/auth/disconnect/google/', {}, format='json')
    with patch('core.social_auth.verify_google_credential', return_value=profile()):
        denied = APIClient().post('/api/v1/auth/google/', {'credential': 'verified'}, format='json')
        assert denied.status_code == 403
        assert client.post('/api/v1/auth/connect/google/', {'credential': 'verified'}, format='json').status_code == 200
        assert APIClient().post('/api/v1/auth/google/', {'credential': 'verified'}, format='json').status_code == 200


def test_provider_can_be_replaced_without_losing_old_revocation() -> None:
    user = customer()
    SocialAccount.objects.create(user=user, provider='google', subject='old-google', email=user.email, connected=False)
    with patch('core.social_auth.verify_google_credential', return_value=profile()):
        assert client_for(user).post('/api/v1/auth/connect/google/', {'credential': 'verified'}, format='json').status_code == 200
    assert user.social_accounts.filter(connected=True).count() == 1
    assert user.social_accounts.filter(connected=False).count() == 1


def test_setting_password_requires_provider_proof_then_unlocks_disconnect() -> None:
    user = customer(False)
    SocialAccount.objects.create(user=user, provider='google', subject='google-owner', email=user.email)
    client = client_for(user)
    with patch('core.social_auth.verify_google_credential', return_value=profile('other@example.com', 'other-subject')):
        assert client.post('/api/v1/auth/password/', {'provider': 'google', 'credential': 'verified', 'password': 'StrongPersonalPassword2026!'}, format='json').status_code == 403
    with patch('core.social_auth.verify_google_credential', return_value=profile()):
        response = client.post('/api/v1/auth/password/', {'provider': 'google', 'credential': 'verified', 'password': 'StrongPersonalPassword2026!'}, format='json')
    assert response.status_code == 200
    assert 'access' in response.data and 'refresh' in response.data
    user.refresh_from_db()
    assert user.check_password('StrongPersonalPassword2026!')
    assert user.credential_version == 1
    assert client.post('/api/v1/auth/disconnect/google/', {}, format='json').status_code == 200


def test_methods_are_recipient_scoped_and_empty_password_is_not_usable() -> None:
    user = customer(False)
    other = User.objects.create(email='other@example.com')
    SocialAccount.objects.create(user=other, provider='google', subject='other-subject', email=other.email)
    response = client_for(user).get('/api/v1/auth/methods/')
    assert response.data == {'has_password': False, 'can_link': True, 'accounts': []}
    assert client_for(other).get('/api/v1/auth/methods/').data['has_password'] is False


@pytest.mark.parametrize('role', ['is_staff', 'is_superuser', 'is_business_admin'])
def test_operators_cannot_link_social_accounts(role: str) -> None:
    user = customer()
    setattr(user, role, True)
    user.save()
    response = client_for(user).post('/api/v1/auth/connect/google/', {'credential': 'verified'}, format='json')
    assert response.status_code == 403
    assert user.social_accounts.count() == 0


def test_anonymous_linking_and_disconnect_are_denied() -> None:
    for route in ['connect/google', 'disconnect/google', 'methods']:
        response = APIClient().get(f'/api/v1/auth/{route}/') if route == 'methods' else APIClient().post(f'/api/v1/auth/{route}/', {}, format='json')
        assert response.status_code == 401


def test_two_disconnects_keep_the_final_provider_connected() -> None:
    user = customer(False)
    for provider in ('google', 'apple'):
        SocialAccount.objects.create(user=user, provider=provider, subject=provider, email=user.email)
    client = client_for(user)
    assert client.post('/api/v1/auth/disconnect/google/', {}, format='json').status_code == 200
    assert client.post('/api/v1/auth/disconnect/apple/', {}, format='json').status_code == 400
    assert user.social_accounts.filter(connected=True).count() == 1


def test_disconnected_provider_cannot_set_password_and_failed_link_rolls_back() -> None:
    user = customer(False)
    SocialAccount.objects.create(user=user, provider='google', subject='google-owner', email=user.email, connected=False)
    with patch('core.social_auth.verify_google_credential', return_value=profile()):
        response = client_for(user).post('/api/v1/auth/password/', {
            'provider': 'google', 'credential': 'verified', 'password': 'StrongPersonalPassword2026!',
        }, format='json')
    assert response.status_code == 403
    user.refresh_from_db()
    assert not user.has_usable_password()


def test_apple_verified_email_is_required() -> None:
    import jwt
    from django.test import override_settings
    from rest_framework.exceptions import ValidationError
    from core.social_auth import verify_apple_credential
    credential = jwt.encode({
        'iss': 'https://appleid.apple.com', 'sub': 'apple-owner',
        'email': 'owner@example.com', 'email_verified': False,
    }, 'test-only-secret-with-at-least-32-characters', algorithm='HS256')
    with override_settings(APPLE_CLIENT_ID=''):
        with pytest.raises(ValidationError):
            verify_apple_credential(credential)


def test_real_credentials_never_fall_back_to_unverified_claims() -> None:
    import jwt
    import requests
    from django.test import override_settings
    from rest_framework.exceptions import ValidationError
    from core.social_auth import verify_google_credential, verify_apple_credential
    credential = jwt.encode({
        'iss': 'https://accounts.google.com', 'sub': 'forged-subject',
        'email': 'owner@example.com', 'email_verified': True,
    }, 'test-only-secret-with-at-least-32-characters', algorithm='HS256')
    with override_settings(GOOGLE_CLIENT_ID='configured'), patch('core.social_auth.requests.get', side_effect=requests.Timeout):
        with pytest.raises(ValidationError):
            verify_google_credential(credential)
    apple = jwt.encode({
        'iss': 'https://appleid.apple.com', 'sub': 'forged-subject',
        'email': 'owner@example.com', 'email_verified': True,
    }, 'test-only-secret-with-at-least-32-characters', algorithm='HS256')
    with override_settings(APPLE_CLIENT_ID=''):
        with pytest.raises(ValidationError):
            verify_apple_credential(apple)


def test_only_effective_identity_changes_send_security_notices() -> None:
    from notification.models import Notification
    user = customer()
    client = client_for(user)
    with patch('core.social_auth.verify_google_credential', return_value=profile()):
        for _ in range(2):
            assert client.post('/api/v1/auth/connect/google/', {'credential': 'verified'}, format='json').status_code == 200
        assert Notification.objects.filter(recipient=user, data__event='account_authentication_changed').count() == 1
        for _ in range(2):
            assert client.post('/api/v1/auth/disconnect/google/', {}, format='json').status_code == 200
        assert Notification.objects.filter(recipient=user, data__event='account_authentication_changed').count() == 2
        assert client.post('/api/v1/auth/connect/google/', {'credential': 'verified'}, format='json').status_code == 200
    assert Notification.objects.filter(recipient=user, data__event='account_authentication_changed').count() == 3
