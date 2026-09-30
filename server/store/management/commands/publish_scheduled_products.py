from django.core.management.base import BaseCommand

from store.services import publish_due_products


class Command(BaseCommand):
    help = 'Publish products whose merchant visibility schedules are due.'

    def handle(self, *args, **options):
        self.stdout.write(f'Published {publish_due_products()} scheduled products.')
