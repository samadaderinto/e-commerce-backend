import contextvars
from datetime import datetime, timezone
import json
import logging
import traceback
import os


class KafkaLogHandler(logging.Handler):
    """Best-effort transport; local console logging remains the source of truth."""
    def emit(self, record):
        try:
            from kafka import KafkaProducer
            payload = json.loads(JsonFormatter().format(record))
            producer = KafkaProducer(
                bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
                value_serializer=lambda value: json.dumps(value).encode('utf-8'),
                request_timeout_ms=500,
                linger_ms=20,
            )
            producer.send(os.environ.get('KAFKA_LOG_TOPIC', 'commerce.logs'), payload)
            producer.flush(timeout=0.5)
            producer.close(timeout=0.5)
        except Exception:
            # Kafka must never take down the web process or hide the console log.
            return


request_context = contextvars.ContextVar('observability_request', default={})


class JsonFormatter(logging.Formatter):
    def format(self, record):
        event = {
            'time': datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            **request_context.get(),
        }
        for field in ('route', 'method', 'status_code', 'duration_ms', 'db_queries', 'db_duration_ms'):
            if hasattr(record, field):
                event[field] = getattr(record, field)
        if record.exc_info:
            # Exception values can contain SQL parameters or provider credentials.
            event['exception_type'] = record.exc_info[0].__name__
            event['stack'] = [
                {'file': frame.filename, 'line': frame.lineno, 'function': frame.name}
                for frame in traceback.extract_tb(record.exc_info[2])
            ]
        return json.dumps(event, ensure_ascii=True)
