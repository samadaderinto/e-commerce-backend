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


class Command(BaseCommand):
    help = "Create the configured default application superuser if it does not exist."

    def handle(self, *args, **options):
        values = {
            field: os.environ.get(env_name, "")
            for field, env_name in ADMIN_ENV_FIELDS.items()
        }
        if not any(value.strip() for value in values.values()):
            self.stdout.write("Default admin is not configured; skipping.")
            return

        missing = [
            env_name
            for field, env_name in ADMIN_ENV_FIELDS.items()
            if not values[field].strip()
        ]
        if missing:
            raise CommandError(
                "Set all default admin environment fields; missing: "
                + ", ".join(missing)
            )

        values["email"] = values["email"].strip()
        for field in ("first_name", "last_name", "gender", "phone1"):
            values[field] = values[field].strip()
        values["gender"] = values["gender"].lower()
        if values["gender"] not in dict(User.GENDER_STATUS):
            raise CommandError("DEFAULT_ADMIN_GENDER must be 'male' or 'female'.")

        try:
            with transaction.atomic():
                existing = User.objects.filter(email=values["email"]).first()
                if existing:
                    self._require_superuser(existing)
                    self.stdout.write("Configured default admin already exists.")
                    return

                candidate = User(
                    email=values["email"],
                    first_name=values["first_name"],
                    last_name=values["last_name"],
                    gender=values["gender"],
                    phone1=values["phone1"],
                    is_staff=True,
                    is_superuser=True,
                    is_active=True,
                )
                try:
                    candidate.full_clean(exclude=["password"])
                    validate_password(values["password"], user=candidate)
                except ValidationError as error:
                    raise CommandError("; ".join(error.messages)) from error

                User.objects.create_superuser(
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
            self._require_superuser(existing)

        self.stdout.write(self.style.SUCCESS("Configured default admin is ready."))

    @staticmethod
    def _require_superuser(user):
        if not (user.is_active and user.is_staff and user.is_superuser):
            raise CommandError(
                "DEFAULT_ADMIN_EMAIL belongs to an account that is not an active superuser."
            )
