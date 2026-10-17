from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from rest_framework.exceptions import ValidationError

from core.models import Review, User, Wishlist
from product.models import Product
from product.serializers import ProductSerializer
from store.models import Store
from utils.exceptions import custom_exception_handler


class ProductInteractionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="password",
            first_name="Buyer",
            last_name="One",
            gender="male",
            phone1="+2348012345678",
        )
        self.merchant = User.objects.create_user(
            email="merchant@example.com",
            password="password",
            first_name="Merchant",
            last_name="One",
            gender="female",
            phone1="+2348012345679",
        )
        self.store = Store.objects.create(
            user=self.merchant, username="merchant-store", name="Merchant Store"
        )
        self.product = Product.objects.create(
            store=self.store,
            title="Noise cancelling headphones",
            description="Comfortable wireless headphones",
            price=Decimal("120.00"),
            discount=10,
            available=8,
            category="electronics",
            visibility=True,
        )

    def test_wishlist_uniqueness_and_product_like_metadata(self):
        request = self.factory.post("/api/v1/wishlist/", {}, format="json")
        request.user = self.user

        Wishlist.objects.create(user=self.user, product=self.product)
        self.assertEqual(Wishlist.objects.count(), 1)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Wishlist.objects.create(user=self.user, product=self.product)
        self.assertEqual(Wishlist.objects.count(), 1)

        data = ProductSerializer(
            self.product, context={"request": request}
        ).data
        self.assertEqual(data["likes_count"], 1)
        self.assertTrue(data["is_liked"])

    def test_wishlist_delete_unlikes_product(self):
        wishlist = Wishlist.objects.create(user=self.user, product=self.product)
        wishlist.delete()
        self.assertFalse(Wishlist.objects.exists())

    def test_review_creation_updates_product_average_rating(self):
        payload = {
            "user": self.user.pk,
            "product": self.product.pk,
            "label": "Solid",
            "comment": "Great",
            "rating": 4,
        }
        review = Review.objects.create(
            user=self.user,
            product=self.product,
            label=payload["label"],
            comment=payload["comment"],
            rating=payload["rating"],
        )
        review.set_avg_rating()
        self.product.refresh_from_db()
        self.assertEqual(self.product.average_rating, Decimal("4.00"))

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Review.objects.create(
                    user=self.user,
                    product=self.product,
                    label=payload["label"],
                    comment=payload["comment"],
                    rating=payload["rating"],
                )
        self.assertEqual(Review.objects.count(), 1)


class ApiExceptionHandlerTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_validation_errors_use_consistent_error_envelope(self):
        request = self.factory.post("/products/", {}, format="json")
        response = custom_exception_handler(
            ValidationError({"title": ["This field is required."]}),
            {"request": request, "view": None},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "invalid")
        self.assertEqual(response.data["error"]["message"], "Request validation failed.")
        self.assertEqual(
            response.data["error"]["details"]["title"],
            ["This field is required."],
        )

    def test_unhandled_errors_are_logged_and_hidden(self):
        request = self.factory.get("/products/")
        with self.assertLogs("codematics.api", level="ERROR"):
            response = custom_exception_handler(
                RuntimeError("database exploded"),
                {"request": request, "view": None},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["error"]["code"], "server_error")
        self.assertEqual(response.data["error"]["message"], "An unexpected error occurred.")


