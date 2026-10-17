import pytest
from django.db import OperationalError
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from unittest.mock import patch

from core.models import User
from core.auth_tokens import credential_version_token_generator
from storefront.views import tokens

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('action', ['login', 'register', 'google', 'apple', 'social'])
def test_active_session_cannot_authenticate_again(action: str) -> None:
    user = User(email='active-session@example.com', is_active=True)
    user.set_password('PrivateSessionPassword2026!')
    user.save()
    original_login = user.last_login
    access = tokens(user)['access']
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    response = client.post(f'/api/v1/auth/{action}/', {
        'email': user.email, 'password': 'PrivateSessionPassword2026!',
        'credential': 'dev-google:other@example.com', 'provider': 'google',
    }, format='json')
    assert response.status_code == 409
    assert 'access' not in response.data and 'refresh' not in response.data
    user.refresh_from_db()
    assert user.last_login == original_login
    assert User.objects.count() == 1


def test_revoked_session_can_recover_with_password() -> None:
    user = User(email='recover-session@example.com', is_active=True)
    user.set_password('PrivateSessionPassword2026!')
    user.save()
    old_access = tokens(user)['access']
    user.credential_version += 1
    user.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {old_access}')
    response = client.post('/api/v1/auth/login/', {
        'email': user.email, 'password': 'PrivateSessionPassword2026!',
    }, format='json')
    assert response.status_code == 200
    assert response.data['user']['id'] == user.pk


def test_invalid_session_can_recover_and_logout_is_available() -> None:
    user = User(email='invalid-session@example.com', is_active=True)
    user.set_password('PrivateSessionPassword2026!')
    user.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')
    response = client.post('/api/v1/auth/login/', {
        'email': user.email, 'password': 'PrivateSessionPassword2026!',
    }, format='json')
    assert response.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
    assert client.post('/api/v1/auth/logout/', {}, format='json').status_code == 204


def test_login_accepts_legacy_mixed_case_email() -> None:
    user = User.objects.create(email='Legacy.Case@example.com', is_active=True)
    user.set_password('PrivateSessionPassword2026!')
    user.save()
    response = APIClient().post('/api/v1/auth/login/', {
        'email': 'legacy.case@example.com',
        'password': 'PrivateSessionPassword2026!',
    }, format='json')
    assert response.status_code == 200
    assert response.data['user']['email'] == 'Legacy.Case@example.com'


def test_logout_reports_refresh_revocation_failure() -> None:
    user = User.objects.create(email='logout-failure@example.com', is_active=True)
    user.set_password('PrivateSessionPassword2026!')
    user.save()
    refresh = tokens(user)['refresh']
    with patch('rest_framework_simplejwt.tokens.RefreshToken.blacklist', side_effect=OperationalError('database unavailable')):
        response = APIClient().post('/api/v1/auth/logout/', {'refresh': refresh}, format='json')
    assert response.status_code == 503
    assert 'database unavailable' not in str(response.data)


def test_inactive_account_cannot_use_a_password_reset_link() -> None:
    user = User.objects.create(email='inactive-reset@example.com', is_active=False)
    user.set_password('PrivateSessionPassword2026!')
    user.save()
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = credential_version_token_generator.make_token(user)
    response = APIClient().post('/api/v1/auth/reset/', {
        'uid': uid,
        'token': token,
        'password': 'NewPrivatePassword2026!',
    }, format='json')
    assert response.status_code == 400
    user.refresh_from_db()
    assert user.check_password('PrivateSessionPassword2026!')
