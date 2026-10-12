"""Create a public watermarked derivative while keeping originals private."""

from io import BytesIO
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError


DIGITAL_IMAGE_SUFFIXES = (
    '.jpg', '.jpeg', '.png', '.webp', '.svg', '.gif', '.avif', '.bmp', '.tiff',
)
DIGITAL_AUDIO_SUFFIXES = ('.mp3', '.m4a', '.wav', '.ogg', '.flac', '.aac')
DIGITAL_VIDEO_SUFFIXES = ('.mp4', '.mov', '.m4v', '.webm', '.avi')


def is_image_digital_asset(value: str | None) -> bool:
    """Return whether a stored digital asset is an image based on its filename."""
    if not value:
        return False
    return urlsplit(value).path.lower().endswith(DIGITAL_IMAGE_SUFFIXES)


def digital_asset_kind(value: str | None) -> str:
    """Classify the media family used to keep variant assets compatible."""
    path = urlsplit(value or '').path.lower()
    if path.endswith(DIGITAL_IMAGE_SUFFIXES):
        return 'image'
    if path.endswith(DIGITAL_AUDIO_SUFFIXES):
        return 'audio'
    if path.endswith(DIGITAL_VIDEO_SUFFIXES):
        return 'video'
    return 'document'


def create_digital_preview(file: Any, store_id: int, product_id: int) -> str:
    try:
        file.seek(0)
        with Image.open(file) as source:
            if source.width * source.height > 40_000_000:
                return ''
            preview = ImageOps.exif_transpose(source).convert('RGB')
            preview.thumbnail((1024, 1024))
            overlay = ImageDraw.Draw(preview)
            for top in range(0, preview.height, 80):
                for left in range(-30, preview.width, 140):
                    overlay.text((left, top), 'PROACE PREVIEW', fill='white', stroke_width=1, stroke_fill='black')
            output = BytesIO()
            preview.save(output, format='JPEG', quality=75)
        path = f'images/digital-previews/{store_id}/{product_id}/{uuid4().hex}_preview.jpg'
        return default_storage.save(path, ContentFile(output.getvalue()))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        # Unsupported artwork can still be sold as a private file without
        # publishing its original as a product thumbnail.
        return ''
    finally:
        file.seek(0)
