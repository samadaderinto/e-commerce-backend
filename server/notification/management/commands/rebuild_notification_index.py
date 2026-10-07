from django.core.management.base import BaseCommand, CommandError

from notification.models import Notification
from notification.search import (
    client,
    enabled,
    ensure_notifications_index,
    notification_document,
)


class Command(BaseCommand):
    help = "Rebuild the Elasticsearch notification index from the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Delete existing index before re-indexing.",
        )

    def handle(self, *args, **options):
        if not enabled():
            raise CommandError("Set ELASTICSEARCH_ENABLED=true before rebuilding the notification index.")
        from django.conf import settings
        from elasticsearch.helpers import bulk

        es = client().options(request_timeout=30)
        index = getattr(
            settings,
            "ELASTICSEARCH_NOTIFICATIONS_INDEX",
            f"{getattr(settings, 'ELASTICSEARCH_INDEX_PREFIX', 'commerce')}-notifications",
        )
        if options.get("clean"):
            es.indices.delete(index=index, ignore_unavailable=True)
        ensure_notifications_index(es)

        notifications = Notification.objects.select_related(
            "recipient",
            "actor_content_type",
            "target_content_type",
            "action_object_content_type",
        )
        actions = (
            {
                "_index": index,
                "_id": notif.pk,
                "_source": notification_document(notif),
            }
            for notif in notifications.iterator(chunk_size=100)
        )
        count, _ = bulk(es, actions, chunk_size=100, raise_on_error=True)
        es.indices.refresh(index=index)
        self.stdout.write(self.style.SUCCESS(f"Indexed {count} notifications."))
