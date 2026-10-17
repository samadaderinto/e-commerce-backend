"""Validation and metadata-safe normalization for public raster image uploads."""
from __future__ import annotations

from io import BytesIO
from pathlib import PurePath

from django.core.files.uploadedfile import UploadedFile, SimpleUploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
SUPPORTED_IMAGE_FORMATS = {
    'JPEG': ('jpg', 'image/jpeg'),
    'PNG': ('png', 'image/png'),
    'WEBP': ('webp', 'image/webp'),
}


class ImageUploadError(ValueError):
    """Raised when an uploaded public image is invalid or unsafe to process."""


def normalize_public_image(
    upload: UploadedFile,
    expected_size: tuple[int, int] | None = None,
) -> SimpleUploadedFile:
    """Decode, orient, and re-encode a public image without source metadata."""
    if upload.size > MAX_IMAGE_BYTES:
        raise ImageUploadError('Images must be at most 5 MB.')

    try:
        upload.seek(0)
        with Image.open(upload) as source:
            image_format = source.format
            if image_format not in SUPPORTED_IMAGE_FORMATS:
                raise ImageUploadError('Use a JPEG, PNG or WebP image.')
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ImageUploadError('Image dimensions are too large.')
            source.load()
            image = ImageOps.exif_transpose(source)
            if expected_size is not None and image.size != expected_size:
                raise ImageUploadError(
                    f'Crop this image to {expected_size[0]} × {expected_size[1]} pixels.'
                )
            if image_format in {'JPEG', 'WEBP'} and image.mode not in {'RGB', 'RGBA'}:
                image = image.convert('RGB')
            output = BytesIO()
            save_options: dict[str, int] = {'quality': 90} if image_format in {'JPEG', 'WEBP'} else {}
            image.save(output, format=image_format, **save_options)
    except ImageUploadError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError, ValueError) as error:
        raise ImageUploadError('Upload a valid JPEG, PNG or WebP image.') from error
    finally:
        upload.seek(0)

    extension, content_type = SUPPORTED_IMAGE_FORMATS[image_format]
    filename = f'{PurePath(upload.name).stem or "image"}.{extension}'
    return SimpleUploadedFile(filename, output.getvalue(), content_type=content_type)
