from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def send_email_task(self, subject, html_body, recipient, reply_to=None):
    message = EmailMessage(
        subject,
        html_body,
        getattr(settings, "APPLICATION_EMAIL", settings.DEFAULT_FROM_EMAIL),
        [recipient],
        reply_to=[reply_to or getattr(settings, "APPLICATION_EMAIL", settings.DEFAULT_FROM_EMAIL)],
    )
    message.content_subtype = "html"
    message.send(fail_silently=False)
