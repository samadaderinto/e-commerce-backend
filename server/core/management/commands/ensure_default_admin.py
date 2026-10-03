import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from core.models import User


ADMIN_ENV_FIELDS = {
    "email": "DEFAULT_ADMIN_EMAIL",
    "password": "DEFAULT_ADMIN_PASSWORD",
    "first_name": "DEFAULT_ADMIN_FIRST_NAME",
    "last_name": "DEFAULT_ADMIN_LAST_NAME",
    "gender": "DEFAULT_ADMIN_GENDER",
    "phone1": "DEFAULT_ADMIN_PHONE",
}

STAFF_ENV_FIELDS = {
    "email": "DEFAULT_STAFF_EMAIL",
    "password": "DEFAULT_STAFF_PASSWORD",
    "first_name": "DEFAULT_STAFF_FIRST_NAME",
    "last_name": "DEFAULT_STAFF_LAST_NAME",
    "gender": "DEFAULT_STAFF_GENDER",
    "phone1": "DEFAULT_STAFF_PHONE",
}


class Command(BaseCommand):
    help = "Create the configured default application superuser and staff user if they do not exist."

    def handle(self, *args, **options):
        self._provision_user(
            ADMIN_ENV_FIELDS,
            role="admin",
            is_staff=True,
            is_superuser=True,
        )
        self._provision_user(
            STAFF_ENV_FIELDS,
            role="staff",
            is_staff=True,
            is_superuser=False,
        )

    def _provision_user(self, env_fields, *, role, is_staff, is_superuser):
        values = {
            field: os.environ.get(env_name, "")
            for field, env_name in env_fields.items()
        }
        if not any(value.strip() for value in values.values()):
            self.stdout.write(f"Default {role} is not configured; skipping.")
            return

        missing = [
            env_name
            for field, env_name in env_fields.items()
            if not values[field].strip()
        ]
        if missing:
            raise CommandError(
                f"Set all default {role} environment fields; missing: "
                + ", ".join(missing)
            )

        values["email"] = values["email"].strip()
        for field in ("first_name", "last_name", "gender", "phone1"):
            values[field] = values[field].strip()
        values["gender"] = values["gender"].lower()
        if values["gender"] not in dict(User.GENDER_STATUS):
            raise CommandError(f"DEFAULT_{role.upper()}_GENDER must be 'male' or 'female'.")

        try:
            with transaction.atomic():
                existing = User.objects.filter(email=values["email"]).first()
                if existing:
                    self._check_flags(existing, role, is_staff, is_superuser)
                    self.stdout.write(f"Configured default {role} already exists.")
                    return

                candidate = User(
                    email=values["email"],
                    first_name=values["first_name"],
                    last_name=values["last_name"],
                    gender=values["gender"],
                    phone1=values["phone1"],
                    is_staff=is_staff,
                    is_superuser=is_superuser,
                    is_active=True,
                )
                try:
                    candidate.full_clean(exclude=["password"])
                    validate_password(values["password"], user=candidate)
                except ValidationError as error:
                    raise CommandError("; ".join(error.messages)) from error

                if is_superuser:
                    User.objects.create_superuser(
                        email=values["email"],
                        password=values["password"],
                        first_name=values["first_name"],
                        last_name=values["last_name"],
                        gender=values["gender"],
                        phone1=values["phone1"],
                    )
                else:
                    User.objects.create_staffuser(
                        email=values["email"],
                        password=values["password"],
                        first_name=values["first_name"],
                        last_name=values["last_name"],
                        gender=values["gender"],
                        phone1=values["phone1"],
                    )
        except IntegrityError:
            # Another API instance may provision the same account at the same time.
            existing = User.objects.filter(email=values["email"]).first()
            if existing is None:
                raise
            self._check_flags(existing, role, is_staff, is_superuser)

        self.stdout.write(self.style.SUCCESS(f"Configured default {role} is ready."))

    @staticmethod
    def _check_flags(user, role, is_staff, is_superuser):
        if not user.is_active:
            raise CommandError(
                f"DEFAULT_{role.upper()}_EMAIL belongs to an inactive account."
            )
        if is_superuser and not (user.is_staff and user.is_superuser):
            raise CommandError(
                f"DEFAULT_{role.upper()}_EMAIL belongs to an account "
                "that is not an active superuser."
            )
        if not is_superuser and not user.is_staff:
            raise CommandError(
                f"DEFAULT_{role.upper()}_EMAIL belongs to an account "
                "that does not have staff status."
            )
