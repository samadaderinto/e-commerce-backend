"""Authentication input and throttle isolation regressions; no provider calls."""
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from pytest_django.fixtures import Settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from core.auth_tokens import credential_version_token_generator
from core.models import User
from core.throttles import AccountAuthThrottle

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolated_auth(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    settings.ROOT_URLCONF = 'storefront.urls'
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, 'NUM_PROXIES': None}
    monkeypatch.setattr(AccountAuthThrottle, 'THROTTLE_RATES', {'auth': '10/minute'})
    cache.clear()
    with patch(
        'core.social_auth.authenticate_social_user',
        side_effect=ValidationError({'detail': 'Provider credential rejected.'}),
    ):
        yield
    cache.clear()


@pytest.mark.parametrize('action', [
    'login', 'register', 'forgot', 'reset', 'verify',
    'refresh', 'logout', 'google', 'apple', 'social',
])
@pytest.mark.parametrize('body', [[], ['email'], 'invalid', 123, True, None])
def test_non_object_auth_bodies_return_clean_400(action: str, body: object) -> None:
    import json

    response = APIClient().generic(
        'POST', f'/api/v1/auth/{action}/', json.dumps(body),
        content_type='application/json',
    )
    assert response.status_code == 400
    assert 'JSON object' in str(response.data)


@pytest.mark.parametrize('field', ['uid', 'token'])
@pytest.mark.parametrize('value', [
    123, True, [], ['token'], {}, {'token': 'value'}, None, '', ' ', 'x' * 257,
])
def test_invalid_reset_fields_return_400_without_changing_credentials(
    field: str, value: object,
) -> None:
    user = User.objects.create_user(email='reset-input@example.test', password='OriginalPassword2026!')
    data = {
        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': credential_version_token_generator.make_token(user),
        'password': 'ReplacementPassword2026!',
        field: value,
    }
    response = APIClient().post('/api/v1/auth/reset/', data, format='json')
    assert response.status_code == 400
    assert 'Invalid reset link' in str(response.data)
    user.refresh_from_db()
    assert user.check_password('OriginalPassword2026!')
    assert user.credential_version == 0


def test_valid_reset_still_revokes_the_used_link() -> None:
    user = User.objects.create_user(email='reset-valid@example.test', password='OriginalPassword2026!')
    data = {
        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': credential_version_token_generator.make_token(user),
        'password': 'ReplacementPassword2026!',
    }
    with patch('notification.views.password_changed_notification'):
        assert APIClient().post('/api/v1/auth/reset/', data, format='json').status_code == 200
    user.refresh_from_db()
    assert user.check_password(data['password'])
    assert user.credential_version == 1
    assert APIClient().post('/api/v1/auth/reset/', data, format='json').status_code == 400


@pytest.mark.parametrize('action', ['google', 'apple', 'social'])
def test_unused_email_and_untrusted_forwarded_header_cannot_reset_social_limit(
    action: str,
) -> None:
    client = APIClient()
    for attempt in range(11):
        response = client.post(
            f'/api/v1/auth/{action}/',
            {
                'email': f'unused-{attempt}@example.test',
                'credential': 'placeholder',
                'provider': 'google',
            },
            format='json', HTTP_X_FORWARDED_FOR=f'198.51.100.{attempt + 1}',
        )
        assert response.status_code == (400 if attempt < 10 else 429)


@pytest.mark.parametrize('action', ['login', 'register', 'forgot'])
def test_account_limits_do_not_merge_clients_behind_one_proxy(action: str) -> None:
    client = APIClient()
    allowed_status = {'login': 401, 'register': 400, 'forgot': 200}[action]
    for email in ['first@example.test', 'second@example.test']:
        for attempt in range(11):
            response = client.post(f'/api/v1/auth/{action}/', {'email': email}, format='json')
            assert response.status_code == (429 if attempt == 10 else allowed_status)


def test_account_email_case_does_not_reset_limit() -> None:
    client = APIClient()
    for attempt in range(11):
        response = client.post('/api/v1/auth/login/', {
            'email': ' OWNER@EXAMPLE.TEST ' if attempt % 2 else 'owner@example.test',
        }, format='json')
        assert response.status_code == (401 if attempt < 10 else 429)


@pytest.mark.parametrize('proxy_count', [0, 1])
def test_explicit_client_limit_is_independent_of_account_bucket(
    settings: Settings, proxy_count: int,
) -> None:
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, 'NUM_PROXIES': proxy_count}
    client = APIClient()
    for attempt in range(11):
        response = client.post(
            '/api/v1/auth/login/', {'email': f'account-{attempt}@example.test'},
            format='json', REMOTE_ADDR='192.0.2.10', HTTP_X_FORWARDED_FOR='198.51.100.1',
        )
        assert response.status_code == (401 if attempt < 10 else 429)
    response = client.post(
        '/api/v1/auth/login/', {'email': 'another@example.test'}, format='json',
        REMOTE_ADDR='192.0.2.11', HTTP_X_FORWARDED_FOR='198.51.100.2',
    )
    assert response.status_code == 401
