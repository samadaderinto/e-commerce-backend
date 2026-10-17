"""Regression coverage for malformed identifiers and listing date boundaries."""
from decimal import Decimal

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Review, User
from product.models import Product
from store.models import Store


@pytest.fixture
def buyer(db: None) -> User:
    return User.objects.create_user(email='validation-buyer@example.test', password='test-password')


@pytest.fixture
def client(buyer: User) -> APIClient:
    result = APIClient()
    result.force_authenticate(buyer)
    return result


@pytest.fixture
def product(db: None) -> Product:
    seller = User.objects.create_user(email='validation-seller@example.test', password='test-password')
    store = Store.objects.create(
        user=seller, name='Validation store', status='active', verified_at=timezone.now(),
    )
    return Product.objects.create(
        store=store, title='Validation product', price=Decimal('10'),
        discount=0, available=5, category='electronics', visibility=True,
    )


@pytest.mark.django_db
@override_settings(ROOT_URLCONF='storefront.urls')
@pytest.mark.parametrize('identity', ['not-a-number', '-1', '0', '999999999'])
def test_invalid_affiliate_product_paths_return_404(identity: str) -> None:
    anonymous = APIClient()
    for path in (
        f'/api/v1/affiliates/r/example/{identity}/example/',
        f'/api/v1/affiliates/clickbank/outbound/{identity}/',
    ):
        assert anonymous.get(path).status_code == 404


@pytest.mark.django_db
@override_settings(ROOT_URLCONF='storefront.urls')
@pytest.mark.parametrize('identity', ['not-a-number', '', '-1', '0', '1.5'])
def test_review_ids_require_positive_integers(
    client: APIClient, product: Product, identity: str,
) -> None:
    response = client.delete(f'/api/v1/products/{product.pk}/reviews/?review_id={identity}')
    assert response.status_code == 400


@pytest.mark.django_db
@override_settings(ROOT_URLCONF='storefront.urls')
def test_valid_review_ids_preserve_ownership_checks(
    client: APIClient, product: Product, buyer: User,
) -> None:
    foreign = Review.objects.create(
        user=product.store.user, product=product, rating=5, label='Review', comment='Details',
    )
    own = Review.objects.create(
        user=buyer, product=product, rating=5, label='Review', comment='Details',
    )
    url = f'/api/v1/products/{product.pk}/reviews/'
    assert client.delete(url + f'?review_id={foreign.pk}').status_code == 403
    assert Review.objects.filter(pk=foreign.pk).exists()
    assert client.delete(url + '?review_id=999999999').status_code == 404
    assert client.delete(url + f'?review_id={own.pk}').status_code == 204
    assert not Review.objects.filter(pk=own.pk).exists()


@pytest.mark.django_db
@override_settings(ROOT_URLCONF='storefront.urls')
def test_end_date_boundary_is_validated_before_filtering(client: APIClient) -> None:
    assert client.get('/api/v1/wallet/?end_date=9999-12-31').status_code == 400
    assert client.get('/api/v1/wallet/?end_date=2026-10-16').status_code == 200
