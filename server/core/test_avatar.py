from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import User


class UserAvatarTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email='avatar-test@example.com',
            password='test-password',
            first_name='Avatar',
            last_name='Tester',
        )
        self.staff = User.objects.create_user(
            email='avatar-staff@example.com',
            password='test-password',
            first_name='Staff',
            last_name='Tester',
            is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @staticmethod
    def sample_image(size: tuple[int, int] = (512, 512), image_format: str = 'PNG') -> SimpleUploadedFile:
        buffer = BytesIO()
        Image.new('RGB', size, 'blue').save(buffer, format=image_format)
        return SimpleUploadedFile('photo.png', buffer.getvalue(), content_type='image/png')

    def test_user_can_upload_and_delete_avatar(self) -> None:
        # 1. Upload valid 512x512 avatar
        response = self.client.post(
            '/api/v1/me/avatar/',
            {'image': self.sample_image((512, 512))},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200)
        avatar_url = response.json().get('avatar_url')
        self.assertTrue(avatar_url)
        self.assertTrue(avatar_url.startswith(f'/api/users/{self.user.pk}/public/images/avatar'))

        # 2. Verify me endpoint reflects the avatar_url
        me_response = self.client.get('/api/v1/me/')
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json().get('avatar_url'), avatar_url)

        # 3. Verify public image endpoint serves the file
        anon = APIClient()
        public_url = avatar_url.replace('/api/users/', '/api/v1/users/').split('?')[0] + '/'
        img_response = anon.get(public_url)
        self.assertEqual(img_response.status_code, 200)
        self.assertEqual(img_response['Content-Type'], 'image/png')

        # 4. Remove avatar
        delete_response = self.client.delete('/api/v1/me/avatar/')
        self.assertEqual(delete_response.status_code, 200)
        self.assertIsNone(delete_response.json().get('avatar_url'))

        # 5. Verify public image endpoint now returns 404
        self.assertEqual(anon.get(public_url).status_code, 404)

    def test_staff_and_admin_can_upload_avatar(self) -> None:
        self.client.force_authenticate(self.staff)
        response = self.client.post(
            '/api/v1/me/avatar/',
            {'image': self.sample_image((512, 512))},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200)
        avatar_url = response.json().get('avatar_url')
        self.assertTrue(avatar_url)
        self.assertTrue(avatar_url.startswith(f'/api/users/{self.staff.pk}/public/images/avatar'))

    def test_wrong_dimensions_and_invalid_formats_rejected(self) -> None:
        # Wrong dimensions
        response = self.client.post(
            '/api/v1/me/avatar/',
            {'image': self.sample_image((300, 300))},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)

        # Unsupported format (GIF)
        response = self.client.post(
            '/api/v1/me/avatar/',
            {'image': self.sample_image((512, 512), image_format='GIF')},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)
