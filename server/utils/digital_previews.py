"""Create a public watermarked derivative while keeping originals private."""

from io import BytesIO
from typing import Any
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError


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
