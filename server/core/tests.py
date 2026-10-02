import os
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.models import User
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()



@pytest.mark.django_db
def test_create_user():
    payload = {
        "first_name": "samaad",
        "last_name": "ade",
        "email": "fake@gmail.com",
        "phone1": "+2349021162144",
        "gender": "male",
        "password": "jejwjheh",
        "phone2": "+12015550123"
    }

    user = User.objects.create_user(**payload)

    assert user.first_name == payload["first_name"]
    assert user.last_name == payload["last_name"]
    assert user.email == payload["email"]
    assert user.gender == payload["gender"]
    assert user.phone1 == payload["phone1"]


@pytest.mark.django_db
def test_ensure_default_admin_creates_superuser_and_is_idempotent():
    admin_values = {
        "DEFAULT_ADMIN_EMAIL": "admin@example.com",
        "DEFAULT_ADMIN_PASSWORD": "A-Strong-Admin-Password-123!",
        "DEFAULT_ADMIN_FIRST_NAME": "Site",
        "DEFAULT_ADMIN_LAST_NAME": "Admin",
        "DEFAULT_ADMIN_GENDER": "female",
        "DEFAULT_ADMIN_PHONE": "+12015550123",
    }
    with patch.dict(os.environ, admin_values):
        call_command("ensure_default_admin")
        user = User.objects.get(email=admin_values["DEFAULT_ADMIN_EMAIL"])
        assert user.is_active and user.is_staff and user.is_superuser
        assert user.check_password(admin_values["DEFAULT_ADMIN_PASSWORD"])

        changed_values = {**admin_values, "DEFAULT_ADMIN_PASSWORD": "A-Different-Password-123!"}
        with patch.dict(os.environ, changed_values):
            call_command("ensure_default_admin")
        user.refresh_from_db()
        assert user.check_password(admin_values["DEFAULT_ADMIN_PASSWORD"])


@pytest.mark.django_db
def test_ensure_default_admin_rejects_partial_configuration():
    with patch.dict(os.environ, {"DEFAULT_ADMIN_EMAIL": "admin@example.com"}):
        with pytest.raises(CommandError, match="Set all default admin environment fields"):
            call_command("ensure_default_admin")


@pytest.mark.django_db
def test_ensure_default_admin_does_not_promote_existing_regular_user():
    User.objects.create_user(
        email="existing@example.com",
        password="A-Strong-Admin-Password-123!",
        first_name="Existing",
        last_name="User",
        gender="male",
        phone1="+12015550123",
    )
    admin_values = {
        "DEFAULT_ADMIN_EMAIL": "existing@example.com",
        "DEFAULT_ADMIN_PASSWORD": "A-Strong-Admin-Password-123!",
        "DEFAULT_ADMIN_FIRST_NAME": "Site",
        "DEFAULT_ADMIN_LAST_NAME": "Admin",
        "DEFAULT_ADMIN_GENDER": "female",
        "DEFAULT_ADMIN_PHONE": "+12015550123",
    }
    with patch.dict(os.environ, admin_values):
        with pytest.raises(CommandError, match="not an active superuser"):
            call_command("ensure_default_admin")
