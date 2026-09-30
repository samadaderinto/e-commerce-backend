import json
import logging
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from observability.models import LogEntry


class Command(BaseCommand):
    help = "Consume structured application logs from Kafka into the searchable log index."

    def add_arguments(self, parser):
        parser.add_argument("--group", default=os.environ.get("KAFKA_LOG_GROUP", "commerce-log-indexer"))

    def handle(self, *args, **options):
        try:
            from kafka import KafkaConsumer
            consumer = KafkaConsumer(
                os.environ.get("KAFKA_LOG_TOPIC", "commerce.logs"),
                bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
                group_id=options["group"],
                value_deserializer=lambda value: json.loads(value.decode("utf-8")),
                auto_offset_reset="latest",
                enable_auto_commit=True,
            )
        except Exception as exc:
            raise CommandError(f"Kafka is unavailable: {exc}") from exc

        self.stdout.write("Consuming structured logs...")
        for message in consumer:
            payload = message.value
            occurred_at = parse_datetime(payload.get("time", ""))
            if occurred_at is None:
                logging.getLogger(__name__).warning("Skipping log without valid time")
                continue
            LogEntry.objects.create(
                occurred_at=occurred_at,
                level=payload.get("level", "INFO"),
                category=payload.get("category") or self._category(payload),
                logger=payload.get("logger", ""),
                message=payload.get("message", ""),
                route=payload.get("route", ""),
                method=payload.get("method", ""),
                status_code=payload.get("status_code"),
                request_id=payload.get("request_id", ""),
                trace_id=payload.get("trace_id", ""),
                user_id=str(payload.get("user_id", "")),
                service=payload.get("service", "api"),
                metadata={key: value for key, value in payload.items() if key not in {
                    "time", "level", "logger", "message", "route", "method", "status_code",
                    "request_id", "trace_id", "user_id", "service",
                }},
            )

    @staticmethod
    def _category(payload):
        if payload.get("status_code", 0) >= 500:
            return "server_error"
        if payload.get("status_code", 0) >= 400:
            return "client_error"
        return "request"
