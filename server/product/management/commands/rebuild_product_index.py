from django.core.management.base import BaseCommand, CommandError

from product.models import Product
from product.search import enabled, ensure_products_index, index_product


class Command(BaseCommand):
    help = "Rebuild the Elasticsearch product index from the database."

    def handle(self, *args, **options):
        if not enabled():
            raise CommandError("Set ELASTICSEARCH_ENABLED=true before rebuilding the product index.")
        ensure_products_index()
        count = 0
        for product_id in Product.objects.values_list("id", flat=True).iterator():
            index_product(product_id)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Indexed {count} products."))
