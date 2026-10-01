import os

from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codematics.storefront_settings")

app = Celery("codematics")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
