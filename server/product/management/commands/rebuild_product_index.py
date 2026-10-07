from django.core.management.base import BaseCommand, CommandError

from product.models import Product
from product.search import client, enabled, ensure_products_index, product_document


class Command(BaseCommand):
    help = "Rebuild the Elasticsearch product index from the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Delete existing index before re-indexing.",
        )

    def handle(self, *args, **options):
        if not enabled():
            raise CommandError("Set ELASTICSEARCH_ENABLED=true before rebuilding the product index.")
        from django.conf import settings
        from elasticsearch.helpers import bulk

        es = client().options(request_timeout=30)
        if options.get("clean"):
            es.indices.delete(index=settings.ELASTICSEARCH_PRODUCTS_INDEX, ignore_unavailable=True)
        ensure_products_index(es)
        products = Product.objects.select_related("store").prefetch_related("tags")
        actions = (
            {"_index": settings.ELASTICSEARCH_PRODUCTS_INDEX, "_id": product.pk,
             "_source": product_document(product)}
            for product in products.iterator(chunk_size=100)
        )
        count, _ = bulk(es, actions, chunk_size=100, raise_on_error=True)
        es.indices.refresh(index=settings.ELASTICSEARCH_PRODUCTS_INDEX)
        self.stdout.write(self.style.SUCCESS(f"Indexed {count} products."))
