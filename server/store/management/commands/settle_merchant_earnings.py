from django.core.management.base import BaseCommand
from store.services import settle_pending_merchant_earnings


class Command(BaseCommand):
    help = "Settles pending merchant ledger earnings whose refund hold window has elapsed."

    def handle(self, *args, **options):
        count = settle_pending_merchant_earnings()
        self.stdout.write(self.style.SUCCESS(f"Successfully settled {count} pending merchant ledger entries."))
