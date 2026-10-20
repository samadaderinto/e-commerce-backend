from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Review, User
from product.models import Product
from store.models import Store


@override_settings(ROOT_URLCONF='storefront.urls')
class ReviewInputAuditTests(TestCase):
    def setUp(self) -> None:
        buyer = User.objects.create_user(email='review-input@test.local', password='test')
        store = Store.objects.create(
            user=buyer, name='Review input fixture', status='active', verified_at=timezone.now(),
        )
        self.product = Product.objects.create(
            store=store, title='Review fixture', price='10', discount=0, available=1,
        )
        self.client = APIClient()
        self.client.force_authenticate(buyer)
        self.buyer = buyer

    def test_malformed_review_photo_url_is_validation_not_server_error(self) -> None:
        for image in ('https://[broken/image.png', 'https://example.com:broken/image.png'):
            with self.subTest(image=image), patch('storefront.views.check_is_verified_buyer', return_value=True):
                response = self.client.post(
                    f'/api/v1/products/{self.product.pk}/reviews/',
                    {'rating': 5, 'label': 'Useful', 'comment': 'Fixture review', 'images': [image]},
                    format='json',
                )
                self.assertEqual(response.status_code, 400)
                self.assertFalse(Review.objects.filter(product=self.product).exists())

    def test_older_own_review_remains_editable_independently_of_current_page(self) -> None:
        own = Review.objects.create(
            user=self.buyer, product=self.product, rating=4, label='My older review', comment='Original text',
        )
        for index in range(51):
            reviewer = User.objects.create_user(email=f'reviewer-{index}@test.local', password='test')
            Review.objects.create(
                user=reviewer, product=self.product, rating=5, label='New review', comment='Fixture',
            )
        url = f'/api/v1/products/{self.product.pk}/reviews/'
        response = self.client.get(url, {'paginated': '1', 'limit': 20})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 52)
        self.assertEqual(len(response.data['results']), 20)
        self.assertNotIn(own.pk, [row['id'] for row in response.data['results']])
        self.assertEqual(response.data['own_review']['id'], own.pk)
        self.assertTrue(response.data['own_review']['is_own_review'])
        last = self.client.get(url, {'paginated': '1', 'limit': 20, 'offset': 40})
        self.assertIn(own.pk, [row['id'] for row in last.data['results']])
        self.client.force_authenticate(None)
        self.assertIsNone(self.client.get(url, {'paginated': '1'}).data['own_review'])
