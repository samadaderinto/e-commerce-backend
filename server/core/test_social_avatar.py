from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from django.test import override_settings

from core.models import User
from core.social_auth import authenticate_social_user, verify_google_credential


@pytest.mark.django_db
@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'}})
def test_google_login_imports_missing_photo_and_preserves_custom_avatar() -> None:
    output = BytesIO()
    Image.new('RGB', (100, 80), 'blue').save(output, format='PNG')
    response = MagicMock()
    response.__enter__.return_value = response
    response.status_code = 200
    response.iter_content.return_value = [output.getvalue()]
    profile = {'sub': 'avatar-test-subject', 'email': 'google-photo@example.com', 'first_name': 'Photo', 'picture': 'https://lh3.googleusercontent.com/photo'}
    with patch('core.social_auth.verify_google_credential', return_value=profile), patch('core.social_avatar.requests.get', return_value=response) as download:
        result = authenticate_social_user('google', {'credential': 'verified-test'})
        user = User.objects.get(email=profile['email'])
        assert user.avatar_image.name.startswith('user-profiles/avatars/google-')
        assert result['user']['avatar_url'].startswith(f'/api/users/{user.pk}/public/images/avatar')
        with user.avatar_image.open('rb') as saved:
            assert Image.open(saved).size == (512, 512)
        original = user.avatar_image.name
        authenticate_social_user('google', {'credential': 'verified-test'})
        user.refresh_from_db()
        assert user.avatar_image.name == original
        assert download.call_count == 1


@pytest.mark.django_db
@pytest.mark.parametrize('picture', ['http://lh3.googleusercontent.com/photo', 'https://localhost/private', 'https://lh3.googleusercontent.com:bad/photo'])
def test_google_photo_rejects_untrusted_urls(picture: str) -> None:
    profile = {'sub': 'avatar-test-subject', 'email': 'unsafe-photo@example.com', 'picture': picture}
    with patch('core.social_auth.verify_google_credential', return_value=profile), patch('core.social_avatar.requests.get') as download:
        authenticate_social_user('google', {'credential': 'verified-test'})
        download.assert_not_called()


@pytest.mark.django_db
def test_photo_download_failure_does_not_prevent_login() -> None:
    import requests
    profile = {'sub': 'avatar-test-subject', 'email': 'failed-photo@example.com', 'picture': 'https://lh3.googleusercontent.com/photo'}
    with patch('core.social_auth.verify_google_credential', return_value=profile), patch('core.social_avatar.requests.get', side_effect=requests.Timeout):
        assert authenticate_social_user('google', {'credential': 'verified-test'})['user']['email'] == profile['email']


def test_google_verification_preserves_verified_picture() -> None:
    response = MagicMock(status_code=200)
    response.json.return_value = {'email': 'photo@example.com', 'email_verified': True, 'aud': 'example-client', 'picture': 'https://lh3.googleusercontent.com/photo'}
    with override_settings(GOOGLE_CLIENT_ID='example-client'), patch('core.social_auth.requests.get', return_value=response):
        assert verify_google_credential('credential')['picture'] == response.json.return_value['picture']
