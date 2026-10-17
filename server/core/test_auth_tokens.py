import pytest

from core.auth_tokens import credential_version_token_generator
from core.models import User


@pytest.mark.django_db
def test_password_reset_token_is_invalidated_when_credentials_change() -> None:
    user = User.objects.create(email='reset-version@example.com', is_active=True)
    user.set_password('ResetTokenPassword2026!')
    user.save()
    token = credential_version_token_generator.make_token(user)

    assert credential_version_token_generator.check_token(user, token)

    user.credential_version += 1
    user.save(update_fields=['credential_version'])
    assert not credential_version_token_generator.check_token(user, token)
