from __future__ import annotations

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from utils.image_uploads import ImageUploadError, normalize_public_image


class PublicImageUploadTests(SimpleTestCase):
    def test_normalization_applies_exif_orientation_and_removes_metadata(self) -> None:
        source = Image.new('RGB', (80, 40), 'red')
        exif = Image.Exif()
        exif[274] = 6
        exif[270] = 'private location metadata'
        content = BytesIO()
        source.save(content, format='JPEG', exif=exif)
        upload = SimpleUploadedFile('location-photo.png', content.getvalue(), content_type='image/jpeg')

        normalized = normalize_public_image(upload)

        self.assertEqual(normalized.name, 'location-photo.jpg')
        self.assertEqual(normalized.content_type, 'image/jpeg')
        with Image.open(normalized) as result:
            self.assertEqual(result.size, (40, 80))
            self.assertEqual(result.getexif(), {})

    def test_normalization_rejects_oversized_dimensions(self) -> None:
        content = BytesIO()
        Image.new('RGB', (6401, 6400), 'blue').save(content, format='PNG')
        upload = SimpleUploadedFile('large.png', content.getvalue(), content_type='image/png')

        with self.assertRaisesRegex(ImageUploadError, 'dimensions are too large'):
            normalize_public_image(upload)
