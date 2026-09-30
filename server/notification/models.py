from notifications.base.models import AbstractNotification


class Notification(AbstractNotification):
    class Meta(AbstractNotification.Meta):
        abstract = False