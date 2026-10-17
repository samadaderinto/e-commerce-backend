"""Import a verified Google profile photo through the configured media storage."""
from __future__ import annotations

import logging
from io import BytesIO
from urllib.parse import urlsplit
from uuid import uuid4

import requests
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

from core.models import User

logger = logging.getLogger(__name__)
MAX_PHOTO_BYTES = 5 * 1024 * 1024


def import_google_avatar(user: User, picture: str) -> None:
    """Fill a missing avatar without replacing a user-selected profile photo."""
    if user.avatar_image or user.avatar_url or not picture:
        return
    try:
        parsed = urlsplit(picture)
        port = parsed.port
    except ValueError:
        return
    host = (parsed.hostname or '').lower()
    if (parsed.scheme != 'https' or not host.endswith('.googleusercontent.com')
            or parsed.username or parsed.password or port not in (None, 443)):
        return
    try:
        with requests.get(picture, timeout=(3, 5), stream=True, allow_redirects=False) as response:
            if response.status_code != 200:
                logger.warning('Google avatar download rejected for user %s (status %s)', user.pk, response.status_code)
                return
            content = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                content.extend(chunk)
                if len(content) > MAX_PHOTO_BYTES:
                    raise ValueError('Avatar exceeds size limit')
        with Image.open(BytesIO(content)) as image:
            if image.format not in {'JPEG', 'PNG', 'WEBP'} or image.width * image.height > 16000000:
                raise ValueError('Unsupported avatar image')
            image = ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'), (512, 512))
            output = BytesIO()
            image.save(output, format='JPEG', quality=90)
        user.avatar_image.save(f'google-{uuid4().hex}.jpg', ContentFile(output.getvalue()), save=False)
        user.avatar_url = ''
        user.save(update_fields=['avatar_image', 'avatar_url', 'updated'])
    except (requests.RequestException, UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as error:
        logger.warning('Google avatar import unavailable for user %s (%s)', user.pk, type(error).__name__)
    except Exception as error:
        # Storage providers may raise their own errors; photo failure must not block login.
        logger.error('Google avatar storage failed for user %s (%s)', user.pk, type(error).__name__)
