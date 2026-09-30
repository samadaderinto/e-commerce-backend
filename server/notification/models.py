from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from jsonfield import JSONField


class Notification(models.Model):
    LEVELS = (
        ("success", "success"),
        ("info", "info"),
        ("warning", "warning"),
        ("error", "error"),
    )

    level = models.CharField("level", choices=LEVELS, default="info", max_length=20)
    unread = models.BooleanField("unread", db_index=True, default=True)

    actor_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="notify_actor",
        verbose_name="actor content type",
    )
    actor_object_id = models.CharField("actor object id", max_length=255)
    actor = GenericForeignKey("actor_content_type", "actor_object_id")

    verb = models.CharField("verb", max_length=255)
    description = models.TextField("description", blank=True, null=True)

    target_content_type = models.ForeignKey(
        ContentType,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="notify_target",
        verbose_name="target content type",
    )
    target_object_id = models.CharField("target object id", blank=True, max_length=255, null=True)
    target = GenericForeignKey("target_content_type", "target_object_id")

    action_object_content_type = models.ForeignKey(
        ContentType,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="notify_action_object",
        verbose_name="action object content type",
    )
    action_object_object_id = models.CharField(
        "action object object id",
        blank=True,
        max_length=255,
        null=True,
    )
    action_object = GenericForeignKey("action_object_content_type", "action_object_object_id")

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="recipient",
    )
    timestamp = models.DateTimeField("timestamp", db_index=True, default=timezone.now)
    public = models.BooleanField("public", db_index=True, default=True)
    deleted = models.BooleanField("deleted", db_index=True, default=False)
    emailed = models.BooleanField("emailed", db_index=True, default=False)
    data = JSONField("data", blank=True, null=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ("-timestamp",)
        indexes = [
            models.Index(fields=["recipient", "unread"], name="notif_rec_unread_idx"),
        ]

    def __str__(self):
        return f"{self.actor} {self.verb}"

    def mark_as_read(self):
        if self.unread:
            self.unread = False
            self.save(update_fields=["unread"])

    def mark_as_unread(self):
        if not self.unread:
            self.unread = True
            self.save(update_fields=["unread"])
