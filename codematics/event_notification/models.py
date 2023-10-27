from django.db import models
from notifications.base.models import AbstractNotification

from core.models import User



class Notification(AbstractNotification):
    class Meta(AbstractNotification.Meta):
        abstract = False