class ProductStoreDropTests(TestCase):
    def setUp(self):
        from django.utils import timezone
        from datetime import timedelta
        self.factory = APIRequestFactory()
        self.merchant = User.objects.create_user(
            email="drop_merchant@example.com",
            password="password",
            first_name="Drop",
            last_name="Merchant",
            gender="female",
            phone1="+2348012345688",
        )
        self.store = Store.objects.create(
            user=self.merchant, username="hype-drops", name="Hype Drops",
            status=Store.STATUS_ACTIVE,
        )
        self.store.verified_at = timezone.now()
        self.store.save()
        from store.models import StoreAddress
        StoreAddress.objects.create(
            store=self.store,
            address='123 Drop St',
            city='New York',
            state='NY',
            zip='10001',
            country='US',
            is_default=True,
        )
        self.buyer = User.objects.create_user(
            email="hype_buyer@example.com",
            password="password",
            first_name="Hype",
            last_name="Buyer",
            gender="male",
            phone1="+2348012345689",
        )
        self.future_drop = Product.objects.create(
            store=self.store,
            title="Limited Edition Streetwear Hoodie",
            description="Ultra rare drop, strictly limited.",
            price=Decimal("150.00"),
            discount=0,
            available=50,
            category="fashion",
            visibility=True,
            drop_at=timezone.now() + timedelta(days=2),
        )
        self.past_drop = Product.objects.create(
            store=self.store,
            title="Archived Retro Sneakers",
            description="Drop is live and ready to buy.",
            price=Decimal("200.00"),
            discount=0,
            available=20,
            category="fashion",
            visibility=True,
            drop_at=timezone.now() - timedelta(hours=1),
        )

    def test_upcoming_drop_property_and_serialization(self):
        self.assertTrue(self.future_drop.is_upcoming_drop)
        self.assertFalse(self.past_drop.is_upcoming_drop)

        data = ProductSerializer(self.future_drop).data
        self.assertTrue(data["is_upcoming_drop"])
        self.assertIsNotNone(data["drop_at"])

    def test_upcoming_drop_blocks_purchase_validation(self):
        from product.policies import validate_purchase
        with self.assertRaises(ValidationError) as ctx:
            validate_purchase(self.future_drop, self.buyer)
        self.assertIn("upcoming drop", str(ctx.exception.detail))

    def test_past_drop_allows_purchase_validation(self):
        from product.policies import validate_purchase
        # Should execute without raising ValidationError
        validate_purchase(self.past_drop, self.buyer)

    def test_anti_bot_protection_throttles_bursts(self):
        from django.core.cache import cache
        from product.policies import check_drop_bot_protection
        cache.clear()
        request = self.factory.post("/api/v1/cart/")
        request.user = self.buyer

        # 9 requests should pass without error
        for _ in range(9):
            check_drop_bot_protection(self.future_drop, request)

        # 10th request also reaches max limit
        check_drop_bot_protection(self.future_drop, request)

        # 11th request triggers anti-bot throttling
        with self.assertRaises(ValidationError) as ctx:
            check_drop_bot_protection(self.future_drop, request)
        self.assertIn("Anti-bot protection active", str(ctx.exception.detail))

    def test_merchant_product_serializer_drop_at_support(self):
        from store.serializers import MerchantProductSerializer
        from django.utils import timezone
        from datetime import timedelta

        target_time = timezone.now() + timedelta(days=5)
        serializer = MerchantProductSerializer(
            instance=self.future_drop,
            data={"title": "Updated Drop Title", "price": "175.00", "drop_at": target_time.isoformat()},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated_product = serializer.save()
        self.assertEqual(updated_product.title, "Updated Drop Title")
        self.assertTrue(updated_product.is_upcoming_drop)

    def test_clickbank_affiliate_rejects_drop_at(self):
        from store.serializers import MerchantProductSerializer
        from django.utils import timezone
        from datetime import timedelta

        data = {
            "title": "ClickBank Diet Guide",
            "description": "A comprehensive diet guide.",
            "category": "health",
            "price": "49.99",
            "product_type": "affiliate_clickbank",
            "affiliate_hoplink": "https://hop.clickbank.net/?affiliate=user&vendor=diet",
            "drop_at": (timezone.now() + timedelta(days=1)).isoformat(),
        }
        serializer = MerchantProductSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("drop_at", serializer.errors)

    def test_product_drop_live_endpoint_json_and_sse(self):
        from storefront.views import ProductDropLiveView
        view = ProductDropLiveView.as_view()

        # Test JSON format query
        req_json = self.factory.get(f"/api/v1/products/{self.future_drop.pk}/drop-live/?format=json")
        resp_json = view(req_json, pk=self.future_drop.pk)
        self.assertEqual(resp_json.status_code, 200)
        self.assertEqual(resp_json.data["product_id"], self.future_drop.pk)
        self.assertFalse(resp_json.data["is_dropped"])
        self.assertGreaterEqual(resp_json.data["viewers"], 1)

        # Test past drop JSON format query
        req_past = self.factory.get(f"/api/v1/products/{self.past_drop.pk}/drop-live/?format=json")
        resp_past = view(req_past, pk=self.past_drop.pk)
        self.assertEqual(resp_past.status_code, 200)
        self.assertTrue(resp_past.data["is_dropped"])

