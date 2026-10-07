"""Create a business administrator without granting Django root permissions."""
import os
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from core.models import User


class Command(BaseCommand):
    help = 'Create a non-technical admin using BUSINESS_ADMIN_PASSWORD from the environment.'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--first-name', default='Business')
        parser.add_argument('--last-name', default='Admin')

    def handle(self, *args, **options):
        password = os.environ.get('BUSINESS_ADMIN_PASSWORD', '')
        if not password:
            raise CommandError('Set BUSINESS_ADMIN_PASSWORD.')
        email = options['email'].strip().lower()
        if User.objects.filter(email=email).exists():
            raise CommandError('Account already exists; existing privileges are never overwritten.')
        user = User(email=email, first_name=options['first_name'], last_name=options['last_name'],
                    is_staff=True, is_business_admin=True, is_active=True)
        try:
            user.full_clean(exclude=['password', 'gender', 'phone1'])
            validate_password(password, user)
        except ValidationError as error:
            raise CommandError('; '.join(error.messages))
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS('Business admin created.'))
