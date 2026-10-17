from django.contrib.auth.tokens import PasswordResetTokenGenerator
from core.models import User


class CredentialVersionTokenGenerator(PasswordResetTokenGenerator):
    """Invalidate password-reset links whenever account credentials or access change."""

    def _make_hash_value(self, user: User, timestamp: int) -> str:
        return f'{super()._make_hash_value(user, timestamp)}:{user.credential_version}'


credential_version_token_generator = CredentialVersionTokenGenerator()
