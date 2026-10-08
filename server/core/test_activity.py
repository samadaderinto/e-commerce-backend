from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.models import update_last_login
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.utils import timezone

from core.activity import record_activity
from core.models import Review, User
from notification.models import Notification
from payment.models import Order
from product.models import Product
from store.models import Store
from rest_framework.test import APIClient


class ActivityTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email='activity@example.com', password='ExamplePass2026!', first_name='Active', last_name='User', gender='male', phone1='+12015550123')
        self.store = Store.objects.create(user=self.user, name='Activity store', username='activity-store')

    def test_login_and_activity_do_not_change_profile_revision(self) -> None:
        original = self.user.updated
        update_last_login(None, self.user)
        record_activity(self.user)
        self.user.refresh_from_db()
        self.store.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)
        self.assertEqual(self.user.updated, original)
        self.assertEqual(self.store.last_active_at, self.user.last_active_at)
        first_activity = self.user.last_active_at
        record_activity(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_active_at, first_activity)
        self.user.first_name = 'Changed'
        self.user.save(update_fields=['first_name'])
        self.assertGreater(self.user.updated, original)

    def test_order_dates_follow_transitions_only(self) -> None:
        order = Order.objects.create(user=self.user, status='confirmed', total=Decimal('20'))
        placed = order.ordered_date
        changed = order.status_updated_at
        order.tracking_number = 'tracking'
        order.save(update_fields=['tracking_number'])
        self.assertEqual(order.status_updated_at, changed)
        order.status = 'cancelled'
        order.save(update_fields=['status'])
        order.refresh_from_db()
        self.assertEqual(order.ordered_date, placed)
        self.assertEqual(order.cancelled_at, order.status_updated_at)
        self.assertGreater(order.status_updated_at, changed)
        order.status = 'refunded'
        order.save(update_fields=['status'])
        order.refresh_from_db()
        self.assertEqual(order.refunded_at, order.status_updated_at)

    def test_review_edit_and_store_revision_are_recorded(self) -> None:
        product = Product.objects.create(store=self.store, title='Tracked', description='Tracked', price=Decimal('10'), discount=0, available=1, category='books')
        review = Review.objects.create(user=self.user, product=product, label='Good', comment='Good', rating=5)
        self.assertFalse(review.is_edited)
        review.comment = 'Updated opinion'
        review.save(update_fields=['comment'])
        review.refresh_from_db()
        self.assertTrue(review.is_edited)
        before = self.store.updated
        product.title = 'Revised'
        product.save(update_fields=['title', 'updated'])
        self.store.refresh_from_db()
        self.assertGreater(self.store.updated, before)

    def test_read_timestamp_is_stable_until_marked_unread(self) -> None:
        notification = Notification.objects.create(recipient=self.user, actor_content_type=ContentType.objects.get_for_model(self.user), actor_object_id=str(self.user.pk), verb='Test')
        notification.mark_as_read()
        first = notification.read_at
        notification.mark_as_read()
        self.assertEqual(notification.read_at, first)
        notification.mark_as_unread()
        notification.refresh_from_db()
        self.assertIsNone(notification.read_at)
        self.assertTrue(notification.unread)

    @override_settings(ROOT_URLCONF='storefront.urls')
    def test_jwt_login_records_login_and_read_only_activity(self) -> None:
        client = APIClient()
        original = self.user.updated
        response = client.post('/api/v1/auth/login/', {'email': self.user.email, 'password': 'ExamplePass2026!'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)
        self.assertEqual(self.user.updated, original)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        response = client.patch('/api/v1/me/', {'last_active_at': '2000-01-01T00:00:00Z', 'last_login': None}, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.last_active_at.year, 2000)
        self.assertIsNotNone(self.user.last_login)

    @override_settings(ROOT_URLCONF='storefront.urls')
    def test_product_views_refresh_history_and_cart_deletion_activity(self) -> None:
        from cart.models import Cart, CartItem
        from core.models import Recent
        self.store.status = Store.STATUS_ACTIVE
        self.store.verified_at = timezone.now()
        self.store.save()
        product = Product.objects.create(store=self.store, title='Viewed', description='Viewed', price=Decimal('10'), discount=0, available=2, category='books')
        buyer = User.objects.create_user(email='viewer@example.com', password='ExamplePass2026!', first_name='Viewer', last_name='User', gender='male', phone1='+12015550123')
        client = APIClient()
        client.force_authenticate(buyer)
        self.assertEqual(client.get(f'/api/v1/products/{product.pk}/').status_code, 200)
        recent = Recent.objects.get(user=buyer, product=product)
        viewed = recent.updated
        self.assertEqual(client.get(f'/api/v1/products/{product.pk}/').status_code, 200)
        recent.refresh_from_db()
        self.assertGreater(recent.updated, viewed)
        self.assertEqual(Recent.objects.filter(user=buyer, product=product).count(), 1)
        cart = Cart.objects.create(user=buyer)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        before = cart.updated
        response = client.delete(f'/api/v1/cart/?product={product.pk}')
        self.assertEqual(response.status_code, 200)
        cart.refresh_from_db()
        self.assertGreater(cart.updated, before)

    def test_coupon_preview_does_not_record_a_redemption(self) -> None:
        from payment.models import Coupon
        from payment.couponing import calculate_coupon_discount
        coupon = Coupon.objects.create(code='TRACKED', valid_to=timezone.now() + timedelta(days=1), discount=10, num_available=5)
        calculate_coupon_discount(coupon, self.user, [], Decimal('20'), reserve=False)
        coupon.refresh_from_db()
        self.assertIsNone(coupon.last_used_at)
        calculate_coupon_discount(coupon, self.user, [], Decimal('20'), reserve=True)
        coupon.refresh_from_db()
        self.assertIsNotNone(coupon.last_used_at)

    def test_affiliate_redirect_records_each_click(self) -> None:
        from affiliates.models import Marketer, Redirect, Url
        from affiliates.views import AffiliatesViewSet
        from rest_framework.test import APIRequestFactory
        product = Product.objects.create(store=self.store, title='Linked', description='Linked', price=Decimal('10'), discount=0, available=2, category='books')
        marketer = Marketer.objects.create(user=self.user, name='Tracking marketer')
        url = Url.objects.create(marketer=marketer, product=product, identifier='tracked', active=True)
        view = AffiliatesViewSet.as_view({'get': 'redirect_url'})
        for _ in range(2):
            response = view(APIRequestFactory().get('/affiliate/r/'), marketer_id=marketer.marketer_id, product_id=str(product.pk), identifier=url.identifier)
            self.assertEqual(response.status_code, 302)
        click = Redirect.objects.get(urlId=url)
        self.assertEqual(click.click_rate, 2)
        self.assertIsNotNone(click.last_clicked_at)
