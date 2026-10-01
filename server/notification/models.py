from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


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
    data = models.JSONField("data", blank=True, null=True)

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


class PushDevice(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_devices",
    )
    token = models.CharField(max_length=4096, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return f"Push device for user {self.user_id}"


class NotificationDelivery(models.Model):
    CHANNEL_EMAIL = "email"
    CHANNEL_PUSH = "push"
    CHANNELS = (
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_PUSH, "FCM push"),
    )

    STATUS_PENDING = "pending"
    STATUS_QUEUED = "queued"
    STATUS_PROCESSING = "processing"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUSES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_QUEUED, "Queued"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    )

    channel = models.CharField(max_length=10, choices=CHANNELS)
    status = models.CharField(
        max_length=12,
        choices=STATUSES,
        default=STATUS_PENDING,
        db_index=True,
    )
    notification = models.ForeignKey(
        Notification,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="notification_deliveries",
    )
    recipient_email = models.EmailField(blank=True)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    reply_to = models.EmailField(blank=True)
    is_html = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [
            models.Index(
                fields=["status", "available_at"],
                name="notif_delivery_ready_idx",
            ),
        ]

    def __str__(self):
        return f"{self.channel} delivery {self.pk} ({self.status})"
