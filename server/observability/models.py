from django.db import models


class LogEntry(models.Model):
    occurred_at = models.DateTimeField(db_index=True)
    level = models.CharField(max_length=20, db_index=True)
    category = models.CharField(max_length=80, db_index=True)
    logger = models.CharField(max_length=160, blank=True, default="")
    message = models.TextField()
    route = models.CharField(max_length=255, blank=True, default="")
    method = models.CharField(max_length=12, blank=True, default="")
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    trace_id = models.CharField(max_length=64, blank=True, default="")
    user_id = models.CharField(max_length=64, blank=True, default="")
    service = models.CharField(max_length=80, default="api", db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-occurred_at", "-pk")
        indexes = [
            models.Index(fields=("category", "occurred_at")),
            models.Index(fields=("level", "occurred_at")),
        ]
