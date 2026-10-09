from io import BytesIO

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import User
from store.models import Store, StoreInfo


class StoreBrandingTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(email='branding-owner@example.com', password='test-password')
        self.other = User.objects.create_user(email='branding-other@example.com', password='test-password')
        self.store = Store.objects.create(
            user=self.owner,
            name='Branding shop',
            status=Store.STATUS_ACTIVE,
            verified_at=timezone.now(),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.base = f'/api/v1/stores/{self.store.pk}/'

    @staticmethod
    def image(size: tuple[int, int], image_format: str = 'PNG') -> SimpleUploadedFile:
        buffer = BytesIO()
        Image.new('RGB', size, 'green').save(buffer, format=image_format)
        return SimpleUploadedFile('photo.png', buffer.getvalue(), content_type='image/png')

    def test_avatar_and_banner_are_uploaded_and_served_through_the_public_proxy(self) -> None:
        for kind, size in [('avatar', (512, 512)), ('banner', (1600, 600))]:
            with self.subTest(kind=kind):
                response = self.client.post(
                    f'{self.base}profile-images/{kind}/',
                    {'image': self.image(size)},
                    format='multipart',
                )
                self.assertEqual(response.status_code, 200)
                image_url = response.json()[f'{kind}_url']
                self.assertTrue(image_url.startswith(f'/api/stores/{self.store.pk}/public/images/{kind}'))
                self.assertEqual(self.client.get(f'{self.base}profile/').json()[f'{kind}_url'], image_url)

                anonymous = APIClient()
                self.assertEqual(anonymous.get(f'{self.base}public/').json()['profile'][f'{kind}_url'], image_url)
                image_response = anonymous.get(image_url.replace('/api/stores/', '/api/v1/stores/').replace('?v=', '/?v='))
                self.assertEqual(image_response.status_code, 200)
                self.assertEqual(image_response['Content-Type'], 'image/png')
                with Image.open(BytesIO(b''.join(image_response.streaming_content))) as saved:
                    self.assertEqual(saved.size, size)
                image_response.close()

    def test_wrong_dimensions_invalid_files_and_oversized_uploads_are_rejected(self) -> None:
        oversized = self.image((512, 512)).read() + b'\0' * (5 * 1024 * 1024)
        cases = [
            ('avatar', self.image((511, 512))),
            ('banner', self.image((1600, 601))),
            ('avatar', self.image((512, 512), 'GIF')),
            ('avatar', SimpleUploadedFile('bad.png', b'not an image', content_type='image/png')),
            ('avatar', SimpleUploadedFile('large.png', oversized, content_type='image/png')),
        ]
        for kind, upload in cases:
            with self.subTest(kind=kind, filename=upload.name):
                response = self.client.post(
                    f'{self.base}profile-images/{kind}/', {'image': upload}, format='multipart',
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn('image', response.json()['error']['details'])
        self.assertFalse(StoreInfo.objects.filter(store=self.store).exists())

    def test_upload_and_removal_cannot_modify_another_merchant_store(self) -> None:
        self.client.force_authenticate(self.other)
        response = self.client.post(
            f'{self.base}profile-images/avatar/', {'image': self.image((512, 512))}, format='multipart',
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.delete(f'{self.base}profile-images/avatar/').status_code, 404)
        self.assertFalse(StoreInfo.objects.filter(store=self.store).exists())
        self.client.force_authenticate(None)
        response = self.client.post(
            f'{self.base}profile-images/avatar/', {'image': self.image((512, 512))}, format='multipart',
        )
        self.assertEqual(response.status_code, 401)

    def test_replacement_removal_and_store_deletion_clean_up_uploaded_files(self) -> None:
        url = f'{self.base}profile-images/avatar/'
        self.client.post(url, {'image': self.image((512, 512))}, format='multipart')
        profile = StoreInfo.objects.get(store=self.store)
        storage, original = profile.avatar_image.storage, profile.avatar_image.name
        with self.captureOnCommitCallbacks(execute=True):
            replacement = self.client.post(url, {'image': self.image((512, 512))}, format='multipart')
        self.assertEqual(replacement.status_code, 200)
        self.assertFalse(storage.exists(original))
        profile.refresh_from_db()
        current = profile.avatar_image.name
        self.assertTrue(storage.exists(current))
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['avatar_url'], '')
        self.assertFalse(storage.exists(current))
        self.assertEqual(APIClient().get(f'{self.base}public/images/avatar/').status_code, 404)

        self.client.post(url, {'image': self.image((512, 512))}, format='multipart')
        profile.refresh_from_db()
        current = profile.avatar_image.name
        with self.captureOnCommitCallbacks(execute=True):
            self.store.delete()
        self.assertFalse(storage.exists(current))

    def test_unverified_branding_is_visible_only_to_owner_or_backoffice(self) -> None:
        self.store.status = Store.STATUS_PENDING
        self.store.verified_at = None
        self.store.save()
        self.client.post(
            f'{self.base}profile-images/avatar/', {'image': self.image((512, 512))}, format='multipart',
        )
        url = f'{self.base}public/images/avatar/'
        self.assertEqual(APIClient().get(url).status_code, 404)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response.close()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_staff_can_brand_official_stores_but_not_merchant_stores(self) -> None:
        staff = User.objects.create_user(email='branding-staff@example.com', password='test-password', is_staff=True)
        official = Store.objects.create(user=staff, name='Official store', is_official=True)
        self.client.force_authenticate(staff)
        for store, expected in [(official, 200), (self.store, 404)]:
            with self.subTest(store=store.pk):
                response = self.client.post(
                    f'/api/v1/stores/{store.pk}/profile-images/banner/',
                    {'image': self.image((1600, 600))},
                    format='multipart',
                )
                self.assertEqual(response.status_code, expected)

    def test_existing_external_image_urls_are_preserved_when_no_file_is_uploaded(self) -> None:
        StoreInfo.objects.create(store=self.store, avatar_url='https://example.com/avatar.png')
        response = self.client.get(f'{self.base}profile/')
        self.assertEqual(response.json()['avatar_url'], 'https://example.com/avatar.png')
