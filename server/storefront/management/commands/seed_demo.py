"""The demo entry point shares the complete scenario dataset with fake-data seeding."""
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Populate the complete local demo catalog, accounts and scenario stores.'

    def add_arguments(self, parser):
        parser.add_argument('--password', required=True)
        parser.add_argument('--scale', choices=['small', 'medium', 'large', 'huge'], default='medium')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Demo seeding is disabled outside development.')
        if len(options['password']) < 12:
            raise CommandError('Use a demo password with at least 12 characters.')
        call_command('populate_fake_data', password=options['password'], scale=options['scale'],
                     stdout=self.stdout, stderr=self.stderr)
