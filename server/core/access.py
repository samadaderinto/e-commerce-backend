"""Shared role policies for both current and legacy API routes."""
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication


def is_admin(user):
    return bool(user and user.is_authenticated and user.is_active and (user.is_superuser or user.is_business_admin))


def is_backoffice(user):
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser or user.is_business_admin))


class IsCustomer(IsAuthenticated):
    message = "Administrative accounts cannot use consumer features."

    def has_permission(self, request, view):
        return super().has_permission(request, view) and not is_backoffice(request.user)


class IsBackoffice(BasePermission):
    def has_permission(self, request, view):
        return is_backoffice(request.user) and request.user.is_active and not request.user.must_change_password


class IsBusinessAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user) and not request.user.must_change_password


class BackofficeJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result:
            user, token = result
            if token.get('credential_version', 0) != user.credential_version:
                raise AuthenticationFailed("Session expired. Sign in again.")
            if user.must_change_password and request.path.rstrip('/') not in {'/api/v1/me', '/api/v1/password/change'}:
                raise PermissionDenied("Set a new password before accessing the back office.")
            from core.activity import record_activity
            record_activity(user)
        return result
