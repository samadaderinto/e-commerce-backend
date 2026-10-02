import base64
import logging
from email.mime.base import MIMEBase

import resend
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = getattr(settings, "RESEND_API_KEY", "")
        if not api_key:
            raise ImproperlyConfigured("Set RESEND_API_KEY to send email through Resend.")

        resend.api_key = api_key
        sent = 0
        for message in email_messages:
            try:
                resend.Emails.send(self._build_payload(message))
            except Exception:
                if not self.fail_silently:
                    raise
                logger.exception("Resend email delivery failed.")
            else:
                sent += 1
        return sent

    @staticmethod
    def _build_payload(message):
        payload = {
            "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": list(message.to),
            "subject": message.subject,
        }
        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)
        if message.extra_headers:
            payload["headers"] = {
                str(key): str(value) for key, value in message.extra_headers.items()
            }

        payload["html" if message.content_subtype == "html" else "text"] = message.body
        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                payload["html"] = content
            elif mimetype == "text/plain":
                payload["text"] = content

        attachments = [
            ResendEmailBackend._build_attachment(attachment)
            for attachment in message.attachments
        ]
        if attachments:
            payload["attachments"] = attachments
        return payload

    @staticmethod
    def _build_attachment(attachment):
        if isinstance(attachment, MIMEBase):
            filename = attachment.get_filename()
            content_type = attachment.get_content_type()
            content = attachment.get_payload(decode=True)
        else:
            filename, content, content_type = (*attachment, None)[:3]

        if isinstance(content, str):
            content = content.encode("utf-8")
        encoded_content = base64.b64encode(content).decode("ascii")
        result = {"filename": filename, "content": encoded_content}
        if content_type:
            result["content_type"] = content_type
        return result
