"""Opt-in PostgreSQL verification against an isolated test database."""

import os

from .test_settings import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("AUDIT_POSTGRES_DATABASE", "proace_audit"),
        "USER": os.environ.get("AUDIT_POSTGRES_USER", "proace_audit"),
        "PASSWORD": os.environ["AUDIT_POSTGRES_PASSWORD"],
        "HOST": os.environ.get("AUDIT_POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("AUDIT_POSTGRES_PORT", "15432"),
        "TEST": {"NAME": "test_proace_audit"},
    },
}
