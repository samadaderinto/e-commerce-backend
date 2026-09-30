import contextvars
from datetime import datetime, timezone
import json
import logging
import traceback


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
