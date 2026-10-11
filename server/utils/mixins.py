from typing import Any

from django.db import models, transaction


class DatesMixin(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Domain post-save inbox/outbox writes share the record's transaction.
        with transaction.atomic(using=kwargs.get("using")):
            super().save(*args, **kwargs)

    class Meta:
        abstract = True